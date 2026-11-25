# The BlueOS containers a guest image ships.
#
# Both archives are fixed-output derivations, so the tag, the digest and the
# hash together name one published image even when the tag itself moves. Moving
# to another image means bumping all three; running the build with a stale hash
# reports the new one.
#
#   nix build --impure --expr 'let f = builtins.getFlake (toString ./.); pkgs =
#     f.inputs.nixpkgs.legacyPackages.aarch64-linux; in pkgs.dockerTools.pullImage
#     { imageName = "bluerobotics/blueos-core"; finalImageTag = "master";
#       imageDigest = "sha256:..."; arch = "arm64"; os = "linux";
#       outputHash = pkgs.lib.fakeHash; outputHashAlgo = "sha256"; }'
#
# The digest is the one the tag resolves to in the multi-arch manifest; the
# per-architecture digests listed inside it name different objects. Only arm64
# is fetched, since the guest images are for Pis.
#
# The tag is a single attribute because the two images of a release have to
# agree: bootstrap starts `blueos-core:<tag>` and the version chooser switches
# both together.
#
# `master` rather than a release: no published tag carries
# 5bcc07cba (navigator: accept NixOS serials on RPi4), and without it a Pi 4
# Navigator reports the Bullseye ttyAMA1-3, which do not exist on the NixOS
# host, so every firmware install fails validation.
#
# It also has to carry #4830 (0c6cf7044). The dns patch decided whether the
# host already had its resolv conf bind by requiring a link count above one,
# which a managed symlink does not have, so it reapplied on every boot and made
# each boot happen twice. Move this to a tag once one contains both.
{
  dockerTools,
  lib,
}:
let
  tag = "master";

  pull = imageName: imageDigest: outputHash: {
    image = "${imageName}:${tag}";
    archive = dockerTools.pullImage {
      inherit imageName imageDigest outputHash;
      finalImageTag = tag;
      outputHashAlgo = "sha256";
      os = "linux";
      arch = "arm64";
    };
  };

  core =
    pull "bluerobotics/blueos-core"
      "sha256:65c09a35d7fdd516065336eafe74fc27db7d732629dbcf00a460546230c0c3bc"
      "sha256-PJO1clwzgw5JxnIbGo6AFcK1VaIfFqSwJ4o6mvecBHc=";

  bootstrap =
    pull "bluerobotics/blueos-bootstrap"
      "sha256:4cb61642f5bbb1ba82cd5d62461c5e94493dd5e7da4a2b1a603a4e875f1f703c"
      "sha256-v4pP+WdjHhZaJQ15iSFID+bZlkbyCccdMkBHSSB8/t0=";
in
{
  # A single attribute, because the two images of a release have to agree:
  # bootstrap starts `blueos-core:<tag>` and the version chooser switches both
  # together.
  inherit
    tag
    core
    bootstrap
    ;

  # What an offline guest ships: the core, and the bootstrap that starts it
  images = [
    core
    bootstrap
  ];

  meta = {
    description = "BlueOS ${tag} core and bootstrap images, for offline installation";
    homepage = "https://github.com/BlueRobotics/BlueOS";
    license = lib.licenses.agpl3Plus;
    platforms = [ "aarch64-linux" ];
  };
}
