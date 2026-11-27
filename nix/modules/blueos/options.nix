# Options shared by both deployments. The native-only knobs (the package, the
# per-service packages, MAVLink ids, the update manifest) live in
# nix/modules/blueos/native.nix, so that a Docker guest does not have to build
# blueos-core to evaluate.
{
  config,
  lib,
  pkgs,
  ...
}:
let
  cfg = config.services.blueos;
  inherit (lib)
    mkOption
    types
    ;

  gitDescribe = "${cfg.version}-0-g${builtins.substring 0 7 cfg.revision}";
in
{
  options.services.blueos = {
    enable = mkOption {
      type = types.bool;
      default = false;
      description = "Enable BlueOS on this host.";
    };

    source = mkOption {
      type = types.path;
      default = ../../..;
      defaultText = lib.literalMD "this repository";
      description = ''
        The BlueOS checkout the host-side files come from: the udev rules and,
        for the Docker deployment, the seed `startup.json`.
      '';
    };

    version = mkOption {
      type = types.str;
      default = "unknown";
      defaultText = lib.literalMD "the version in the `blueos-core` package";
      description = "BlueOS version this system runs, reported by the UI and the version chooser.";
    };

    revision = mkOption {
      type = types.str;
      default = "unknown";
      defaultText = lib.literalMD "the commit in the `blueos-core` package";
      description = "BlueOS commit this system was built from.";
    };

    channel = mkOption {
      type = types.str;
      default = "dev";
      defaultText = lib.literalMD "the channel in the `blueos-core` package";
      description = "Release channel, such as stable, beta or dev.";
    };

    # Null on a Docker guest: the version running there is whatever the version
    # chooser last switched to, so the one this system was built with would be
    # wrong as soon as the vehicle updates.
    motdVersion = mkOption {
      type = types.nullOr types.str;
      default = null;
      internal = true;
      description = "Version the motd greets the user with, or null to leave it out.";
    };

    gitDescribe = mkOption {
      type = types.str;
      internal = true;
      readOnly = true;
      default = gitDescribe;
      defaultText = lib.literalMD "the version and revision, in `git describe` form";
      description = "Version string in the `<version>-0-g<rev>` form the Docker image used.";
    };

    board = mkOption {
      type = types.str;
      default = "unknown";
      example = "pi4";
      description = ''
        Board identifier, which selects the releases the update daemon offers.
        It has to match the `board` field the release manifest publishes.
      '';
    };

    user = {
      name = mkOption {
        type = types.str;
        default = "pi";
        description = "Unprivileged account BlueOS logs into over SSH.";
      };

      initialPassword = mkOption {
        type = types.str;
        default = "raspberry";
        description = "Password for that account, matching BlueOS's own default.";
      };
    };

    cache = {
      # Placeholder defaults, inherited from the original standalone flake.
      # Replace both with BlueRobotics-owned values, or set them to null to ship
      # a device that trusts no cache beyond nixpkgs.
      host = mkOption {
        type = types.nullOr types.str;
        default = "https://cache.eric.dev.br";
        description = ''
          Trusted Nix binary cache to use for BlueOS updates. The manifest a
          device reads has to name store paths this cache can serve, so both
          usually belong to the same deployment.
        '';
      };

      publicKey = mkOption {
        type = types.nullOr types.str;
        default = "cache.eric.dev.br-1:szEyq5LCjxDCUHYSRaSFU5HdHmR7QlT+FRG3tB9QtpE=";
        description = "Public key for the trusted Nix binary cache.";
      };
    };

    raspberryPi = {
      enable = mkOption {
        type = types.bool;
        default = pkgs.stdenv.hostPlatform.system == "aarch64-linux";
        defaultText = lib.literalMD "true on aarch64-linux";
        description = ''
          Apply the settings BlueOS expects on a Pi: the i2c bus for the
          Navigator and the UART left free for it.
        '';
      };
    };

    docker = {
      tag = mkOption {
        type = types.str;
        default = "master";
        example = "1.4.7";
        description = ''
          Tag of the BlueOS containers this host runs. It is the only thing that
          decides which BlueOS is installed: the version chooser moves it
          forward through Docker, not through NixOS generations.
        '';
      };

      coreImage = mkOption {
        type = types.str;
        default = "bluerobotics/blueos-core";
        description = "Repository the bootstrap container starts BlueOS from.";
      };

      bootstrapImage = mkOption {
        type = types.str;
        default = "bluerobotics/blueos-bootstrap";
        description = "Repository of the bootstrap container itself.";
      };

      images = mkOption {
        type = types.listOf (
          types.submodule {
            options = {
              image = mkOption {
                type = types.str;
                description = "Image reference the archive is tagged as, `repository:tag`.";
              };

              archive = mkOption {
                type = types.package;
                description = "The `docker save` archive to copy into the SD card.";
              };
            };
          }
        );
        default = [ ];
        example = lib.literalExpression "blueos-release.images";
        description = ''
          Images to ship inside the SD card, so a board whose first boot has no
          network can still install BlueOS. Each is loaded before anything pulls
          from a registry, and keeps the tag its archive carries, so the core
          image here has to be the one `docker.tag` names.

          Each archive is a fixed-output derivation pinned to one release, so
          setting this while leaving `docker.tag` at a moving tag would put two
          different BlueOS versions on the card.
        '';
      };
    };
  };
}
