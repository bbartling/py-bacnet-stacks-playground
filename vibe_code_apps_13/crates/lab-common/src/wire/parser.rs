//! Incremental envelope parser with bounded resync.

use super::envelope::{
    crc_over, Direction, Envelope, EnvelopeError, HARD_MAX_PAYLOAD, PREAMBLE, PROTOCOL_VERSION,
};

/// Events emitted while feeding bytes.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ParseEvent {
    Frame(Envelope),
    Rejected(EnvelopeError),
    Resynced { skipped: usize },
}

/// Streaming parser. Cap buffer growth when noise never yields a preamble.
#[derive(Debug)]
pub struct EnvelopeParser {
    buf: Vec<u8>,
    max_payload: u16,
    max_buf: usize,
}

impl EnvelopeParser {
    #[must_use]
    pub fn new(max_payload: u16) -> Self {
        let max_payload = max_payload.min(HARD_MAX_PAYLOAD);
        let frame_cap = 10 + usize::from(max_payload) + 4;
        Self {
            buf: Vec::with_capacity(frame_cap),
            max_payload,
            max_buf: frame_cap.saturating_mul(4).max(1024),
        }
    }

    /// Push bytes; return zero or more parse events.
    pub fn push(&mut self, chunk: &[u8]) -> Vec<ParseEvent> {
        self.buf.extend_from_slice(chunk);
        let mut events = Vec::new();
        loop {
            match self.try_one() {
                Ok(None) => break,
                Ok(Some(ev)) | Err(ev) => events.push(ev),
            }
            if self.buf.len() > self.max_buf {
                // Drop oldest half and keep scanning — never unbounded.
                let drop_n = self.buf.len() / 2;
                self.buf.drain(..drop_n);
                events.push(ParseEvent::Resynced { skipped: drop_n });
            }
        }
        events
    }

    fn try_one(&mut self) -> Result<Option<ParseEvent>, ParseEvent> {
        if self.buf.is_empty() {
            return Ok(None);
        }
        // Find preamble.
        let Some(start) = find_preamble(&self.buf) else {
            let skipped = self.buf.len().saturating_sub(1);
            if skipped > 0 {
                self.buf.drain(..skipped);
                return Err(ParseEvent::Resynced { skipped });
            }
            return Ok(None);
        };
        if start > 0 {
            self.buf.drain(..start);
            return Err(ParseEvent::Resynced { skipped: start });
        }
        if self.buf.len() < 10 {
            return Ok(None);
        }
        let version = self.buf[2];
        if version != PROTOCOL_VERSION {
            self.buf.drain(..1);
            return Err(ParseEvent::Rejected(EnvelopeError::BadVersion(version)));
        }
        let direction = match Direction::try_from_u8(self.buf[3]) {
            Ok(d) => d,
            Err(e) => {
                self.buf.drain(..1);
                return Err(ParseEvent::Rejected(e));
            }
        };
        let sequence = u32::from_be_bytes([self.buf[4], self.buf[5], self.buf[6], self.buf[7]]);
        let declared = u16::from_be_bytes([self.buf[8], self.buf[9]]);
        if declared > self.max_payload {
            self.buf.drain(..1);
            return Err(ParseEvent::Rejected(EnvelopeError::PayloadTooLarge {
                declared,
                max: self.max_payload,
            }));
        }
        let payload_len = usize::from(declared);
        let total = 10 + payload_len + 4;
        if self.buf.len() < total {
            return Ok(None);
        }
        let body = &self.buf[2..10 + payload_len];
        let expected = crc_over(body);
        let actual = u32::from_be_bytes([
            self.buf[10 + payload_len],
            self.buf[10 + payload_len + 1],
            self.buf[10 + payload_len + 2],
            self.buf[10 + payload_len + 3],
        ]);
        if expected != actual {
            self.buf.drain(..1);
            return Err(ParseEvent::Rejected(EnvelopeError::BadCrc {
                expected,
                actual,
            }));
        }
        let payload = self.buf[10..10 + payload_len].to_vec();
        self.buf.drain(..total);
        Ok(Some(ParseEvent::Frame(Envelope {
            direction,
            sequence,
            payload,
        })))
    }
}

fn find_preamble(buf: &[u8]) -> Option<usize> {
    buf.windows(2).position(|w| w == PREAMBLE)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::wire::envelope::{encode_envelope, PayloadPattern};

    fn encode(dir: Direction, seq: u32, payload: &[u8]) -> Vec<u8> {
        let mut out = Vec::new();
        encode_envelope(dir, seq, payload, &mut out).unwrap();
        out
    }

    #[test]
    fn split_at_every_byte() {
        let payload = vec![0x55; 17];
        let frame = encode(Direction::BToA, 7, &payload);
        for split in 0..=frame.len() {
            let mut p = EnvelopeParser::new(HARD_MAX_PAYLOAD);
            let mut events = p.push(&frame[..split]);
            events.extend(p.push(&frame[split..]));
            let frames: Vec<_> = events
                .into_iter()
                .filter_map(|e| match e {
                    ParseEvent::Frame(f) => Some(f),
                    _ => None,
                })
                .collect();
            assert_eq!(frames.len(), 1, "split={split}");
            assert_eq!(frames[0].sequence, 7);
            assert_eq!(frames[0].payload, payload);
        }
    }

    #[test]
    fn one_byte_at_a_time() {
        let mut payload = vec![0; 64];
        PayloadPattern::AllAa.fill(&mut payload, 0, 0);
        let frame = encode(Direction::AToB, 99, &payload);
        let mut p = EnvelopeParser::new(HARD_MAX_PAYLOAD);
        let mut got = None;
        for byte in frame {
            for ev in p.push(&[byte]) {
                if let ParseEvent::Frame(f) = ev {
                    got = Some(f);
                }
            }
        }
        let got = got.expect("frame");
        assert_eq!(got.payload, payload);
    }

    #[test]
    fn multiple_frames_one_buffer() {
        let a = encode(Direction::AToB, 1, b"hi");
        let b = encode(Direction::BToA, 2, b"there");
        let mut both = a;
        both.extend_from_slice(&b);
        let mut p = EnvelopeParser::new(HARD_MAX_PAYLOAD);
        let frames: Vec<_> = p
            .push(&both)
            .into_iter()
            .filter_map(|e| match e {
                ParseEvent::Frame(f) => Some(f.sequence),
                _ => None,
            })
            .collect();
        assert_eq!(frames, vec![1, 2]);
    }

    #[test]
    fn noise_then_resync() {
        let frame = encode(Direction::AToB, 3, &[1, 2, 3]);
        let mut noisy = vec![0x00, 0xFF, 0x55, 0x00];
        noisy.extend_from_slice(&frame);
        let mut p = EnvelopeParser::new(HARD_MAX_PAYLOAD);
        let frames: Vec<_> = p
            .push(&noisy)
            .into_iter()
            .filter_map(|e| match e {
                ParseEvent::Frame(f) => Some(f.sequence),
                _ => None,
            })
            .collect();
        assert_eq!(frames, vec![3]);
    }

    #[test]
    fn bad_crc_rejected() {
        let mut frame = encode(Direction::AToB, 1, b"x");
        *frame.last_mut().unwrap() ^= 0xFF;
        let mut p = EnvelopeParser::new(HARD_MAX_PAYLOAD);
        let rejected = p
            .push(&frame)
            .into_iter()
            .any(|e| matches!(e, ParseEvent::Rejected(EnvelopeError::BadCrc { .. })));
        assert!(rejected);
    }
}
