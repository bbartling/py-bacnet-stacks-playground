//! Token-edge counters for coexistence evidence (Gate 3+).
//!
//! A successful FEC ReadProperty alone must never set `hardware_ok=true`.
//! Reports must include directed Token edges (e.g. `0→3`, `3→7`, `7→0`).

use std::collections::BTreeMap;

use bacnet_transport::mstp_frame::{FrameType, MstpFrame};
use serde::Serialize;

/// Directed Token edge `source → destination`.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize)]
pub struct TokenEdge {
    pub from: u8,
    pub to: u8,
}

impl TokenEdge {
    #[must_use]
    pub fn new(from: u8, to: u8) -> Self {
        Self { from, to }
    }

    #[must_use]
    pub fn label(&self) -> String {
        format!("{}->{}", self.from, self.to)
    }
}

/// Accumulates MS/TP control-plane telemetry from decoded frames.
#[derive(Debug, Default, Clone, Serialize)]
pub struct TokenEdgeCounters {
    pub tokens: u64,
    pub self_tokens: u64,
    pub poll_for_master: u64,
    pub reply_to_pfm: u64,
    pub edges: BTreeMap<String, u64>,
}

impl TokenEdgeCounters {
    pub fn observe(&mut self, frame: &MstpFrame) {
        match frame.frame_type {
            FrameType::Token => {
                self.tokens += 1;
                if frame.source == frame.destination {
                    self.self_tokens += 1;
                }
                let edge = TokenEdge::new(frame.source, frame.destination);
                *self.edges.entry(edge.label()).or_insert(0) += 1;
            }
            FrameType::PollForMaster => {
                self.poll_for_master += 1;
            }
            FrameType::ReplyToPollForMaster => {
                self.reply_to_pfm += 1;
            }
            _ => {}
        }
    }

    /// Count for a specific directed Token edge.
    #[must_use]
    pub fn edge_count(&self, from: u8, to: u8) -> u64 {
        self.edges
            .get(&TokenEdge::new(from, to).label())
            .copied()
            .unwrap_or(0)
    }

    /// True when the classic three-master ring edges are all present at least once.
    #[must_use]
    pub fn has_ring_0_3_7(&self) -> bool {
        self.edge_count(0, 3) > 0 && self.edge_count(3, 7) > 0 && self.edge_count(7, 0) > 0
    }

    /// Coexistence soft-fail signals (software heuristics).
    #[must_use]
    pub fn coexistence_red_flags(&self) -> Vec<&'static str> {
        let mut flags = Vec::new();
        if self.self_tokens > 0 {
            flags.push("self_token_ts_to_ts");
        }
        if self.edge_count(3, 0) > 0 && self.edge_count(3, 7) == 0 {
            flags.push("token_3_to_0_without_3_to_7");
        }
        flags
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use bytes::Bytes;

    fn token(from: u8, to: u8) -> MstpFrame {
        MstpFrame {
            frame_type: FrameType::Token,
            destination: to,
            source: from,
            data: Bytes::new(),
        }
    }

    #[test]
    fn counts_ring_edges_and_self_token() {
        let mut c = TokenEdgeCounters::default();
        c.observe(&token(0, 3));
        c.observe(&token(3, 7));
        c.observe(&token(7, 0));
        c.observe(&token(3, 3));
        assert!(c.has_ring_0_3_7());
        assert_eq!(c.self_tokens, 1);
        assert_eq!(c.edge_count(0, 3), 1);
        assert!(c.coexistence_red_flags().contains(&"self_token_ts_to_ts"));
    }

    #[test]
    fn flags_token_3_to_0_without_successor_7() {
        let mut c = TokenEdgeCounters::default();
        c.observe(&token(3, 0));
        assert!(c
            .coexistence_red_flags()
            .contains(&"token_3_to_0_without_3_to_7"));
    }
}
