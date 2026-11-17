{
  fetchFromGitHub,
  fetchurl,
  lib,
  openssl,
  pkg-config,
  rustPlatform,
  udev,
}:
let
  version = "0.9.5";

  # build.rs downloads Vue at build time, which the sandbox forbids; the patch
  # drops the download and this file is supplied instead.
  vue = fetchurl {
    url = "https://unpkg.com/vue@3.0.5/dist/vue.global.js";
    hash = "sha256-Wr5PnkpmZ3oQFRZLfDrI6fsePSMak5h8rW2rqq+mdWg=";
  };
in
rustPlatform.buildRustPackage {
  pname = "linux2rest";
  inherit version;

  src = fetchFromGitHub {
    owner = "patrickelectric";
    repo = "linux2rest";
    tag = "v${version}";
    hash = "sha256-D2N7pyQEgqsZuaoMpqJSXJv2eiqZ7wuCgvWVV5BiqC8=";
  };

  cargoHash = "sha256-stWFmQK9Wg3B1ZBp/JpIJHexoPUiv6e8hZY6jj3SkGU=";

  nativeBuildInputs = [ pkg-config ];

  patches = [
    ./no-download.patch
    ./journal-forward-debug.patch
    ./journal-buffer-cap.patch
    ./serial-by-path-missing.patch
    ./throttled-via-vcgencmd.patch
  ];

  postPatch = ''
    cp ${./Cargo.lock} Cargo.lock
    cp ${vue} src/html/vue.js
  '';

  buildInputs = [
    openssl
    udev
  ];

  # Without this the platform endpoint is compiled out and answers 500.
  cargoBuildFlags = [ "--features=raspberry" ];

  meta = {
    description = "REST API exposing Linux system information";
    homepage = "https://github.com/patrickelectric/linux2rest";
    license = lib.licenses.mit;
    mainProgram = "linux2rest";
    platforms = lib.platforms.linux;
  };
}
