//! NixOS generations of the system profile: what "a BlueOS version" means on
//! this system.

use std::fs;
use std::path::{Path, PathBuf};

use anyhow::Context;
use jiff::Timestamp;
use serde::{Deserialize, Serialize};
use utoipa::ToSchema;

pub(crate) const PROFILE_DIR: &str = "/nix/var/nix/profiles";
pub(crate) const SYSTEM_PROFILE: &str = "/nix/var/nix/profiles/system";
pub(crate) const CURRENT_SYSTEM: &str = "/run/current-system";
pub(crate) const BOOTED_SYSTEM: &str = "/run/booted-system";
pub(crate) const KNOWN_GOOD_ROOT: &str = "/nix/var/nix/gcroots/blueos/known-good";

/// `etc/blueos/release.json`, written by modules/blueos/version.nix. Each
/// generation carries its own copy, so no Nix evaluation is needed to identify
/// it.
#[derive(Deserialize, Clone)]
pub(crate) struct Release {
    pub(crate) version: String,
    #[serde(default)]
    pub(crate) revision: String,
    #[serde(default)]
    pub(crate) channel: String,
}

/// A generation as the API reports it.
#[derive(Clone, Serialize, ToSchema)]
pub(crate) struct GenerationInfo {
    /// Generation number from `system-<n>-link`.
    pub(crate) generation: u32,
    /// Store path of the system closure. Two builds of one version differ here.
    pub(crate) toplevel: String,
    pub(crate) version: String,
    pub(crate) channel: String,
    pub(crate) revision: String,
    /// When the generation link was created.
    pub(crate) created: Timestamp,
    /// Whether this is what the system is running right now.
    pub(crate) current: bool,
    /// Whether the rollback machinery recorded this generation as healthy.
    pub(crate) known_good: bool,
    /// Whether the kernel and initrd match what the machine booted, which is
    /// what decides if activating this generation needs a reboot.
    pub(crate) reboot_required: bool,
}

#[derive(Clone)]
pub(crate) struct Generation {
    pub(crate) id: u32,
    pub(crate) toplevel: PathBuf,
    pub(crate) release: Option<Release>,
    pub(crate) created: Timestamp,
}

impl Generation {
    pub(crate) fn version(&self) -> String {
        self.release
            .as_ref()
            .map(|release| release.version.clone())
            .unwrap_or_else(|| "unknown".to_string())
    }
}

pub(crate) fn read_release(toplevel: &Path) -> Option<Release> {
    let raw = fs::read_to_string(toplevel.join("etc/blueos/release.json")).ok()?;
    serde_json::from_str(&raw).ok()
}

/// The link's own mtime, which is when the generation was created. The store
/// path's mtime is normalised to the epoch, so following the symlink would date
/// every generation to 1970.
fn created(path: &Path) -> anyhow::Result<Timestamp> {
    let meta = fs::symlink_metadata(path).context("generation link is unreadable")?;
    let modified = meta.modified().context("generation link has no mtime")?;
    Ok(Timestamp::try_from(modified)?)
}

fn read_generation(id: u32, link: &Path) -> anyhow::Result<Generation> {
    let toplevel = fs::canonicalize(link).context("generation link is broken")?;
    Ok(Generation {
        id,
        release: read_release(&toplevel),
        created: created(link)?,
        toplevel,
    })
}

/// Every generation on the profile, newest first. Reading the links rather than
/// asking nix-env avoids taking the profile lock.
pub(crate) fn all() -> anyhow::Result<Vec<Generation>> {
    let entries = fs::read_dir(PROFILE_DIR).context("cannot read the profile directory")?;

    let mut links: Vec<(u32, PathBuf)> = entries
        .filter_map(Result::ok)
        .filter_map(|entry| {
            let name = entry.file_name();
            let name = name.to_str()?;
            let id = name.strip_prefix("system-")?.strip_suffix("-link")?;
            Some((id.parse::<u32>().ok()?, entry.path()))
        })
        .collect();
    links.sort_by_key(|(id, _)| std::cmp::Reverse(*id));

    Ok(links
        .into_iter()
        .filter_map(|(id, link)| read_generation(id, &link).ok())
        .collect())
}

pub(crate) fn find(id: u32) -> Option<Generation> {
    all().ok()?.into_iter().find(|item| item.id == id)
}

pub(crate) fn current_toplevel() -> Option<PathBuf> {
    fs::canonicalize(CURRENT_SYSTEM).ok()
}

/// What the profile points at. It is the running system except between an
/// activation that needs a reboot and the reboot itself.
pub(crate) fn profile_toplevel() -> Option<PathBuf> {
    fs::canonicalize(SYSTEM_PROFILE).ok()
}

pub(crate) fn known_good() -> Option<PathBuf> {
    fs::canonicalize(KNOWN_GOOD_ROOT).ok()
}

/// The one generation to present as the rollback target.
///
/// Several links can point at a single closure, so matching on the closure
/// alone badges every one of them. Exactly one is chosen instead: the running
/// generation when it is the recorded one, otherwise the newest that is.
pub(crate) fn known_good_generation() -> Option<u32> {
    let target = known_good()?;
    let generations = all().ok()?;

    let running = current_toplevel();
    generations
        .iter()
        .find(|generation| running.as_deref() == Some(generation.toplevel.as_path()))
        .filter(|generation| generation.toplevel == target)
        .or_else(|| {
            generations
                .iter()
                .find(|generation| generation.toplevel == target)
        })
        .map(|generation| generation.id)
}

/// Whether activating `candidate` needs a reboot before it takes effect. Mirrors
/// what nixos-rebuild compares, plus the init interface version that
/// `switch-to-configuration` refuses to activate across.
pub(crate) fn reboot_required(candidate: &Path) -> bool {
    for file in ["kernel", "initrd", "kernel-modules"] {
        let new = fs::canonicalize(candidate.join(file));
        let booted = fs::canonicalize(Path::new(BOOTED_SYSTEM).join(file));
        if let (Ok(new), Ok(booted)) = (new, booted)
            && new != booted
        {
            return true;
        }
    }

    let new_interface = fs::read_to_string(candidate.join("init-interface-version"));
    let running_interface =
        fs::read_to_string(Path::new(CURRENT_SYSTEM).join("init-interface-version"));
    match (new_interface, running_interface) {
        (Ok(new), Ok(running)) => !new.is_empty() && new != running,
        _ => false,
    }
}

impl Generation {
    pub(crate) fn info(&self) -> GenerationInfo {
        self.info_with(known_good_generation())
    }

    /// `info` for the whole list at once, so one lookup decides the badge for
    /// every generation instead of rescanning the profile per row.
    pub(crate) fn info_with(&self, known_good: Option<u32>) -> GenerationInfo {
        let current = current_toplevel().as_deref() == Some(self.toplevel.as_path());
        GenerationInfo {
            generation: self.id,
            toplevel: self.toplevel.to_string_lossy().into_owned(),
            version: self.version(),
            channel: self
                .release
                .as_ref()
                .map(|release| release.channel.clone())
                .unwrap_or_default(),
            revision: self
                .release
                .as_ref()
                .map(|release| release.revision.clone())
                .unwrap_or_default(),
            created: self.created,
            current,
            known_good: known_good == Some(self.id),
            reboot_required: reboot_required(&self.toplevel),
        }
    }
}
