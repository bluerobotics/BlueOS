# BlueOS on NixOS

NixOS support for BlueOS on Raspberry Pis 4 and 5.

The revision and build date come from the flake's own git metadata (`self.rev`, `self.lastModifiedDate`), while `version` and `channel` in `nix/version.nix` are literals, because a flake cannot read its own tags. They should be bumped as part of cutting a release.

## Developing

The devshell carries the toolchain for both halves: `bun` and `nodejs` for the frontend, `uv` and `python311` for the Python services, and `cargo` and `rustc` for the Rust packages.

```fish
nix develop
```

Packages are built by the flake:

```fish
nix build .#blueos-core
```

The flake evaluates only git-tracked files, so make sure to `git add` them.

## Building an image

`nixosConfigurations.blueos-pi4` and `blueos-pi5` are `aarch64-linux` systems, so building one needs either an ARM host or `binfmt` QEMU emulation on an x86_64 machine.

```fish
nix build .#nixosConfigurations.blueos-pi4.config.system.build.sdImage
```

The configurations in this repository call it with no release configured, so they report the literal version and use the placeholder manifest and cache described below. That is what CI caches.

## Releases

Publishing lives outside this repo.

`lib.mkImage` builds the same system with a different version, manifest or cache, which is what the release repo uses:

```nix
blueos.lib.mkImage {
  board = "4";
  version = "1.5.0";
  channel = "stable";
  manifestUrl = "https://releases.example.com/blueos/manifest.json";
  cache = {
    host = "https://cache.example.com";
    publicKey = "cache.example.com-1:...";
  };
}
```

The release repo pins a BlueOS commit, tags it on its own schedule, builds the images and publishes `manifest.json`. Tagging images there rather than here keeps them off the Docker container's release cadence.

## QEMU guests

Two x86_64 guests exist for end-to-end tests, sharing `nix/nixos/qemu/common.nix`:

- `blueos-guest` is a Docker host. BlueOS is installed as a container by the test run.
- `blueos-native` runs `services.blueos` from this checkout. It exists to catch regressions in the port.

```fish
nix build .#packages.x86_64-linux.blueos-guest-qemu
nix build .#packages.x86_64-linux.blueos-native-qemu
```

`system.build.images.qemu` runs its install step inside `vmTools.runInLinuxVM`, so building either image requires the `kvm` system feature.

`blueos-native` disables the rollback feature, since it requires nixos-hardware's Raspberry Pi modules.

## Patch policy

Patches allow the NixOS version to diverge from the Docker origin in a controlled manner.

Every patch has to fall into exactly one of these buckets:

- **Never upstream.** The change is wrong for the container image. Each of these needs a comment in the patch itself saying so and why, so it does not get proposed again.
- **Permanently carried.** A feature this flake needs that the main repo will not take, or has not taken yet.

The patches currently carried:

| Patch | Bucket | Why |
| --- | --- | --- |
| `blueos-core/cable-guy-dhcpcd.patch` | Never upstream | A `dhcpcd` daemon already owns the interface on Bookworm and Bullseye; the one-shot client would regress the inherited `DHCPCD` handler. |
| `blueos-core/helper-nixos-factory-mode.patch` | Never upstream | Skips the factory-mode probe, which asks the container version chooser for a `factory` tag. Generations have no such concept, so the probe would always fail. |
| `blueos-core/helper-nginx-paths.patch` | Permanently carried | Points helper at this flake's nginx pid file, extension directory and config. |

A patch that upstream merges must be deleted in the same commit that notices it.

## Known gaps

- **No RPi3 support.** A Navigator cannot be used on a Pi3, the hat expects a pinout the board does not have.
- **Log rotation.** BlueOS removed the `log_zipper` service without a replacement. `/var/logs/blueos` now grows until `nix.gc` removes an old generation.
- **Navigator EEPROM.** The EEPROM endpoints read `/sys/bus/i2c/devices/0-0050/eeprom`, which only exists when the `navigator-eeprom` device tree overlay is loaded. The Pi 4 image loads it, but the Pi 5 board script does not, so those endpoints report `EEPROM_NOT_FOUND` there.
