//! Startup configuration.
//!
//! Every setting is a flag with an environment variable behind it, so the unit
//! file can configure the daemon and an operator can still override it.

use std::net::SocketAddr;

use clap::Parser;

#[derive(Debug, Parser)]
#[command(name = "blueos-updates", version, about)]
pub(crate) struct Config {
    /// Board identifier, which selects the releases the manifest offers. It has
    /// to match the `board` field the publisher writes.
    #[arg(long, env = "BLUEOS_BOARD", default_value = "unknown")]
    pub(crate) board: String,

    #[arg(long, env = "BLUEOS_UPDATES_ADDR", default_value = "0.0.0.0:8081")]
    pub(crate) addr: SocketAddr,

    /// Where the list of published releases is read from. Without one, only the
    /// generations already on the card are offered.
    #[arg(long, env = "BLUEOS_UPDATES_MANIFEST")]
    pub(crate) manifest_url: Option<String>,
}

impl Config {
    pub(crate) fn from_env() -> Self {
        Self::parse()
    }
}
