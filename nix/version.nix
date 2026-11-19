# The BlueOS version metadata, shared by blueos-core and blueos-frontend. These
# are the values that are not properties of the commit.
{
  # A literal so the version is readable from the closure, not only from git. A
  # flake cannot see its own tags, so this cannot be derived from `git
  # describe`. Bump it as part of cutting a release.
  version = "1.5.0-dev";

  # Reported to Sentry and to the version chooser. `dev` keeps these builds out
  # of Sentry, which only accepts a `<x.y.z>-<commits>-g<hash>` describe string.
  # Available options:
  # - stable
  # - beta
  # - dev
  channel = "dev";
}
