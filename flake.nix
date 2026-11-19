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

      compiledPackages = pkgs: {
        bridges = pkgs.callPackage ./nix/packages/bridges { };

        blueos-recorder = pkgs.callPackage ./nix/packages/blueos-recorder { };

        disktest = pkgs.callPackage ./nix/packages/disktest { };

        linux2rest = pkgs.callPackage ./nix/packages/linux2rest { };

        machineid-cli = pkgs.callPackage ./nix/packages/machineid-cli { };

        mavlink-server = pkgs.callPackage ./nix/packages/mavlink-server { };

        mavlink2rest = pkgs.callPackage ./nix/packages/mavlink2rest { };

        mavlink-camera-manager = pkgs.callPackage ./nix/packages/mavlink-camera-manager { };

        mcap = pkgs.mcap-cli;

        mcap-foxglove-video-extract = pkgs.callPackage ./nix/packages/mcap-foxglove-video-extract { };

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
            blueos = self.packages.aarch64-linux.blueos-core;
            sdImageModule = "${nixpkgs}/nixos/modules/installer/sd-card/sd-image.nix";
            ubootPackage = self.packages.aarch64-linux.uboot-rpi;
          };
          modules = [
            ./nix/modules/blueos
            nixos-hardware.nixosModules."raspberry-pi-${board}"
            ./nix/nixos/rpi/pi${board}
            {
              services.blueos.board = "pi${board}";
              services.blueos.updates.manifestUrl = manifestUrl;
            }
          ]
          ++ lib.optional (version != null) { services.blueos.version = version; }
          ++ lib.optional (channel != null) { services.blueos.channel = channel; }
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
      lib = { inherit mkImage; };

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
        }
        // lib.optionalAttrs (system == "x86_64-linux") {
          blueos-guest-qemu = self.nixosConfigurations.blueos-guest.config.system.build.images.qemu;
          blueos-native-qemu = self.nixosConfigurations.blueos-native.config.system.build.images.qemu;
        }
      );

      nixosModules = {
        blueos =
          { pkgs, ... }:
          {
            imports = [ ./nix/modules/blueos ];

            services.blueos.package = self.packages.${pkgs.stdenv.hostPlatform.system}.blueos-core;
          };

        default = self.nixosModules.blueos;
      };

      nixosConfigurations = {
        blueos-pi4 = mkImage { board = "4"; };
        blueos-pi5 = mkImage { board = "5"; };

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
