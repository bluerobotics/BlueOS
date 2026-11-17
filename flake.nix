{
  description = "BlueOS, packaged as a NixOS system";

  # Placeholder: both point at personal infrastructure and have to be replaced
  # with BlueRobotics-owned endpoints before this is usable by anyone else.
  nixConfig = {
    extra-substituters = [ "https://cache.eric.dev.br" ];
    extra-trusted-public-keys = [
      "cache.eric.dev.br-1:szEyq5LCjxDCUHYSRaSFU5HdHmR7QlT+FRG3tB9QtpE="
    ];
  };

  inputs = {
    self.submodules = true;

    nixpkgs.url = "https://channels.nixos.org/nixos-unstable/nixexprs.tar.zst";
    nixos-hardware = {
      url = "github:NixOS/nixos-hardware";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    pyproject-nix = {
      url = "github:pyproject-nix/pyproject.nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    uv2nix = {
      url = "github:pyproject-nix/uv2nix";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    pyproject-build-systems = {
      url = "github:pyproject-nix/build-system-pkgs";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.uv2nix.follows = "uv2nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs =
    {
      self,
      nixpkgs,
      nixos-hardware,
      pyproject-nix,
      uv2nix,
      pyproject-build-systems,
      ...
    }:
    let
      inherit (nixpkgs) lib;

      forAllSystems = lib.genAttrs [
        "x86_64-linux"
        "aarch64-linux"
        "aarch64-darwin"
      ];

      revision = self.rev or (self.dirtyRev or null);
      shortRev = if revision == null then "unknown" else builtins.substring 0 7 revision;

      # The metadata that is not a property of the commit, shared by
      # blueos-core and blueos-frontend. `version` and `channel` are literals in
      # nix/version.nix, since a flake cannot see its own tags.
      blueos-version =
        let
          stamp = self.lastModifiedDate or "";
        in
        {
          # `rev` is absent when the input is a dirty checkout, which is what a
          # `path:` override of a working tree looks like.
          rev = self.rev or (self.dirtyRev or "unknown");

          # Derived from the source rather than the clock: the wall clock would
          # make every build a different store path.
          date =
            if builtins.stringLength stamp >= 8 then
              "${builtins.substring 0 4 stamp}-${builtins.substring 4 2 stamp}-${builtins.substring 6 2 stamp}"
            else
              "unknown";

          inherit (import ./nix/version.nix) version channel;
        };

      gstFor = pkgs: pkgs.callPackage ./nix/packages/gst.nix { };

      compiledPackages =
        pkgs:
        let
          # Shared so mavlink-camera-manager and mcap-foxglove-video-extract
          # link the same trimmed GStreamer.
          gst = gstFor pkgs;
        in
        {
          bridges = pkgs.callPackage ./nix/packages/bridges { };

          blueos-recorder = pkgs.callPackage ./nix/packages/blueos-recorder { };

          disktest = pkgs.callPackage ./nix/packages/disktest { };

          linux2rest = pkgs.callPackage ./nix/packages/linux2rest { };

          machineid-cli = pkgs.callPackage ./nix/packages/machineid-cli { };

          mavlink-server = pkgs.callPackage ./nix/packages/mavlink-server { };

          mavlink2rest = pkgs.callPackage ./nix/packages/mavlink2rest { };

          mavlink-camera-manager = pkgs.callPackage ./nix/packages/mavlink-camera-manager { inherit gst; };

          mcap = pkgs.mcap-cli;

          mcap-foxglove-video-extract = pkgs.callPackage ./nix/packages/mcap-foxglove-video-extract {
            inherit gst;
          };

          zenoh = pkgs.callPackage ./nix/packages/zenoh { };

          zenoh-backend-filesystem = pkgs.callPackage ./nix/packages/zenoh-backend-filesystem { };

          zenoh-plugin-remote-api = pkgs.callPackage ./nix/packages/zenoh-plugin-remote-api { };
        };

      # Exported so a release repository can build an image from a pinned
      # commit with its own version, manifest and cache. The defaults are what
      # this repository builds for itself, which is what CI caches.
      #
      # `manifestUrl` is a placeholder pointing at the standalone flake's
      # published manifest. It has to move to a BlueRobotics-owned endpoint
      # before these images are distributed. Pass `null` to ship a device that
      # offers no remote releases.
      mkImage =
        {
          board,
          version ? null,
          channel ? null,
          manifestUrl ? "https://epiceric.github.io/blueos-nix/manifest.json",
          cache ? null,
        }:
        lib.nixosSystem {
          system = "aarch64-linux";
          specialArgs = {
            sdImageModule = "${nixpkgs}/nixos/modules/installer/sd-card/sd-image.nix";
            ubootPackage = self.packages.aarch64-linux.uboot-rpi;
          };
          modules = [
            ./nix/modules/blueos/native.nix
            nixos-hardware.nixosModules."raspberry-pi-${board}"
            ./nix/nixos/rpi/pi${board}
            {
              services.blueos = {
                package = self.packages.aarch64-linux.blueos-core;
                board = "pi${board}";
                updates.manifestUrl = manifestUrl;
                rollback.enable = lib.mkDefault true;
              };
            }
          ]
          ++ lib.optional (version != null) { services.blueos.version = version; }
          ++ lib.optional (channel != null) { services.blueos.channel = channel; }
          ++ lib.optional (cache != null) { services.blueos.cache = cache; };
        };

      # The Docker deployment. Same board support and the same SD image, but
      # BlueOS itself is a container the vehicle updates through the version
      # chooser rather than a NixOS generation, so there is no `version`,
      # `channel` or `manifestUrl`: those describe a NixOS generation, and here
      # `docker.tag` is what decides which BlueOS is installed.
      #
      # By default the card ships the factory core and bootstrap images, so a
      # brand new card comes up with BlueOS the way a Raspbian one does, without
      # needing a registry. Pass `offline = false` for a card that is expected
      # to have a network on first boot and should not carry 500MB of images.
      #
      # `tag` has to agree with the archives when they are shipped, since a
      # loaded archive keeps its own tag; asking for another one drops the
      # archives and the card pulls that tag on first boot instead.
      mkGuestImage =
        {
          board,
          tag ? null,
          cache ? null,
          offline ? true,
        }:
        let
          release = self.packages.aarch64-linux.blueos-release;

          containerTag = if tag != null then tag else release.tag;
          bakeImages = offline && containerTag == release.tag;
        in
        lib.nixosSystem {
          system = "aarch64-linux";
          specialArgs = {
            sdImageModule = "${nixpkgs}/nixos/modules/installer/sd-card/sd-image.nix";
            ubootPackage = self.packages.aarch64-linux.uboot-rpi;
          };
          modules = [
            ./nix/modules/blueos/guest.nix
            nixos-hardware.nixosModules."raspberry-pi-${board}"
            ./nix/nixos/rpi/pi${board}
            {
              services.blueos = {
                board = "pi${board}";
                raspberryPi.enable = true;
                docker.tag = containerTag;
              };

              image.baseName = "blueos-pi${board}-guest-${shortRev}";
            }
          ]
          ++ lib.optional bakeImages { services.blueos.docker.images = release.images; }
          ++ lib.optional (cache != null) { services.blueos.cache = cache; };
        };

      mkQemuGuest =
        { name, module }:
        lib.nixosSystem {
          system = "x86_64-linux";
          specialArgs = {
            blueos = self.packages.x86_64-linux.blueos-core;
          };
          modules = [
            module
            { image.baseName = lib.mkDefault "blueos-${name}-${shortRev}"; }
          ];
        };
    in
    {
      lib = {
        inherit mkImage mkGuestImage;
      };

      packages = forAllSystems (
        system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
        in
        compiledPackages pkgs
        // {
          blueos-frontend = pkgs.callPackage ./nix/packages/blueos-frontend {
            inherit (blueos-version)
              version
              rev
              date
              ;
            src = self.outPath;
          };

          ardupilot-tools = pkgs.callPackage ./nix/packages/ardupilot-tools { };

          swagger-ui = pkgs.callPackage ./nix/packages/swagger-ui { };

          blueos-updates = pkgs.callPackage ./nix/packages/blueos-updates { src = self.outPath; };

          blueos-core = pkgs.callPackage ./nix/packages/blueos-core {
            inherit
              pyproject-nix
              uv2nix
              pyproject-build-systems
              ;

            gst = gstFor pkgs;

            src = self.outPath;

            inherit (blueos-version)
              version
              rev
              channel
              ;

            inherit (self.packages.${system})
              ardupilot-tools
              blueos-recorder
              blueos-frontend
              bridges
              disktest
              linux2rest
              machineid-cli
              mavlink-server
              mavlink2rest
              mavlink-camera-manager
              mcap
              mcap-foxglove-video-extract
              swagger-ui
              zenoh
              ;
          };

          default = self.packages.${system}.blueos-core;
        }

        // lib.optionalAttrs (system == "aarch64-linux") {
          uboot-rpi = pkgs.callPackage ./nix/packages/uboot-rpi { };

          blueos-release = pkgs.callPackage ./nix/packages/blueos-release { };
        }
        // lib.optionalAttrs (system == "x86_64-linux") {
          blueos-guest-qemu = self.nixosConfigurations.blueos-guest.config.system.build.images.qemu;
          blueos-native-qemu = self.nixosConfigurations.blueos-native.config.system.build.images.qemu;
        }
      );

      checks = forAllSystems (
        system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
        in
        lib.optionalAttrs pkgs.stdenv.hostPlatform.isLinux {
          gstreamer-trim = (gstFor pkgs).check;
        }
      );

      nixosModules = {
        blueos =
          { pkgs, ... }:
          {
            imports = [ ./nix/modules/blueos/native.nix ];

            services.blueos.package = self.packages.${pkgs.stdenv.hostPlatform.system}.blueos-core;
          };

        default = self.nixosModules.blueos;
      };

      nixosConfigurations = {
        blueos-pi4 = mkImage { board = "4"; };
        blueos-pi5 = mkImage { board = "5"; };

        blueos-pi4-guest = mkGuestImage { board = "4"; };
        blueos-pi5-guest = mkGuestImage { board = "5"; };

        blueos-guest = mkQemuGuest {
          name = "guest";
          module = ./nix/nixos/qemu/sil.nix;
        };
        blueos-native = mkQemuGuest {
          name = "native";
          module = ./nix/nixos/qemu/native.nix;
        };
      };

      devShells =
        lib.genAttrs
          [
            "x86_64-linux"
            "aarch64-linux"
            "aarch64-darwin"
          ]
          (
            system:
            let
              pkgs = nixpkgs.legacyPackages.${system};
            in
            {
              default = pkgs.mkShell {
                packages = [
                  pkgs.bun
                  pkgs.cargo
                  pkgs.clippy
                  pkgs.lsof
                  pkgs.nixfmt
                  pkgs.nodejs_24
                  pkgs.parallel
                  pkgs.python311
                  pkgs.pkg-config
                  pkgs.rustc
                  pkgs.rustfmt
                  pkgs.shellcheck
                  pkgs.uv
                ];
              };
            }
          );
    };
}
