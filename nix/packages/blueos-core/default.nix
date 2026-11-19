{
  callPackage,
  applyPatches,
  ardupilot-tools,
  bash,
  blueos-frontend,
  blueos-recorder,
  bridges,
  channel,
  disktest,
  filebrowser,
  gst_all_1,
  iproute2,
  lib,
  linux2rest,
  machineid-cli,
  makeWrapper,
  mavlink-server,
  mavlink2rest,
  mavlink-camera-manager,
  mcap,

  mcap-foxglove-video-extract,
  nginx,
  procps,
  pyproject-build-systems,
  pyproject-nix,
  python311,
  rev,
  src,
  swagger-ui,
  systemd,
  ttyd,
  uv2nix,
  version,
  zenoh,
}:
let
  patchedSrc = applyPatches {
    name = "BlueOS-${version}-patched";
    inherit src;
    patches = [
      ./cable-guy-dhcpcd.patch
      ./helper-nginx-paths.patch
      ./helper-nixos-factory-mode.patch
    ];
  };

  workspace = uv2nix.lib.workspace.loadWorkspace { workspaceRoot = "${patchedSrc}/core"; };

  overlay = workspace.mkPyprojectOverlay { sourcePreference = "wheel"; };

  setuptools =
    final: prev: name:
    prev.${name}.overrideAttrs (old: {
      nativeBuildInputs =
        (old.nativeBuildInputs or [ ]) ++ final.resolveBuildSystem { setuptools = [ ]; };
    });

  overrides = final: prev: {
    aiohttp = setuptools final prev "aiohttp";
    psutil = setuptools final prev "psutil";
    python-multipart = setuptools final prev "python-multipart";
    smbus2 = setuptools final prev "smbus2";
    pydantic = setuptools final prev "pydantic";
    sdbus = prev.sdbus.overrideAttrs (old: {
      buildInputs = (old.buildInputs or [ ]) ++ [ systemd ];
    });
  };

  pythonSet = (callPackage pyproject-nix.build.packages { python = python311; }).overrideScope (
    lib.composeManyExtensions [
      pyproject-build-systems.overlays.default
      overlay
      overrides
    ]
  );

  # An empty spec installs only each package's own dependencies. The default
  # groups would pull pytest, pylint and mypy into the runtime venv.
  env = pythonSet.mkVirtualEnv "blueos-core-env" { blueos-core = [ ]; };

  # Launched as `<service>/main.py` with its own directory on sys.path. Not the
  # same set as the units: some entries of core/start-blueos-core are not
  # Python services.
  services = [
    "ardupilot_manager"
    "bag_of_holding"
    "beacon"
    "bridget"
    "cable_guy"
    "commander"
    "customization"
    "disk_usage"
    "helper"
    "kraken"
    "nmea_injector"
    "pardal"
    "ping"
    "recorder_extractor"
    "wifi"
  ];

  serviceScripts = lib.concatMapStringsSep "\n" (name: ''
    makeWrapper $out/bin/python $out/bin/${name} \
      --add-flags "${patchedSrc}/core/services/${name}/main.py" \
      --prefix PYTHONPATH : "${patchedSrc}/core/services/${name}" \
      --prefix PYTHONPATH : "${ardupilot-tools}/lib/python" \
      --prefix PATH : "${ardupilot-tools}/bin" \
      --prefix LD_LIBRARY_PATH : "${lib.makeLibraryPath [ systemd ]}"
  '') services;

  runtimePath = lib.makeBinPath [
    ardupilot-tools
    blueos-recorder
    bridges
    disktest
    filebrowser
    gst_all_1.gst-plugins-base
    iproute2
    linux2rest
    machineid-cli
    mavlink-camera-manager
    mavlink-server
    mavlink2rest
    mcap
    mcap-foxglove-video-extract
    nginx
    procps
    systemd
    ttyd
    zenoh
  ];
in
env.overrideAttrs (old: {
  pname = "blueos-core";

  nativeBuildInputs = (old.nativeBuildInputs or [ ]) ++ [ makeWrapper ];

  postInstall = (old.postInstall or "") + ''
    ${serviceScripts}

    makeWrapper ${lib.getExe bash} $out/bin/start-blueos-core \
      --add-flags "${patchedSrc}/core/start-blueos-core" \
      --prefix PATH : "${patchedSrc}/core/services:${runtimePath}:$out/bin" \
      --prefix LD_LIBRARY_PATH : "${lib.makeLibraryPath [ systemd ]}"

    mkdir -p $out/share
    ln -s ${blueos-frontend}/share/blueos-frontend $out/share/blueos-frontend
    ln -s ${swagger-ui} $out/share/swagger-ui
  '';

  passthru = (old.passthru or { }) // {
    inherit
      env
      blueos-frontend
      swagger-ui
      version
      rev
      channel
      ;
    src = patchedSrc;
  };
})
