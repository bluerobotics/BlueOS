# BlueOS running in Docker on a NixOS host: the container layout install.sh
# produces on Raspbian, with NixOS owning the operating system underneath.
#
# Only the bootstrap container is NixOS's business, and only its creation. That
# container is the same one install.sh creates: it reads startup.json and runs
# blueos-core itself, so the version chooser and the factory reset keep working
# by rewriting that file and restarting the container, exactly as on Raspbian.
#
# That is also why this does not use virtualisation.oci-containers, which runs
# `docker rm -f` before `docker run` on every start. The version chooser switches
# bootstrap by renaming the container to bootstrap-backup and creating a new one
# under the old name, and remove-and-run on boot would silently undo that. This
# mirrors install.sh instead: `docker create` once, `docker start` every boot.
{
  config,
  lib,
  pkgs,
  ...
}:
let
  cfg = config.services.blueos;
  inherit (lib)
    mkDefault
    mkIf
    ;

  docker = config.virtualisation.docker.package;

  container = "blueos-bootstrap";

  core = "${cfg.docker.coreImage}:${cfg.docker.tag}";
  bootstrap = "${cfg.docker.bootstrapImage}:${cfg.docker.tag}";
  factory = "${cfg.docker.coreImage}:factory";

  startupJson = pkgs.writeText "blueos-startup.json" (
    builtins.replaceStrings [ ''"factory"'' ] [ ''"${cfg.docker.tag}"'' ] (
      builtins.readFile "${cfg.source}/bootstrap/startup.json.default"
    )
  );

  # The images the card carries, already unpacked into a Docker data-root. When
  # this is present there is nothing to load or pull, so the truncation checks
  # below are not needed.
  bakedStore =
    if cfg.docker.images == [ ] then
      null
    else
      pkgs.callPackage ../../packages/blueos-docker-store {
        inherit (cfg.docker) images;
      };

  # The file whose presence proves an image was unpacked completely: its own
  # entrypoint, which is what a truncated load leaves empty. Checked by reading
  # it back out of the loaded image, since that is the only way to see what
  # actually landed in the store.
  sentinelFor =
    image:
    if image == core then
      "/usr/bin/start-blueos-core"
    else if image == bootstrap then
      "/main.py"
    else
      throw "services.blueos.docker.images: no sentinel known for ${image}";

  # Where the baked store is unpacked.
  #
  # /var/lib/docker is dockerd's own default (daemon/config/config_linux.go), so
  # naming it here only makes the unit's intent legible; nothing overrides it.
  dataRoot = "/var/lib/docker";

  # Only needed when the card does not carry the images itself.
  pullScript = ''
    # bootstrap, and core when the card does not carry it. A pull can be cut
    # short the same way a load can, so a truncated image is dropped and
    # fetched again rather than trusted. Anything load() already proved good is
    # skipped, since verifying it again would start a container for nothing.
    while read -r image sentinel; do
      grep -qxF "$image" "$verified" && continue
      if have "$image" && ! intact "$image" "$sentinel"; then
        echo "Removing truncated $image" >&2
        docker image rm --force "$image" > /dev/null
      fi
      if ! have "$image"; then
        docker pull "$image"
      fi
    done <<'IMAGES'
    ${bootstrap} ${sentinelFor bootstrap}
    ${core} ${sentinelFor core}
    IMAGES
  '';

  # Load and truncation detection, only needed when the card does not carry a
  # pre-built store. Kept as one string so the install script does not have to
  # carry dead branches.
  loadMachinery = ''
    # An interrupted load leaves a present but truncated image, which `docker
    # image inspect` reports as healthy: the layer is there, its contents are
    # not. `test -s` inside the image answers it with an exit code, so nothing
    # is printed. That matters because the daemon logs container output to the
    # journal: reading the file out to measure it would dump the entrypoint
    # into the journal on every boot, and no log driver is asked to keep it.
    intact() {
      have "$1" || return 1
      docker run --rm --log-driver=none --entrypoint /bin/sh "$1" -c "test -s '$2'" > /dev/null 2>&1
    }

    # Images this boot has already proven good, so the pull loop below does not
    # pay for verifying them a second time.
    verified=$(mktemp)
    trap 'rm -f "$verified"' EXIT

    # Stamps live here; the directory also exists as a tmpfiles rule, but the
    # stamp is written by this unit and must not depend on rule ordering.
    mkdir -p /root/.config/blueos

    # A stamp records which archive a tag's image came from, and the id it had
    # once the load finished. Keying it on the archive's store path is what
    # makes a rebuilt card reload: a new archive is a new path, which no
    # existing stamp covers, where comparing tags alone would keep serving the
    # image an older archive left behind.
    #
    # The stamp and `intact` answer different questions and neither replaces
    # the other: the stamp says the tag came from this archive, `intact` says
    # the bytes survived. A truncated image keeps its id, so an id match alone
    # would vouch for a file that is empty.
    load() {
      local image=$1 archive=$2 sentinel=$3
      local stamp=/root/.config/blueos/.loaded-$(basename "$archive")
      local expected id

      expected=$(cat "$stamp" 2> /dev/null || true)
      id=$(docker image inspect -f '{{.Id}}' "$image" 2> /dev/null || true)
      if [ -n "$expected" ] && [ "$id" = "$expected" ] && intact "$image" "$sentinel"; then
        echo "$image" >> "$verified"
        return 0
      fi

      # Absent, truncated, or left over from another archive. Removed by id,
      # not by tag: `:factory` is another tag on the same image, so removing
      # only `$image` would untag it and leave the damaged layers in place for
      # `load` to reuse. Dropping the id is what forces a real re-unpack.
      if have "$image"; then
        echo "Removing $image, which is not what $archive provides" >&2
        docker image rm --force "$(docker image inspect -f '{{.Id}}' "$image")" > /dev/null
      fi
      rm -f "$stamp"

      docker load --input "$archive"
      if ! intact "$image" "$sentinel"; then
        echo "error: $image is still truncated after loading $archive" >&2
        docker image rm --force "$image" > /dev/null || true
        return 1
      fi
      docker image inspect -f '{{.Id}}' "$image" > "$stamp"
      echo "$image" >> "$verified"
    }
  '';

  installScript = ''
    set -e
    have() { docker image inspect "$1" > /dev/null 2>&1; }

    ${lib.optionalString (bakedStore == null) loadMachinery}

    ${lib.optionalString (bakedStore != null) ''
      # The store's images are unpacked but nameless: dockerd owns
      # repositories.json, so it cannot ship one. This list is the tag set the
      # build recorded, applied by image id.
      #
      # Skipped when the tag already exists, so a tag the version chooser moved
      # keeps its new target. Deleted layers cannot reach here: the store unit
      # verifies every shipped layer before docker.service starts and
      # re-extracts if one is missing.
      while read -r reference id _; do
        have "$reference" || docker tag "$id" "$reference"
      done < ${bakedStore}/docker.tar.images
    ''}

    # :factory is another name for the archive's image, so a boot that finds
    # the archive's tag gone can restore it without unpacking it again.
    if ! have ${core} && have ${factory}; then
      docker tag ${factory} ${core}
    fi

    ${lib.optionalString (bakedStore == null) ''
      ${lib.concatMapStringsSep "\n" (image: ''
        load ${image.image} ${image.archive} ${sentinelFor image.image}
      '') cfg.docker.images}

      ${pullScript}
    ''}

    # Set once and left alone. Tagging on every boot would move the fallback
    # to whatever the card shipped, undoing the version the vehicle is on.
    if ! have ${factory}; then
      docker tag ${core} ${factory}
    fi

    # Only create. A container the version chooser replaced is a different one
    # under the same name, and it has to survive the reboot.
    if ! docker inspect --type container ${container} > /dev/null 2>&1; then
      docker create -t \
        --restart unless-stopped \
        --name ${container} \
        --net=host \
        -v /root/.config/blueos/bootstrap:/root/.config/bootstrap \
        -v /run/docker.sock:/var/run/docker.sock \
        -v /var/logs/blueos:/var/logs/blueos \
        -e BLUEOS_CONFIG_PATH=/root/.config/blueos \
        ${bootstrap}
    fi

    docker start ${container}
  '';
