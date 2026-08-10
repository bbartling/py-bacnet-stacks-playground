//! Guided 10-step operator tutorial content (ends at SIM).

use crate::nav::AppMode;

/// Static copy for each tutorial step (1..=10).
#[derive(Debug, Clone, Copy)]
pub struct TutorialStep {
    pub title: &'static str,
    /// Short supporting sentence shown under the title (M&V plain language).
    pub blurb: &'static str,
}

pub const STEP_COUNT: u8 = 10;

const STEPS: [TutorialStep; 10] = [
    TutorialStep {
        title: "Welcome",
        blurb: "This app screens a school day’s energy cost under a portable tariff. Measured facility demand is the baseline; any “DSM savings” language stays off until fit screens clear.",
    },
    TutorialStep {
        title: "Site & models",
        blurb: "Confirm the site models loaded. Without them, peak and cost figures are placeholders — not M&V results.",
    },
    TutorialStep {
        title: "Fit to measured data",
        blurb: "Compare model vs bills and meters with NMBE (bias) and CV(RMSE) (scatter). Outside the screen ⇒ no verified savings claim.",
    },
    TutorialStep {
        title: "Tariff basics",
        blurb: "Set on-peak energy, off-peak energy, and demand $/kW. These drive day cost — not the building physics.",
    },
    TutorialStep {
        title: "Pick a day",
        blurb: "Choose month, day-of-year, and weekend. The rest of the tutorial uses this screening day.",
    },
    TutorialStep {
        title: "Baseline day",
        blurb: "One peak kW and one daily kWh for the reference day. Report magnitude ± nothing yet — this is a point estimate from the walk.",
    },
    TutorialStep {
        title: "DSM strategy",
        blurb: "Pick a named schedule strategy. This is enumeration screening, not an optimized setpoint search.",
    },
    TutorialStep {
        title: "Engineering check",
        blurb: "Nearest historical day + EnergyPlus delta is an engineering benchmark (not a trained ML score). Review peak, kWh, and out-of-distribution flag.",
    },
    TutorialStep {
        title: "Day cost",
        blurb: "Day total = energy $ + demand $. Treat as a screening estimate under the tariff above — not a settled utility bill.",
    },
    TutorialStep {
        title: "SIM",
        blurb: "Baseline vs strategy kW on one chart. If fit screens fail, do not read the gap as verified savings.",
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
        "baseline" => "Occupied setpoints all day — reference shape, not a savings case.",
        "stagger_preheat" => "Staggered zone preheat before occupancy to blunt the morning peak.",
        "flat_24_7" => "All zones heat all day — compare arm / upper-bound peak shape.",
        "deep_setback" => "Deep unoccupied setback; recovery can rebound into a sharp peak.",
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
        assert_eq!(STEPS.len(), STEP_COUNT as usize);
        assert_eq!(step_content(10).title, "SIM");
        assert_eq!(AppMode::TUTORIAL_SIM, STEP_COUNT);
        assert_eq!(AppMode::TUTORIAL_LAST, STEP_COUNT);
        assert_eq!(step_content(AppMode::TUTORIAL_LAST).title, "SIM");
    }

    #[test]
    fn step_content_clamps() {
        assert_eq!(step_content(0).title, step_content(1).title);
        assert_eq!(step_content(99).title, "SIM");
        assert_eq!(step_content(1).title, "Welcome");
    }

    #[test]
    fn blurbs_avoid_status_jargon() {
        for s in &STEPS {
            let low = s.blurb.to_ascii_lowercase();
            assert!(!low.contains("diagnostic_only"), "{}", s.title);
            assert!(!low.contains("blocked"), "{}", s.title);
            assert!(!low.contains("no-go"), "{}", s.title);
        }
    }
}
