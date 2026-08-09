//! Top-level app modes and workspace folders.

/// Workspace folder shown one-at-a-time under Workspace mode.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum WorkspaceFolder {
    Site,
    Tariff,
    DayWeather,
    Strategies,
    Validation,
    SimLab,
    Annual,
}

impl WorkspaceFolder {
    pub const ALL: [WorkspaceFolder; 7] = [
        WorkspaceFolder::Site,
        WorkspaceFolder::Tariff,
        WorkspaceFolder::DayWeather,
        WorkspaceFolder::Strategies,
        WorkspaceFolder::Validation,
        WorkspaceFolder::SimLab,
        WorkspaceFolder::Annual,
    ];

    pub fn label(self) -> &'static str {
        match self {
            WorkspaceFolder::Site => "Site & models",
            WorkspaceFolder::Tariff => "Tariff",
            WorkspaceFolder::DayWeather => "Day & weather",
            WorkspaceFolder::Strategies => "Strategies",
            WorkspaceFolder::Validation => "Validation",
            WorkspaceFolder::SimLab => "SIM Lab",
            WorkspaceFolder::Annual => "Annual",
        }
    }
}

/// Top-level navigation mode.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum AppMode {
    Welcome,
    Tutorial { step: u8 },
    Workspace { folder: WorkspaceFolder },
}

impl AppMode {
    pub const TUTORIAL_FIRST: u8 = 1;
    pub const TUTORIAL_LAST: u8 = 10;
    pub const TUTORIAL_SIM: u8 = 10;

    pub fn welcome() -> Self {
        AppMode::Welcome
    }

    pub fn tutorial_start() -> Self {
        AppMode::Tutorial {
            step: Self::TUTORIAL_FIRST,
        }
    }

    pub fn workspace_default() -> Self {
        AppMode::Workspace {
            folder: WorkspaceFolder::SimLab,
        }
    }

    pub fn mode_label(self) -> &'static str {
        match self {
            AppMode::Welcome => "Welcome",
            AppMode::Tutorial { .. } => "Tutorial",
            AppMode::Workspace { .. } => "Workspace",
        }
    }

    pub fn tutorial_step(self) -> Option<u8> {
        match self {
            AppMode::Tutorial { step } => Some(step),
            _ => None,
        }
    }

    /// Advance tutorial one step (clamped at last).
    pub fn next_tutorial(self) -> Self {
        match self {
            AppMode::Tutorial { step } => AppMode::Tutorial {
                step: step.saturating_add(1).min(Self::TUTORIAL_LAST),
            },
            other => other,
        }
    }

    /// Go back one tutorial step (clamped at first).
    pub fn back_tutorial(self) -> Self {
        match self {
            AppMode::Tutorial { step } => AppMode::Tutorial {
                step: step.saturating_sub(1).max(Self::TUTORIAL_FIRST),
            },
            other => other,
        }
    }

    /// Jump to SIM (tutorial step 10).
    pub fn skip_to_sim(self) -> Self {
        AppMode::Tutorial {
            step: Self::TUTORIAL_SIM,
        }
    }

    pub fn exit_to_workspace(self) -> Self {
        Self::workspace_default()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn tutorial_has_exactly_ten_steps_last_is_sim() {
        assert_eq!(AppMode::TUTORIAL_FIRST, 1);
        assert_eq!(AppMode::TUTORIAL_LAST, 10);
        assert_eq!(AppMode::TUTORIAL_SIM, 10);
        assert_eq!(AppMode::TUTORIAL_LAST - AppMode::TUTORIAL_FIRST + 1, 10);
        let sim = AppMode::Tutorial {
            step: AppMode::TUTORIAL_SIM,
        };
        assert_eq!(sim.tutorial_step(), Some(10));
    }

    #[test]
    fn next_back_bounds() {
        let mut m = AppMode::tutorial_start();
        assert_eq!(m.tutorial_step(), Some(1));
        m = m.back_tutorial();
        assert_eq!(m.tutorial_step(), Some(1), "back at first stays at 1");
        for expected in 2..=10 {
            m = m.next_tutorial();
            assert_eq!(m.tutorial_step(), Some(expected));
        }
        m = m.next_tutorial();
        assert_eq!(m.tutorial_step(), Some(10), "next at last stays at 10");
        m = m.back_tutorial();
        assert_eq!(m.tutorial_step(), Some(9));
    }

    #[test]
    fn skip_to_sim_jumps_to_step_ten() {
        let m = AppMode::Tutorial { step: 3 }.skip_to_sim();
        assert_eq!(m.tutorial_step(), Some(10));
        assert_eq!(AppMode::TUTORIAL_SIM, 10);
    }

    #[test]
    fn mode_labels() {
        assert_eq!(AppMode::Welcome.mode_label(), "Welcome");
        assert_eq!(
            AppMode::Tutorial { step: 1 }.mode_label(),
            "Tutorial"
        );
        assert_eq!(
            AppMode::Workspace {
                folder: WorkspaceFolder::Tariff
            }
            .mode_label(),
            "Workspace"
        );
        assert_eq!(WorkspaceFolder::SimLab.label(), "SIM Lab");
    }
}
