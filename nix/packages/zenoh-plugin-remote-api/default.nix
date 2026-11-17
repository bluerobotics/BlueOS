# Packaged from the crates.io tarball, the release form of eclipse-zenoh/zenoh-ts:
# it ships a lockfile with no git sources. The version has to match the router in
# nix/packages/zenoh exactly, because the plugin ABI check compares version and
# features for equality.
{
  fetchzip,
  lib,
  rustPlatform,
}:
rustPlatform.buildRustPackage (finalAttrs: {
  pname = "zenoh-plugin-remote-api";
  version = "1.9.0";

  # `.crate` is a gzipped tar under an extension the unpacker does not know.
  src = fetchzip {
    url = "https://static.crates.io/crates/zenoh-plugin-remote-api/zenoh-plugin-remote-api-${finalAttrs.version}.crate";
    extension = "tar.gz";
    hash = "sha256-ZJb16NLIZfY8RwwcO7qC37prYf/JyEUrkI2Ba484nmg=";
  };

  cargoHash = "sha256-+IY6ETJY0ES23nFL637y2k4qzn9uDOxzhlFhecUh+nY=";

  # The crate is a dynamically loaded plugin, so its only output is the .so.
  meta = {
    description = "Zenoh plugin exposing the remote API over websockets";
    homepage = "https://github.com/eclipse-zenoh/zenoh-ts";
    license = with lib.licenses; [
      epl20
      asl20
    ];
    platforms = lib.platforms.linux;
  };
})
