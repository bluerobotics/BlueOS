{
  fetchFromGitHub,
  lib,
  pkg-config,
  rustPlatform,
  zstd,
}:
let
  # ROS message definitions, a submodule the release archive lacks. Only msgs/
  # is compiled in, via include_dir!.
  zBlueberry = fetchFromGitHub {
    owner = "patrickelectric";
    repo = "zBlueberry";
    rev = "b32e621173041aaa5e723705b1ffe6207dc68533";
    hash = "sha256-ZA4gZr0zLy+lM+XTtpI0+564lVab08snOrOQkbNJsII=";
  };
in
rustPlatform.buildRustPackage (finalAttrs: {
  pname = "blueos-recorder";
  version = "0.0.5";

  src = fetchFromGitHub {
    owner = "bluerobotics";
    repo = "blueos-recorder";
    tag = finalAttrs.version;
    hash = "sha256-cOn+oiLxpqs1f7898N/Y1i1i+BC/B3656y3lKfr6Nvw=";
  };

  cargoLock.lockFile = ./Cargo.lock;

  postPatch = ''
    cp ${./Cargo.lock} Cargo.lock
    mkdir -p src/external/zBlueberry
    cp -r ${zBlueberry}/msgs src/external/zBlueberry/msgs
  '';

  nativeBuildInputs = [ pkg-config ];

  buildInputs = [ zstd ];

  meta = {
    description = "Records Zenoh traffic to MCAP files on BlueOS";
    homepage = "https://github.com/bluerobotics/blueos-recorder";
    license = lib.licenses.mit;
    mainProgram = "blueos-recorder";
    platforms = lib.platforms.linux;
  };
})
