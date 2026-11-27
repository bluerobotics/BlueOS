{
  fetchFromGitHub,
  lib,
  rustPlatform,
}:
rustPlatform.buildRustPackage (finalAttrs: {
  pname = "disktest";
  version = "1.16.0";

  src = fetchFromGitHub {
    owner = "patrickelectric";
    repo = "disktest";
    tag = finalAttrs.version;
    hash = "sha256-SQx2W0zJvpMAewobhCoATanpuzbhi/iqviFW5XBLkt8=";
  };

  cargoLock.lockFile = ./Cargo.lock;

  cargoBuildFlags = [
    "--package"
    "disktest"
  ];

  meta = {
    description = "Tester for SSDs, SD cards and other block devices";
    homepage = "https://github.com/patrickelectric/disktest";
    license = with lib.licenses; [
      mit
      asl20
    ];
    mainProgram = "disktest";
    platforms = lib.platforms.linux;
  };
})