in
{
  imports = [
    ./options.nix
    ./host.nix
  ];

  config = mkIf cfg.enable {
    assertions = [
      {
        assertion = lib.all (image: image.image == core || image.image == bootstrap) cfg.docker.images;
        message = "Every image in services.blueos.docker.images has to be the one services.blueos.docker.coreImage/bootstrapImage and docker.tag name, since a loaded archive keeps its own tag rather than taking the one it is started from.";
      }
    ];

    # rpi/common.nix gives both deployments a bootcount U-Boot, but only
    # native.nix imports rollback.nix, which is what writes the good.conf its
    # altbootcmd boots and what clears /bootcount. Left alone, a guest card
    # counts up in /bootcount until it passes the boot limit and then fails to
    # boot with no fallback, so the guest takes the same U-Boot without the
    # bootcount support.
    hardware.raspberry-pi.firmware.uboot.package = lib.mkForce (
      pkgs.callPackage ../../packages/uboot-rpi { bootcount = false; }
    );

    # The store replaces the archives rather than joining them: once the data
    # root is populated there is nothing left to `docker load`, so shipping the
    # archives too would just duplicate the same layers on the card.
    sdImage.storePaths =
      if bakedStore != null then [ bakedStore ] else map (image: image.archive) cfg.docker.images;

    virtualisation.docker = {
      enable = mkDefault true;
      daemon.settings.features.containerd-snapshotter = false;
    };

    services.journald.settings.Journal.Storage = "persistent";

    environment.etc."dhcpcd.conf".text = "";

    systemd.tmpfiles.rules = [
      "d /root/.config/blueos/bootstrap 0755 root root -"
      "d /root/.docker 0755 root root -"
      "d /root/.majortom 0755 root root -"
      "d /home/${cfg.user.name}/.docker 0755 ${cfg.user.name} users -"
      "d /run/wpa_supplicant 0755 root root -"
      "d /tmp/wpa_playground 0755 root root -"
      "L /etc/resolv.conf.host - - - - /etc/resolv.conf"
    ];

    systemd.services = {
      # docker.service carries `Wants=network-online.target` from moby's own
      # unit, and NetworkManager's wait-online is what satisfies that target. On
      # a card that carries its images there is nothing to pull, so all it buys
      # is a DHCP round trip before the container may start: measured 19.7s on a
      # Pi 4, over half of userspace. A card built for `offline = false` keeps
      # it, since that one really does pull on first boot.
      NetworkManager-wait-online.enable = mkDefault (bakedStore == null);

      # Seeds only. The version chooser rewrites the file, so overwriting it on
      # every boot would undo the version the vehicle is on.
      blueos-startup-json = {
        description = "Seed the BlueOS bootstrap startup.json";
        wantedBy = [ "multi-user.target" ];
        before = [ "blueos-bootstrap.service" ];
        serviceConfig = {
          Type = "oneshot";
          RemainAfterExit = true;
        };
        script = ''
          if [ ! -e /root/.config/blueos/bootstrap/startup.json ]; then
            install -m 0644 ${startupJson} /root/.config/blueos/bootstrap/startup.json
          fi
        '';
      };

      blueos-bootstrap = {
        description = "Create and start the BlueOS bootstrap container";
        wantedBy = [ "multi-user.target" ];
        after = [
          "docker.service"
          "docker.socket"
          "blueos-startup-json.service"
        ]
        ++ lib.optional (bakedStore != null) "blueos-docker-store.service";
        requires = [ "docker.service" ];
        path = [ docker ];

        # Not a oneshot: a oneshot stays in "activating" until the script
        # exits, so multi-user.target would wait for the image work, which is
        # minutes when a card has to load an archive. exec lets the boot finish
        # and BlueOS appear when the container actually starts.
        #
        # No restart, because this script is the one thing that must not be
        # run twice at once. Restarting it kills a `docker load` partway and
        # starts the next attempt on the half-unpacked layers, which is how a
        # present but truncated image is made. Every boot runs it again anyway,
        # so a failure is already retried there.
        serviceConfig = {
          Type = "exec";
          RemainAfterExit = true;
          TimeoutStartSec = 0;
          Restart = "no";
        };
        unitConfig.StartLimitIntervalSec = 0;
        script = installScript;
      };
    }
    // lib.optionalAttrs (bakedStore != null) {
      # The store ships as a tar because a directory cannot survive /nix/store:
      # it canonicalises modes and drops xattrs, and both are load-bearing in an
      # overlay2 layer. Extracting here rather than into the SD image itself is
      # forced by make-ext4-fs.nix, which runs populateRootCommands *outside*
      # fakeroot -- setuid bits and the opaque xattr would be silently lost.
      #
      # This runs before docker.service, so the daemon's first scan of its data
      # root already finds every image present and no container has to wait for
      # an unpack. Ordered with requiredBy rather than after alone: Docker
      # reading a half-populated data root is worse than not starting.
      blueos-docker-store = {
        description = "Unpack the BlueOS image store into Docker's data root";
        # Pulled in by docker.service rather than by a target: Docker reading a
        # half-populated data root is worse than not starting, so the ordering
        # and the dependency have to be the same edge.
        requiredBy = [ "docker.service" ];
        before = [ "docker.service" ];
        # The root filesystem is built sized to its contents plus 16MB, and only
        # grows to fill the card in expand-root-partition. Extracting 1.4GB
        # before that runs would fail with ENOSPC, so the ordering is load-
        # bearing rather than tidy. `wants`, not `requires`: that unit only
        # exists while sdImage.expandOnBoot is on, and requiring a unit that is
        # absent fails this one.
        after = [ "expand-root-partition.service" ];
        wants = [ "expand-root-partition.service" ];
        serviceConfig = {
          Type = "oneshot";
          RemainAfterExit = true;
          # Extracting this on a slow card is minutes, and a timeout would leave
          # a half-populated store behind.
          TimeoutStartSec = 0;
        };
        script = ''
          set -e
          mkdir -p ${dataRoot}

          # Every layer this store ships has to be present and complete.
          #
          # Checking only that the layers which *are* there are consistent is
          # not enough: deleting a whole image takes its layers with it and
          # leaves a store that passes that check while missing an image, and
          # the boot then cannot tag or start it. Comparing against the shipped
          # list is what turns that into a re-extract.
          #
          # Also not by tar's exit status: tar exits 2 both for a real failure
          # and for a mode it lacks the privilege to apply, which on a card it
          # does not.
          layers=${dataRoot}/image/overlay2/layerdb/sha256
          verify() {
            local chain cache
            while read -r chain; do
              [ -n "$chain" ] || continue
              cache=$(cat "$layers/$chain/cache-id" 2> /dev/null) || return 1
              [ -d ${dataRoot}/overlay2/"$cache"/diff ] || return 1
              [ -f ${dataRoot}/overlay2/"$cache"/link ] || return 1
            done < ${bakedStore}/docker.tar.layers
          }

          # Checked every boot rather than gated on a stamp: the daemon removes
          # layers when an image is deleted (`docker image rm -f`, which the
          # version chooser does on every switch), and a stamp would then keep
          # a broken store forever. On a whole store this is the entire cost of
          # the unit.
          if verify; then
            echo "image store already populated, nothing to unpack"
            exit 0
          fi

          # --numeric-owner and --xattrs so a layer's setuid bits, its owners
          # and the opaque directory marks all come back as the daemon wrote
          # them. The whiteouts are already char devices in the tar.
          #
          # --warning=no-timestamp because there is no RTC: the clock starts at
          # whatever the build recorded in the firmware epoch and the layers
          # were built later, so every entry looks future-dated. Without it the
          # extract writes one line per file, 4201 of them for the shipped
          # images, which buries the rest of the boot in the journal.
          #
          # Extracting over an existing store is safe and is what repairs one:
          # the tar only writes the shipped layers, and repositories.json is
          # left alone, so images the version chooser pulled stay tagged.
          ${pkgs.zstd}/bin/zstd -dc ${bakedStore}/docker.tar.zst |
            ${pkgs.gnutar}/bin/tar -xf - -C ${dataRoot} \
              --numeric-owner --xattrs --warning=no-timestamp || true

          verify || {
            echo "error: ${bakedStore}/docker.tar.zst did not produce a usable store" >&2
            exit 1
          }
          echo "unpacked the image store into ${dataRoot}"
        '';
      };
    };
  };
}
