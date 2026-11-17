//! Release discovery from a published manifest.
//!
//! The daemon only lists what the manifest names; an update is always a user
//! action.

use anyhow::Context;
use serde::{Deserialize, Serialize};
use utoipa::ToSchema;

/// One published build. `toplevel` is the store path the publisher put in the
/// binary cache.
#[derive(Deserialize, Serialize, Clone, ToSchema)]
pub(crate) struct Release {
    pub(crate) board: String,
    #[serde(default)]
    pub(crate) channel: String,
    pub(crate) version: String,
    #[serde(default)]
    pub(crate) revision: String,
    pub(crate) toplevel: String,
    #[serde(default)]
    pub(crate) published: Option<jiff::Timestamp>,
}

#[derive(Deserialize)]
pub(crate) struct Manifest {
    #[serde(default)]
    releases: Vec<Release>,
}

/// Releases published for `board`, newest first. Without a manifest URL there
/// is nothing to list.
pub(crate) async fn releases(
    manifest_url: Option<&str>,
    board: &str,
) -> anyhow::Result<Vec<Release>> {
    let Some(url) = manifest_url else {
        return Ok(Vec::new());
    };

    let response = reqwest::get(url)
        .await
        .with_context(|| format!("cannot reach the release manifest at {url}"))?
        .error_for_status()
        .with_context(|| format!("the release manifest at {url} rejected the request"))?;

    let mut manifest: Manifest = response
        .json()
        .await
        .context("the release manifest is not valid JSON")?;

    let mut releases: Vec<Release> = manifest
        .releases
        .drain(..)
        .filter(|release| release.board == board)
        .collect();
    releases.sort_by(|a, b| {
        b.published
            .cmp(&a.published)
            .then(b.version.cmp(&a.version))
    });
    Ok(releases)
}
