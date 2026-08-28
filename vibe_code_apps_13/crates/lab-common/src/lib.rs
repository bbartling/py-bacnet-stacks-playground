//! Shared, dependency-free validation for the checkpoint 13 lab.

use core::fmt;
use core::str::FromStr;

/// Baud rates accepted by every serial-facing CLI and configuration file.
#[derive(Debug, Default, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash)]
#[repr(u32)]
pub enum BaudRate {
    B9600 = 9_600,
    B19200 = 19_200,
    #[default]
    B38400 = 38_400,
    B57600 = 57_600,
    B76800 = 76_800,
    B115200 = 115_200,
}

impl BaudRate {
    pub const ALL: [Self; 6] = [
        Self::B9600,
        Self::B19200,
        Self::B38400,
        Self::B57600,
        Self::B76800,
        Self::B115200,
    ];

    #[must_use]
    pub const fn as_u32(self) -> u32 {
        self as u32
    }
}

impl fmt::Display for BaudRate {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        self.as_u32().fmt(formatter)
    }
}

impl TryFrom<u32> for BaudRate {
    type Error = ConfigError;

    fn try_from(value: u32) -> Result<Self, Self::Error> {
        match value {
            9_600 => Ok(Self::B9600),
            19_200 => Ok(Self::B19200),
            38_400 => Ok(Self::B38400),
            57_600 => Ok(Self::B57600),
            76_800 => Ok(Self::B76800),
            115_200 => Ok(Self::B115200),
            _ => Err(ConfigError::UnsupportedBaud(value)),
        }
    }
}

impl FromStr for BaudRate {
    type Err = ConfigError;

    fn from_str(value: &str) -> Result<Self, Self::Err> {
        value
            .parse::<u32>()
            .map_err(|_| ConfigError::InvalidInteger(value.to_owned()))?
            .try_into()
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct MstpMasterConfig {
    pub serial_path: String,
    pub baud: BaudRate,
    pub mac: u8,
    pub max_master: u8,
    pub max_info_frames: u8,
}

impl MstpMasterConfig {
    /// Validates the serial path and MS/TP master configuration relationships.
    ///
    /// # Errors
    ///
    /// Returns [`ConfigError`] when the serial path is empty, `Max_Master` is
    /// outside the `BACnet` range, the local MAC exceeds `Max_Master`, or
    /// `Max_Info_Frames` is zero.
    pub fn validate(&self) -> Result<(), ConfigError> {
        if self.serial_path.trim().is_empty() {
            return Err(ConfigError::EmptySerialPath);
        }
        if self.max_master > 127 {
            return Err(ConfigError::MaxMasterOutOfRange(self.max_master));
        }
        if self.mac > self.max_master {
            return Err(ConfigError::MacExceedsMaxMaster {
                mac: self.mac,
                max_master: self.max_master,
            });
        }
        if self.max_info_frames == 0 {
            return Err(ConfigError::ZeroMaxInfoFrames);
        }
        Ok(())
    }
}

/// Validates that the B/IP and MS/TP network numbers are routable and distinct.
///
/// # Errors
///
/// Returns [`ConfigError`] when either network is reserved (`0` or `65535`) or
/// when both router ports are configured with the same network number.
pub fn validate_router_networks(bip_network: u16, mstp_network: u16) -> Result<(), ConfigError> {
    for network in [bip_network, mstp_network] {
        if network == 0 || network == u16::MAX {
            return Err(ConfigError::InvalidNetworkNumber(network));
        }
    }
    if bip_network == mstp_network {
        return Err(ConfigError::DuplicateNetworkNumber(bip_network));
    }
    Ok(())
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ConfigError {
    UnsupportedBaud(u32),
    InvalidInteger(String),
    EmptySerialPath,
    MaxMasterOutOfRange(u8),
    MacExceedsMaxMaster { mac: u8, max_master: u8 },
    ZeroMaxInfoFrames,
    InvalidNetworkNumber(u16),
    DuplicateNetworkNumber(u16),
}

impl fmt::Display for ConfigError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::UnsupportedBaud(value) => write!(
                formatter,
                "unsupported baud {value}; expected 9600, 19200, 38400, 57600, 76800, or 115200"
            ),
            Self::InvalidInteger(value) => write!(formatter, "invalid integer: {value}"),
            Self::EmptySerialPath => formatter.write_str("serial path must not be empty"),
            Self::MaxMasterOutOfRange(value) => {
                write!(formatter, "Max_Master {value} exceeds 127")
            }
            Self::MacExceedsMaxMaster { mac, max_master } => {
                write!(
                    formatter,
                    "master MAC {mac} exceeds Max_Master {max_master}"
                )
            }
            Self::ZeroMaxInfoFrames => formatter.write_str("Max_Info_Frames must be at least 1"),
            Self::InvalidNetworkNumber(value) => {
                write!(
                    formatter,
                    "network number {value} is not a routable network"
                )
            }
            Self::DuplicateNetworkNumber(value) => {
                write!(formatter, "B/IP and MS/TP cannot both use network {value}")
            }
        }
    }
}

impl std::error::Error for ConfigError {}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn default_baud_is_38400() {
        assert_eq!(BaudRate::default(), BaudRate::B38400);
    }

    #[test]
    fn accepts_every_policy_baud() {
        for expected in BaudRate::ALL {
            assert_eq!(expected.to_string().parse(), Ok(expected));
            assert_eq!(BaudRate::try_from(expected.as_u32()), Ok(expected));
        }
    }

    #[test]
    fn rejects_unapproved_baud() {
        assert_eq!(
            BaudRate::try_from(9_601),
            Err(ConfigError::UnsupportedBaud(9_601))
        );
    }

    #[test]
    fn validates_mstp_master_relationships() {
        let valid = MstpMasterConfig {
            serial_path: "/dev/serial/by-id/adapter".to_owned(),
            baud: BaudRate::default(),
            mac: 1,
            max_master: 10,
            max_info_frames: 1,
        };
        assert_eq!(valid.validate(), Ok(()));

        let invalid = MstpMasterConfig { mac: 11, ..valid };
        assert_eq!(
            invalid.validate(),
            Err(ConfigError::MacExceedsMaxMaster {
                mac: 11,
                max_master: 10
            })
        );
    }

    #[test]
    fn router_networks_must_be_distinct_and_routable() {
        assert_eq!(validate_router_networks(100, 2001), Ok(()));
        assert_eq!(
            validate_router_networks(100, 100),
            Err(ConfigError::DuplicateNetworkNumber(100))
        );
        assert_eq!(
            validate_router_networks(0, 2001),
            Err(ConfigError::InvalidNetworkNumber(0))
        );
        assert_eq!(
            validate_router_networks(100, u16::MAX),
            Err(ConfigError::InvalidNetworkNumber(u16::MAX))
        );
    }
}
