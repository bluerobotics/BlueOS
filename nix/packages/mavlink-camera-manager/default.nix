{
  lib,
  bun,
  fetchFromGitHub,
  git,
  glib,
  gst_all_1,
  libv4l,
  nodejs,
  pkg-config,
  rustPlatform,
  stdenv,
  stdenvNoCC,
  writableTmpDirAsHomeHook,
  zstd,
}:
let
  version = "3.26.3";

  src = fetchFromGitHub {
    owner = "mavlink";
    repo = "mavlink-camera-manager";
    tag = "t${version}";
    hash = "sha256-fJwpGzi1kPuPDGGLBloN9CDPDEhtZc1QuAGwtOz6Kig=";
  };

  frontendNodeModules = stdenvNoCC.mkDerivation {
    pname = "mavlink-camera-manager-frontend-node-modules";
    inherit version src;

    impureEnvVars = lib.fetchers.proxyImpureEnvVars;

    nativeBuildInputs = [
      bun
      writableTmpDirAsHomeHook
    ];

    dontConfigure = true;

    buildPhase = ''
      runHook preBuild

      cd frontend
      export BUN_INSTALL_CACHE_DIR=$(mktemp -d)
      bun install \
        --cpu='*' \
        --os='*' \
        --frozen-lockfile \
        --ignore-scripts \
        --no-progress

      runHook postBuild
    '';

    installPhase = ''
      runHook preInstall

      mkdir -p $out/frontend
      find . -type d -name node_modules -exec cp -R --parents {} $out/frontend \;

      runHook postInstall
    '';

    dontFixup = true;

    outputHash = "sha256-YnkiKAxUibZFE2Un+BfxImGXEQjaFmi9zgcfURDHgLw=";
    outputHashAlgo = "sha256";
    outputHashMode = "recursive";
  };

  frontend = stdenvNoCC.mkDerivation {
    pname = "mavlink-camera-manager-frontend";
    inherit version src;

    nativeBuildInputs = [
      bun
      nodejs
      writableTmpDirAsHomeHook
    ];

    configurePhase = ''
      runHook preConfigure

      cp -R ${frontendNodeModules}/frontend/node_modules frontend/node_modules
      patchShebangs frontend/node_modules

      runHook postConfigure
    '';

    buildPhase = ''
      runHook preBuild

      pushd frontend
      bun run build-only
      popd

      runHook postBuild
    '';

    installPhase = ''
      runHook preInstall

      mkdir -p $out/share
      cp -R frontend/dist $out/share/mavlink-camera-manager-frontend

      runHook postInstall
    '';
  };
in
rustPlatform.buildRustPackage {
  pname = "mavlink-camera-manager";
  inherit version src;

  __structuredAttrs = true;

  cargoHash = "sha256-86+sEaQH8LRRd47+5WSjLhMKDLTKHfst7Me+3cEu0Xs=";

  nativeBuildInputs = [
    git
    pkg-config
    rustPlatform.bindgenHook
  ];

  env.SKIP_WEB = "1";

  # Upstream tests need GStreamer runtime plugins (x264enc) and a writable HOME
  doCheck = false;

  postPatch = ''
    mkdir -p frontend
    ln -s ${frontend}/share/mavlink-camera-manager-frontend frontend/dist
  '';

  buildInputs = [
    glib
    gst_all_1.gstreamer
    gst_all_1.gst-plugins-bad
    gst_all_1.gst-plugins-base
    gst_all_1.gst-rtsp-server
    libv4l
    stdenv.cc.cc.lib
    zstd
  ];
}
