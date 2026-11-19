{
  lib,
  rustPlatform,
  fetchFromGitHub,
}:
rustPlatform.buildRustPackage (finalAttrs: {
  pname = "machineid-cli";
  version = "0.2.3";

  src = fetchFromGitHub {
    owner = "patrickelectric";
    repo = "machineid-cli";
    tag = finalAttrs.version;
    hash = "sha256-EMC7rzyJ77ifxChLvPFY7qoqJ7FC1wxBtI7MbagMBqw=";
  };

  cargoLock = {
    lockFile = ./Cargo.lock;
    outputHashes = {
      "machineid-rs-1.2.4" = "sha256-g2cpC/KcwwMQM9I3JxLoVEgn9I/FYz9xXum7iO+fgHY=";
    };
  };

  # Upstream ships no Cargo.lock, so the pinned one above has to be placed
  # before cargo's vendoring check runs.
  postPatch = ''
    cp ${./Cargo.lock} Cargo.lock
  '';

  meta = {
    description = "Generate a machine identifier from hardware properties";
    homepage = "https://github.com/patrickelectric/machineid-cli";
    license = lib.licenses.mit;
    mainProgram = "machineid-cli";
    platforms = lib.platforms.linux;
  };
})
