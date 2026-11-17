{
  fetchFromGitHub,
  gst_all_1,
  lib,
  pkg-config,
  rustPlatform,
  zstd,
}:
rustPlatform.buildRustPackage (finalAttrs: {
  pname = "mcap-foxglove-video-extract";
  version = "0.1.3";

  src = fetchFromGitHub {
    owner = "bluerobotics";
    repo = "mcap-foxglove-video-extract";
    tag = finalAttrs.version;
    hash = "sha256-J3yO2PZauQ6YcNuMJFx0PIK7R/C+A88n/3zc8/aTn6I=";
  };

  cargoLock.lockFile = ./Cargo.lock;

  # Upstream does not commit a lockfile, so the one the vendor directory was
  # built from has to be put back for the consistency check.
  postPatch = ''
    cp ${./Cargo.lock} Cargo.lock
  '';

  nativeBuildInputs = [ pkg-config ];

  buildInputs = [
    gst_all_1.gstreamer
    gst_all_1.gst-plugins-base
    zstd
  ];

  meta = {
    description = "Extracts video streams from MCAP recordings";
    homepage = "https://github.com/bluerobotics/mcap-foxglove-video-extract";
    license = lib.licenses.mit;
    mainProgram = "mcap-foxglove-video-extract";
    platforms = lib.platforms.linux;
  };
})
