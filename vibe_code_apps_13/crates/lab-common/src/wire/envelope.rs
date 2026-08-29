//! Encode/decode helpers for the private Phase 1 envelope.

use core::fmt;

use crc32fast::Hasher;
use serde::{Deserialize, Serialize};

/// Frame magic.
pub const PREAMBLE: [u8; 2] = [0x55, 0xAA];
/// Envelope version byte.
pub const PROTOCOL_VERSION: u8 = 1;
/// Hard ceiling for declared payload length (CLI may lower this).
pub const HARD_MAX_PAYLOAD: u16 = 256;

/// Required length sweep when `max_payload` permits.
pub const BOUNDARY_LENGTHS: [u16; 16] = [
    0, 1, 2, 7, 8, 15, 16, 31, 32, 63, 64, 127, 128, 254, 255, 256,
];

/// Direction tag on the wire.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[repr(u8)]
pub enum Direction {
    AToB = 0xA1,
    BToA = 0xB1,
}

impl Direction {
    #[must_use]
    pub const fn as_u8(self) -> u8 {
        self as u8
    }

    #[must_use]
    pub const fn opposite(self) -> Self {
        match self {
            Self::AToB => Self::BToA,
            Self::BToA => Self::AToB,
        }
    }

    /// # Errors
    ///
    /// Returns [`EnvelopeError::BadDirection`] for unknown tags.
    pub fn try_from_u8(value: u8) -> Result<Self, EnvelopeError> {
        match value {
            0xA1 => Ok(Self::AToB),
            0xB1 => Ok(Self::BToA),
            other => Err(EnvelopeError::BadDirection(other)),
        }
    }
}

impl fmt::Display for Direction {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::AToB => f.write_str("A->B"),
            Self::BToA => f.write_str("B->A"),
        }
    }
}

/// Deterministic payload families used by the coordinator.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum PayloadPattern {
    AllZero,
    AllOne,
    All55,
    AllAa,
    Ramp,
    PseudoRandom,
}

impl PayloadPattern {
    pub const CYCLE: [Self; 6] = [
        Self::AllZero,
        Self::AllOne,
        Self::All55,
        Self::AllAa,
        Self::Ramp,
        Self::PseudoRandom,
    ];

    /// Fill `out` with the pattern. For [`Self::PseudoRandom`], `seed` and `sequence` mix the stream.
    pub fn fill(self, out: &mut [u8], seed: u64, sequence: u32) {
        match self {
            Self::AllZero => out.fill(0x00),
            Self::AllOne => out.fill(0xFF),
            Self::All55 => out.fill(0x55),
            Self::AllAa => out.fill(0xAA),
            Self::Ramp => {
                for (i, byte) in out.iter_mut().enumerate() {
                    *byte = u8::try_from(i & 0xFF).unwrap_or(0);
                }
            }
            Self::PseudoRandom => {
                // Tiny deterministic LCG — no rand crate in lab-common.
                let mut state = seed
                    .wrapping_mul(0x9E37_79B9_7F4A_7C15)
                    .wrapping_add(u64::from(sequence));
                for byte in out.iter_mut() {
                    state = state
                        .wrapping_mul(6_364_136_223_846_793_005)
                        .wrapping_add(1);
                    *byte = u8::try_from((state >> 33) & 0xFF).unwrap_or(0);
                }
            }
        }
    }
}

impl fmt::Display for PayloadPattern {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(match self {
            Self::AllZero => "all_00",
            Self::AllOne => "all_ff",
            Self::All55 => "all_55",
            Self::AllAa => "all_aa",
            Self::Ramp => "ramp",
            Self::PseudoRandom => "prng",
        })
    }
}

/// Decoded envelope (payload owned).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Envelope {
    pub direction: Direction,
    pub sequence: u32,
    pub payload: Vec<u8>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum EnvelopeError {
    BadVersion(u8),
    BadDirection(u8),
    PayloadTooLarge { declared: u16, max: u16 },
    BadCrc { expected: u32, actual: u32 },
    Truncated,
}

impl fmt::Display for EnvelopeError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::BadVersion(v) => write!(f, "unsupported envelope version {v}"),
            Self::BadDirection(v) => write!(f, "bad direction tag 0x{v:02X}"),
            Self::PayloadTooLarge { declared, max } => {
                write!(f, "declared payload {declared} exceeds max {max}")
            }
            Self::BadCrc { expected, actual } => {
                write!(
                    f,
                    "CRC mismatch expected=0x{expected:08X} actual=0x{actual:08X}"
                )
            }
            Self::Truncated => f.write_str("truncated envelope"),
        }
    }
}

