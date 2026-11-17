# The filesystem storage backend, which zenohd loads alongside the storage
# manager plugin. The pinned blueos-zenoh.json5 declares no storages, so nothing
# uses it yet; it exists so the deployment matches the release's plugin set and
# a storage can be declared later without repackaging zenoh.
#
# Pinned to 1.9.0 for the same reason as the router.
{
  fetchzip,
  lib,
  pkg-config,
  rustPlatform,
  zstd,
}:
rustPlatform.buildRustPackage (finalAttrs: {
  pname = "zenoh-backend-filesystem";
  version = "1.9.0";

  src = fetchzip {
    url = "https://static.crates.io/crates/zenoh-backend-filesystem/zenoh-backend-filesystem-${finalAttrs.version}.crate";
    extension = "tar.gz";
    hash = "sha256-5n4TGsdubT5ASZPCETtpLEKNRY74LtOQt6f5XP1wO7s=";
  };

  cargoHash = "sha256-kbMOAL/CvmbOjKVpnZrZlRsl0sibTBwvqCq5GzXjGx8=";

  nativeBuildInputs = [
    pkg-config
    rustPlatform.bindgenHook
  ];

  buildInputs = [ zstd ];

  # The vendored rocksdb 9.9.3 predates GCC 16, which no longer pulls cstdint
  # in transitively, so its headers fail on uint64_t.
  env.CXXFLAGS = "-include cstdint";

  meta = {
    description = "Filesystem storage backend for Zenoh";
    homepage = "https://github.com/eclipse-zenoh/zenoh-backend-filesystem";
    license = lib.licenses.asl20;
    platforms = lib.platforms.linux;
  };
})
