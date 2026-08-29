//! Read deadlines from baud + envelope size.

use crate::BaudRate;

/// Wire time assumes 10 serial bits per octet (8N1 + start).
///
/// Policy: `max(1000 ms, 4 * wire_ms + 100 ms)` plus optional override handled by CLI.
#[must_use]
pub fn deadline_ms(baud: BaudRate, envelope_bytes: usize) -> u64 {
    let baud = u64::from(baud.as_u32()).max(1);
    let bits = (envelope_bytes as u64).saturating_mul(10);
    let wire_ms = bits.saturating_mul(1000).div_ceil(baud);
    let computed = wire_ms.saturating_mul(4).saturating_add(100);
    computed.max(1_000)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::wire::envelope::HARD_MAX_PAYLOAD;

    #[test]
    fn deadlines_at_policy_bauds() {
        let envelope = 10 + usize::from(HARD_MAX_PAYLOAD) + 4;
        for baud in BaudRate::ALL {
            let ms = deadline_ms(baud, envelope);
            assert!(ms >= 1_000, "{baud} -> {ms}");
            // 9600 needs well over 1s for 256-byte payloads.
            if baud == BaudRate::B9600 {
                assert!(ms > 1_000, "9600 should inflate past floor");
            }
        }
    }
}
