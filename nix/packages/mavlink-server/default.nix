{
  lib,
  rustPlatform,
  rustc,
  cargo,
  binaryen,
  cmake,
  fetchFromGitHub,
  git,
  gzip,
  lld,
  pkg-config,
  openssl,
  stdenv,
  trunk,
  wasm-bindgen-cli_0_2_100,
}:
let
  version = "0.11.1";

  src = fetchFromGitHub {
    owner = "bluerobotics";
    repo = "mavlink-server";
    tag = version;
    hash = "sha256-BOvG1DWpzq3C208Cuwq6+OgQaZsoRsVEpJWpLLcU0YI=";
  };

  # build.rs drives trunk, which installs toolchains through rustup and downloads
  # wasm-bindgen; neither works in the sandbox. Built here and staged below.
  frontend = stdenv.mkDerivation {
    pname = "mavlink-server-frontend";
    inherit version src;

    cargoDeps = rustPlatform.importCargoLock {
      lockFile = "${src}/src/webpage/Cargo.lock";
      outputHashes = {
        "egui_autocomplete-9.0.0" = "sha256-zhqI9GUui2Efxr8dHyttAPdMFPNuINhiDTdyP+PDuMU=";
      };
    };

    # The webpage is its own cargo workspace; the hook defaults to the root lockfile.
    cargoRoot = "src/webpage";

    nativeBuildInputs = [
      binaryen
      cargo
      lld
      rustc
      rustPlatform.cargoSetupHook
      trunk
      wasm-bindgen-cli_0_2_100
    ];

    # rustc ships the wasm32 std; only the linker is missing.
    CARGO_BUILD_TARGET = "wasm32-unknown-unknown";
    CARGO_HOME = "/build/cargo-home";

    buildPhase = ''
      runHook preBuild

      cd src/webpage
      trunk build --release --offline --locked

      runHook postBuild
    '';

    installPhase = ''
      runHook preInstall

      mkdir -p $out
      cp -R dist/. $out/

      # Upstream serves the .gz copies, not the originals.
      find $out -type f ! -name '*.gz' -exec gzip -9 {} +

      runHook postInstall
    '';
  };
in
rustPlatform.buildRustPackage (finalAttrs: {
  pname = "mavlink-server";
  inherit version src;

  cargoLock = {
    lockFile = ./Cargo.lock;
    outputHashes = {
      "include_dir-0.7.4" = "sha256-nuxK7up+JrSWWAwsbEM9wt+usDR65/p69ZQa/8uSccw=";
      "include_dir_macros-0.7.4" = "sha256-nuxK7up+JrSWWAwsbEM9wt+usDR65/p69ZQa/8uSccw=";
      "mavlink-codec-0.1.0" = "sha256-Z33CEKNSc9ven/7OUe4Ykiom+BaMjCweaTrNvgcWLC8=";
    };
  };

  nativeBuildInputs = [
    cmake
    git
    gzip
    pkg-config
  ];

  buildInputs = [ openssl ];

  # Skips build.rs's trunk run
  env.SKIP_FRONTEND = "1";

  # include_dir is vendored as a flat directory, so its `include_str!("../../README.md")`,
  # which resolves inside the upstream workspace, points one level above the vendor
  # root. Only used for a doc attribute, so an empty placeholder is enough.
  postPatch = ''
    touch "$NIX_BUILD_TOP/cargo-vendor-dir/README.md"

    mkdir -p src/webpage/dist
    cp -R ${frontend}/. src/webpage/dist/
    chmod -R u+w src/webpage/dist
  '';

  # The TCP integration tests share a process-global driver registry and register
  # the same endpoint uuids, so they must not run concurrently.
  checkFlags = [
    "--"
    "--test-threads=1"
  ];

  nativeInstallCheckInputs = [ ];

  meta = {
    description = "MAVLink server with a web interface";
    homepage = "https://github.com/bluerobotics/mavlink-server";
    license = lib.licenses.mit;
    mainProgram = "mavlink-server";
    platforms = lib.platforms.linux;
  };
})
