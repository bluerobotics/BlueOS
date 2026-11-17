//! Switching the running system to another generation, and fetching published
//! closures.
//!
//! Both go through the commands `nixos-rebuild` uses, so the rollback
//! pre-switch check arms itself as it does for a manual deploy.

use std::path::{Path, PathBuf};
use std::process::ExitStatus;

use anyhow::{Context, bail};
use tokio::process::Command;

/// Where the detached switch writes its output. Next to the rollback state
/// file, so both halves of an update are found in one place.
pub(crate) const SWITCH_LOG: &str = "/var/lib/blueos/updates/last-switch.log";

pub(crate) struct Activation {
    pub(crate) toplevel: String,
    /// True when the generation cannot take effect until the machine reboots.
    pub(crate) reboot_required: bool,
    /// The file the detached switch writes its progress and errors to.
    pub(crate) log: String,
}

/// Which profile link the switch starts from.
///
/// `nix-env --set` appends a generation whenever the store path differs from
/// the profile's current target, so pointing the profile at a build that is
/// already there would duplicate it. Going back to an installed version is the
/// common case for a vehicle, so it switches the existing link instead.
pub(crate) enum Selection {
    /// A generation link that already exists, reused rather than duplicated.
    Generation(u32),
    /// A store path with no generation link yet, which gains one.
    Store,
}

/// Point the system profile at `toplevel` and start activating it.
///
/// The order is the one nixos-rebuild uses: set the profile, then let the
/// generation activate itself. The rollback check compares the incoming
/// toplevel against the *running* system rather than the profile, so it still
/// arms despite the profile having already moved.
///
/// The switch is started, not awaited: it restarts every BlueOS unit, this
/// daemon included, so waiting could only end in a dead client. The caller gets
/// `Activation` once the switch is queued and follows the outcome through the
/// status endpoint.
pub(crate) async fn activate(
    toplevel: &Path,
    selection: Selection,
    mode: &str,
) -> anyhow::Result<Activation> {
    let (argument, value) = match selection {
        Selection::Generation(number) => ("--switch-generation", number.to_string()),
        Selection::Store => ("--set", toplevel.to_string_lossy().into_owned()),
    };

    let (status, stderr) = run(
        Command::new("nix-env").args([
            "--profile",
            crate::generations::SYSTEM_PROFILE,
            argument,
            &value,
        ]),
        "nix-env",
    )
    .await?;
    if !status.success() {
        bail!(
            "nix-env could not point the system profile at {}: {}",
            toplevel.display(),
            detail(&stderr)
        );
    }

    start_switch(toplevel, mode).await?;

    // `boot` only installs the generation, so nothing takes effect until the
    // machine reboots, whatever the incoming kernel looks like. A `switch` only
    // needs one when the kernel, initrd or init interface differ.
    let reboot_required = mode == "boot" || crate::generations::reboot_required(toplevel);

    Ok(Activation {
        toplevel: toplevel.to_string_lossy().into_owned(),
        reboot_required,
        log: SWITCH_LOG.to_string(),
    })
}

/// Queue the generation's own `switch-to-configuration` in a transient unit and
/// return, leaving it to run on its own.
///
/// `--no-block` keeps the switch out of this process's cgroup and stops this
/// process from waiting on it, which is what lets the switch restart the daemon
/// that started it.
///
/// Output goes to a file rather than `--pipe`: `--pipe` hands the unit's
/// streams to this process, so this process dying would take the switch with it.
///
/// The PATH is forwarded explicitly: a transient unit otherwise starts with
/// systemd's default, which lacks coreutils, and the rollback pre-switch check
/// runs `readlink` before it does anything else.
async fn start_switch(toplevel: &Path, mode: &str) -> anyhow::Result<()> {
    let log = PathBuf::from(SWITCH_LOG);

    let output = Command::new("systemd-run")
        .args([
            "--quiet",
            "--no-block",
            "--collect",
            "--service-type=oneshot",
            // The switch restarts system units, so it must not be scoped to a
            // caller's session.
            "--system",
            "--description=BlueOS update activation",
            // A switch that hangs must not hold the machine hostage.
            "--property=TimeoutStartSec=15min",
            // Exit 100 means the generation is installed and needs a reboot,
            // which is a completed update rather than a failure.
            "--property=SuccessExitStatus=100",
        ])
        .arg(format!("--unit=blueos-activate-{}", unique_suffix()))
        .arg(format!(
            "--setenv=PATH={}",
            std::env::var("PATH").unwrap_or_else(|_| "/run/current-system/sw/bin".to_string())
        ))
        .arg(format!("--property=StandardOutput=file:{}", log.display()))
        // Truncates rather than appends, so the log always describes the
        // activation the status endpoint currently reports.
        .arg(format!("--property=StandardError=file:{}", log.display()))
        .arg(toplevel.join("bin/switch-to-configuration"))
        .arg(mode)
        .output()
        .await
        .context("systemd-run could not be started")?;

    if !output.status.success() {
        bail!(
            "the activation could not be started: {}",
            detail(&String::from_utf8_lossy(&output.stderr))
        );
    }

    Ok(())
}

/// A value that is unique per activation, so a queued switch is never mistaken
/// for one already running.
fn unique_suffix() -> String {
    format!(
        "{}-{}",
        std::process::id(),
        jiff::Timestamp::now().as_nanosecond()
    )
}

/// Substitute a closure from the binary cache: no Nix evaluation, just the store
/// path the caller already has.
pub(crate) async fn realise(toplevel: &str) -> anyhow::Result<()> {
    let (status, stderr) = run(
        Command::new("nix-store").args(["--realise", toplevel]),
        "nix-store",
    )
    .await?;

    if !status.success() {
        bail!(
            "{toplevel} is not available from the binary cache: {}",
            detail(&stderr)
        );
    }
    Ok(())
}

/// Drop a generation from the profile, which also deletes its store path if
/// nothing else refers to it. `nix-env` is the only writer of the profile, so
/// going through it keeps the numbering and the `system` link consistent.
pub(crate) async fn delete_generation(number: &str) -> anyhow::Result<()> {
    let (status, stderr) = run(
        Command::new("nix-env").args([
            "--profile",
            crate::generations::SYSTEM_PROFILE,
            "--delete-generations",
            number,
        ]),
        "nix-env",
    )
    .await?;

    if !status.success() {
        bail!(
            "nix-env could not delete generation {number}: {}",
            detail(&stderr)
        );
    }
    Ok(())
}

async fn run(command: &mut Command, name: &str) -> anyhow::Result<(ExitStatus, String)> {
    let output = command
        .output()
        .await
        .with_context(|| format!("{name} could not be started"))?;

    Ok((
        output.status,
        String::from_utf8_lossy(&output.stderr).into_owned(),
    ))
}

/// Nix's own error text, or a placeholder when it said nothing.
fn detail(stderr: &str) -> String {
    let trimmed = stderr.trim();
    if trimmed.is_empty() {
        "no output".to_string()
    } else {
        trimmed.to_string()
    }
}
