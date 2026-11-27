# Zenoh 1.9.0, the version the pinned BlueOS uses for every piece: the router,
# its rest and storage plugins, the remote-api websocket plugin, and the Python
# and TypeScript clients.
#
# The plugin ABI check compares version and features for equality, so the daemon
# cannot come from nixpkgs: its 1.10.1 refuses to load a 1.9.0 plugin.
{
  fetchFromGitHub,
  lib,
  rustPlatform,
}:
rustPlatform.buildRustPackage (finalAttrs: {
  pname = "zenoh";
  version = "1.9.0";

  src = fetchFromGitHub {
    owner = "eclipse-zenoh";
    repo = "zenoh";
    rev = finalAttrs.version;
    hash = "sha256-sFHUphFu5a+buSa3GQvSmGo8SFtn3V5ZqTOnWMPlvs8=";
  };

  cargoHash = "sha256-1PjtZ5/bAnLlMbkcKAA6DCKDafItGiATjct5Pv8muas=";

  # Excluding the examples and the two template plugins keeps the build to the
  # router and the plugins that ship with it.
  cargoBuildFlags = [
    "--package"
    "zenoh"
    "--package"
    "zenohd"
    "--package"
    "zenoh-plugin-rest"
    "--package"
    "zenoh-plugin-storage-manager"
    "--bins"
    "--lib"
  ];

  doCheck = false;

  meta = {
    description = "Communication protocol that combines pub/sub with key value storage and computation";
    homepage = "https://zenoh.io";
    changelog = "https://github.com/eclipse-zenoh/zenoh/releases/tag/${finalAttrs.version}";
    license = lib.licenses.asl20;
    mainProgram = "zenohd";
    platforms = lib.platforms.linux;
  };
})
