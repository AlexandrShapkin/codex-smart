//! Strict release versions: no untrusted suffixes are echoed in diagnostics.
use std::fmt;

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub struct Version {
    pub major: u32,
    pub minor: u32,
    pub patch: u32,
}
impl Version {
    pub const fn new(major: u32, minor: u32, patch: u32) -> Self {
        Self {
            major,
            minor,
            patch,
        }
    }
    pub fn parse(raw: &str) -> Option<Self> {
        if raw.len() > 32 {
            return None;
        }
        let mut parts = raw.split('.');
        fn component(raw: &str) -> Option<u32> {
            if raw.is_empty()
                || (raw.len() > 1 && raw.starts_with('0'))
                || !raw.bytes().all(|b| b.is_ascii_digit())
            {
                return None;
            }
            raw.parse().ok()
        }
        let version = Self::new(
            component(parts.next()?)?,
            component(parts.next()?)?,
            component(parts.next()?)?,
        );
        if parts.next().is_some() {
            return None;
        }
        Some(version)
    }
}
impl fmt::Display for Version {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}.{}.{}", self.major, self.minor, self.patch)
    }
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn strict_release_parsing_and_numeric_order() {
        assert_eq!(Version::parse("0.160.0"), Some(Version::new(0, 160, 0)));
        assert!(Version::new(1, 10, 0) > Version::new(1, 9, 99));
        for raw in [
            "v1.2.3",
            "01.2.3",
            "1.2",
            "1.2.3.4",
            "1.2.3-SECRET",
            "1.2.3+build",
            "1.2.-3",
            "1.2.4294967296",
            "1.2. 3",
        ] {
            assert_eq!(Version::parse(raw), None);
        }
    }
}