impl std::error::Error for EnvelopeError {}

/// CRC-32 over version..payload (bytes after preamble).
#[must_use]
pub fn crc_over(body: &[u8]) -> u32 {
    let mut hasher = Hasher::new();
    hasher.update(body);
    hasher.finalize()
}

/// Encode one envelope into `out` (cleared first).
///
/// # Errors
///
/// Returns [`EnvelopeError::PayloadTooLarge`] when payload exceeds `HARD_MAX_PAYLOAD`.
pub fn encode_envelope(
    direction: Direction,
    sequence: u32,
    payload: &[u8],
    out: &mut Vec<u8>,
) -> Result<(), EnvelopeError> {
    let len = u16::try_from(payload.len()).map_err(|_| EnvelopeError::PayloadTooLarge {
        declared: u16::MAX,
        max: HARD_MAX_PAYLOAD,
    })?;
    if len > HARD_MAX_PAYLOAD {
        return Err(EnvelopeError::PayloadTooLarge {
            declared: len,
            max: HARD_MAX_PAYLOAD,
        });
    }
    out.clear();
    out.extend_from_slice(&PREAMBLE);
    out.push(PROTOCOL_VERSION);
    out.push(direction.as_u8());
    out.extend_from_slice(&sequence.to_be_bytes());
    out.extend_from_slice(&len.to_be_bytes());
    out.extend_from_slice(payload);
    let crc = crc_over(&out[2..]);
    out.extend_from_slice(&crc.to_be_bytes());
    Ok(())
}

/// Decode a complete buffer that already starts at preamble (for unit tests).
///
/// # Errors
///
/// Propagates version/direction/length/CRC failures.
#[allow(dead_code)]
fn decode_complete(buf: &[u8], max_payload: u16) -> Result<Envelope, EnvelopeError> {
    if buf.len() < 14 {
        return Err(EnvelopeError::Truncated);
    }
    if buf[0..2] != PREAMBLE {
        return Err(EnvelopeError::Truncated);
    }
    let version = buf[2];
    if version != PROTOCOL_VERSION {
        return Err(EnvelopeError::BadVersion(version));
    }
    let direction = Direction::try_from_u8(buf[3])?;
    let sequence = u32::from_be_bytes([buf[4], buf[5], buf[6], buf[7]]);
    let declared = u16::from_be_bytes([buf[8], buf[9]]);
    if declared > max_payload.min(HARD_MAX_PAYLOAD) {
        return Err(EnvelopeError::PayloadTooLarge {
            declared,
            max: max_payload.min(HARD_MAX_PAYLOAD),
        });
    }
    let payload_len = usize::from(declared);
    let total = 10 + payload_len + 4;
    if buf.len() < total {
        return Err(EnvelopeError::Truncated);
    }
    let body = &buf[2..10 + payload_len];
    let expected = crc_over(body);
    let actual = u32::from_be_bytes([
        buf[10 + payload_len],
        buf[10 + payload_len + 1],
        buf[10 + payload_len + 2],
        buf[10 + payload_len + 3],
    ]);
    if expected != actual {
        return Err(EnvelopeError::BadCrc { expected, actual });
    }
    Ok(Envelope {
        direction,
        sequence,
        payload: buf[10..10 + payload_len].to_vec(),
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn round_trip_every_boundary() {
        let mut encoded = Vec::new();
        for &len in &BOUNDARY_LENGTHS {
            let mut payload = vec![0_u8; usize::from(len)];
            PayloadPattern::Ramp.fill(&mut payload, 1, 2);
            encode_envelope(Direction::AToB, 42, &payload, &mut encoded).unwrap();
            let decoded = decode_complete(&encoded, HARD_MAX_PAYLOAD).unwrap();
            assert_eq!(decoded.sequence, 42);
            assert_eq!(decoded.payload, payload);
        }
    }

    #[test]
    fn rejects_oversized_declared_length() {
        let mut buf = Vec::new();
        encode_envelope(Direction::AToB, 1, &[0; 8], &mut buf).unwrap();
        // Corrupt length to 512 while keeping short buffer — parser path tested elsewhere.
        buf[8] = 0x02;
        buf[9] = 0x00;
        let err = decode_complete(&buf, HARD_MAX_PAYLOAD).unwrap_err();
        assert!(matches!(err, EnvelopeError::PayloadTooLarge { .. }));
    }
}
