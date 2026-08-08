//! Guided 10-step operator tutorial content (ends at SIM).

use crate::nav::AppMode;

/// Static copy for each tutorial step (1..=10).
#[derive(Debug, Clone, Copy)]
pub struct TutorialStep {
    pub title: &'static str,
    /// Short supporting sentence shown under the title.
    pub blurb: &'static str,
}

pub const STEP_COUNT: u8 = 10;

const STEPS: [TutorialStep; 10] = [
    TutorialStep {
        title: "Welcome",
        blurb: "Lakeside Heating DSM screens portable TOD/demand tariffs against hybrid BAS+delta walks. Honesty: IdealLoads + fixed-COP ≠ GSHP. Operational DSM is BLOCKED / NO-GO until multi-res gates clear — recommendations stay off.",
    },
    TutorialStep {
        title: "Site & models",
        blurb: "Confirm hybrid ONNX and nearest-day library load status before trusting any walk numbers.",
    },
    TutorialStep {
        title: "Validation glance",
        blurb: "Compact E+ multi-resolution badges only — full detail lives in Workspace → Validation.",
    },
    TutorialStep {
        title: "Tariff basics",
        blurb: "Three portable rates plus Reset to Creekside CP-2. Full TOD grid is in Workspace → Tariff.",
    },
    TutorialStep {
        title: "Pick a day",
        blurb: "Choose month, day-of-year, and weekend flag for the screening day.",
    },
    TutorialStep {
        title: "Baseline day",
        blurb: "One peak kW and one daily kWh from the HVAC 24/7 compare arm (run Compare if empty).",
    },
    TutorialStep {
        title: "DSM strategy",
        blurb: "Pick a named strategy. This is strategy enumeration screening — not mathematical optimization.",
    },
    TutorialStep {
        title: "Engineering check",
        blurb: "Nearest-Day + E+ Delta is the engineering benchmark (not ML). Review peak, kWh, and OOD.",
    },
    TutorialStep {
        title: "Day cost",
        blurb: "Day total with energy vs demand split under the portable TOD tariff.",
    },
    TutorialStep {
        title: "SIM",
        blurb: "Baseline vs DSM kW overlay. If DSM is NO-GO, recommendations remain blocked.",
    },
];

/// Title + blurb for step in 1..=10 (clamped).
pub fn step_content(step: u8) -> TutorialStep {
    let idx = step
        .clamp(AppMode::TUTORIAL_FIRST, AppMode::TUTORIAL_LAST) as usize
        - 1;
    STEPS[idx]
}

pub fn strategy_blurb(strategy_id: &str) -> &'static str {
    match strategy_id {
        "baseline" => "Occupied setpoints all day — reference, not a savings strategy.",
        "stagger_preheat" => "Staggered zone preheat before occupancy to blunt the morning peak.",
        "flat_24_7" => "All zones heat all day — compare arm / worst-case peak shape.",
        "deep_setback" => "Deep unoccupied setback; recovery may rebound into a sharp peak.",
        "morning_all_on" => "All zones preheat together — often peak-heavy vs stagger.",
        _ => "Named strategy from the screening library.",
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::nav::AppMode;

    #[test]
    fn exactly_ten_steps_last_is_sim() {
        assert_eq!(STEP_COUNT, 10);
        assert_eq!(STEPS.len(), 10);
        assert_eq!(step_content(10).title, "SIM");
        assert_eq!(AppMode::TUTORIAL_SIM, 10);
        assert_eq!(step_content(AppMode::TUTORIAL_LAST).title, "SIM");
    }

    #[test]
    fn step_content_clamps() {
        assert_eq!(step_content(0).title, step_content(1).title);
        assert_eq!(step_content(99).title, "SIM");
        assert_eq!(step_content(1).title, "Welcome");
    }
}
