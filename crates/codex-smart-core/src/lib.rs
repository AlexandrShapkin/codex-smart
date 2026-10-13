//! Thin launcher primitives. Discovery never executes discovered programs.
pub mod capability;
pub mod config;
pub mod doctor;
pub mod migration;
pub mod playbook;
pub mod process;
pub mod routing;
pub mod tool_lock;
pub mod version;
pub mod workflow;
pub const VERSION: &str = env!("CARGO_PKG_VERSION");
