{
  lib,
  rustPlatform,
  fetchFromGitHub,
  pkg-config,
  udev,
}:
rustPlatform.buildRustPackage (finalAttrs: {
  pname = "bridges";
  version = "0.10.3";

  src = fetchFromGitHub {
    owner = "patrickelectric";
    repo = "bridges";
    tag = finalAttrs.version;
    hash = "sha256-LkddoUuihKvihEauHISQiSEQ2jvzZXlDnSyf8CcGyJ0=";
  };

  cargoLock = {
    lockFile = ./Cargo.lock;
  };

  # Upstream ships no Cargo.lock, so the pinned one above has to be placed
  # before cargo's vendoring check runs.
  postPatch = ''
    cp ${./Cargo.lock} Cargo.lock
  '';

  nativeBuildInputs = [ pkg-config ];

  buildInputs = [ udev ];

  meta = {
    description = "Simple UDP-to-serial bridge";
    homepage = "https://github.com/patrickelectric/bridges";
    license = lib.licenses.mit;
    mainProgram = "bridges";
    platforms = lib.platforms.linux;
  };
})
