# Automatic rollback for a BlueOS SD card.
#
# Two layers, because they cover different failures:
#
#   - U-Boot abandons a generation that never reaches userspace. The firmware
#     config points U-Boot at a bootcount file on the FAT partition; three
#     failed attempts make it run altbootcmd, which boots good.conf instead of
#     the extlinux menu. Nothing in the new generation has to work for this,
#     which is the case that actually bricks a card.
#   - A timer rolls back a generation that boots but is not healthy, or that
#     never confirms. This is what a bad service or network configuration needs,
#     since the bootloader cannot tell.
#
# Arming happens in a pre-switch check rather than an activation script:
# switch-to-configuration exits before activating for `boot`, so an activation
# script would miss every update that needs a reboot.

{
  config,
  lib,
  pkgs,
  ...
}:
let
  cfg = config.services.blueos.rollback;

  stateDir = "/var/lib/blueos/updates";
  stateFile = "${stateDir}/state.json";
  firmwareDir = config.hardware.raspberry-pi.firmware.path;
  bootcountFile = "${firmwareDir}/bootcount";

  profile = "/nix/var/nix/profiles/system";
  gcroot = "/nix/var/nix/gcroots/blueos/known-good";
  goodConf = "/boot/extlinux/good.conf";

  nix = config.nix.package.out;

  blueosUnits = lib.attrNames (
    lib.filterAttrs (_: unit: lib.elem "blueos.target" (unit.wantedBy or [ ])) config.systemd.services
  );

  arm = pkgs.writeShellScript "blueos-rollback-arm" ''
    set -eu
    toplevel=$(readlink -f "$1")
    action=$2

    # Only switch and boot change what the next boot runs
    case "$action" in
      switch|boot) ;;
      *) exit 0 ;;
    esac

    if [ "$toplevel" = "$(readlink -f /run/current-system)" ]; then
      exit 0
    fi

    mkdir -p ${stateDir}
    printf '{"pending":"%s","mode":"%s"}\n' "$toplevel" "$action" > ${stateFile}.tmp
    mv ${stateFile}.tmp ${stateFile}

    ${config.systemd.package}/bin/systemctl restart blueos-rollback.timer 2>/dev/null || true

    ${config.systemd.package}/bin/systemctl stop blueos-confirm-after-switch.service 2>/dev/null || true
    ${config.systemd.package}/bin/systemd-run \
      --quiet --no-block --collect --system \
      --unit=blueos-confirm-after-switch \
      --service-type=oneshot \
      --description="Confirm the generation an update just switched to" \
      --setenv=PATH="$PATH" \
      ${confirmAfterSwitch} "$toplevel" 2>/dev/null || true

    if [ ! -s ${goodConf} ]; then
      echo "no known-good generation yet, leaving the bootcount fallback disarmed" >&2
      exit 0
    fi

    if [ -d ${firmwareDir} ]; then
      printf '\275\001\000\001' > ${bootcountFile}
      sync ${bootcountFile} 2>/dev/null || sync
    fi
  '';

  healthCheckScript = pkgs.writeShellScript "blueos-health-check" ''
    set -eu

    failed=0
    for unit in ${lib.concatMapStringsSep " " (u: "${u}.service") blueosUnits}; do
      case "$(${config.systemd.package}/bin/systemctl is-failed "$unit" || true)" in
        failed) echo "$unit failed to start" >&2; failed=1 ;;
      esac
    done
    [ "$failed" -eq 0 ]

    ${pkgs.curl}/bin/curl --fail --silent --max-time 30 http://127.0.0.1/status > /dev/null

    ${cfg.healthCheck}
  '';

  confirm = pkgs.writeShellScript "blueos-rollback-confirm" ''
    set -eu
    toplevel=$(readlink -f ${profile})

    rm -f ${bootcountFile}
    sync

    mkdir -p "$(dirname ${gcroot})"
    ln -sfn "$toplevel" ${gcroot}

    # altbootcmd boots this directly
    mkdir -p "$(dirname ${goodConf})"
    {
      printf 'DEFAULT blueos-good\n'
      printf 'LABEL blueos-good\n'
      printf '  LINUX %s/kernel\n' "$toplevel"
      printf '  INITRD %s/initrd\n' "$toplevel"
      printf '  APPEND init=%s/init %s\n' "$toplevel" "$(cat "$toplevel/kernel-params")"
    } > ${goodConf}.tmp
    mv ${goodConf}.tmp ${goodConf}
    sync

    printf '{"knownGood":"%s"}\n' "$toplevel" > ${stateFile}.tmp
    mv ${stateFile}.tmp ${stateFile}
  '';

  # Judges a generation that an update just switched to, without waiting for the
  # deadline. The pre-switch check cannot do this itself: it runs before the
  # switch, when the profile already names the new generation but the old one is
  # still running, so judging there would confirm a build that never booted
  confirmAfterSwitch = pkgs.writeShellScript "blueos-confirm-after-switch" ''
    set -eu
    expected=$1

    deadline=$(( $(date +%s) + ${toString cfg.settleDelaySeconds} ))
    while [ "$(date +%s)" -lt "$deadline" ]; do
      sleep 1
    done

    running=$(readlink -f /run/current-system)
    if [ "$running" != "$expected" ]; then
      echo "still running $running, not confirming $expected" >&2
      exit 0
    fi

    case "$(readlink -f ${profile})" in
      "$running") ;;
      *) echo "a reboot is owed before $expected can be judged" >&2; exit 0 ;;
    esac

    if ${healthCheckScript}; then
      echo "the generation the update switched to is healthy, confirming it"
      ${confirm}
    else
      echo "the generation the update switched to is not healthy; leaving it to the deadline" >&2
    fi
  '';

  rollback = pkgs.writeShellScript "blueos-rollback" ''
    set -eu

    if ! grep -q '"pending"' ${stateFile} 2>/dev/null; then
      echo "no update pending, nothing to roll back"
      exit 0
    fi

    known_good=$(readlink -f ${gcroot} 2>/dev/null || true)
    if [ -z "$known_good" ] || [ ! -e "$known_good" ]; then
      echo "update pending but no known-good generation recorded, leaving the system alone" >&2
      exit 1
    fi

    if ${healthCheckScript}; then
      echo "the running generation is healthy, confirming it"
      ${confirm}
      exit 0
    fi

    if [ "$(readlink -f ${profile})" = "$known_good" ]; then
      echo "the known-good generation is itself unhealthy, refusing to loop" >&2
      exit 1
    fi

    echo "rolling back to $known_good"
    ${nix}/bin/nix-env --profile ${profile} --set "$known_good"
    "$known_good/bin/switch-to-configuration" boot

    rm -f ${bootcountFile}
    printf '{"knownGood":"%s","rolledBackFrom":"%s"}\n' "$known_good" \
      "$(readlink -f /run/current-system)" > ${stateFile}.tmp
    mv ${stateFile}.tmp ${stateFile}
    sync

    ${config.systemd.package}/bin/systemctl reboot
  '';
in
{
  options.services.blueos.rollback = {
    enable = lib.mkEnableOption "automatic rollback of a failed BlueOS update";

    timeout = lib.mkOption {
      type = lib.types.str;
      default = "10min";
      example = "30min";
      description = ''
        How long a freshly activated generation has to confirm itself before it
        is rolled back. Services come up in seconds; the margin is for the
        vehicle to reach the network, which is when a user can intervene.
      '';
    };

    settleDelaySeconds = lib.mkOption {
      type = lib.types.ints.unsigned;
      default = 30;
      description = ''
        How long to wait before judging a generation, so that services that
        restart a few times on startup are not counted as failed.
      '';
    };

    settleDelay = lib.mkOption {
      type = lib.types.str;
      internal = true;
      readOnly = true;
      default = "${toString cfg.settleDelaySeconds}s";
      defaultText = lib.literalMD "`settleDelaySeconds`, in systemd's time-span syntax";
      description = "`settleDelaySeconds` in the form systemd's `ExecStartPre` accepts.";
    };

    healthCheck = lib.mkOption {
      type = lib.types.lines;
      default = "";
      description = ''
        Extra shell commands run before a generation is confirmed. A non-zero
        exit treats the generation as failed.
      '';
    };
  };

  config = lib.mkIf cfg.enable {
    # The check text is inlined into a generated script whose $1 and $2 are the
    # new toplevel and the action
    system.preSwitchChecks.blueos-rollback-arm = "${arm} \"$1\" \"$2\"";

    systemd.services.blueos-boot-health = {
      description = "Confirm the running BlueOS generation";
      wantedBy = [ "multi-user.target" ];
      after = [
        "blueos.target"
        "nginx.service"
      ];
      wants = [ "blueos.target" ];
      serviceConfig = {
        Type = "oneshot";
        RemainAfterExit = true;
        ExecStart = pkgs.writeShellScript "blueos-boot-health" ''
          set -eu
          sleep ${cfg.settleDelay}
          ${healthCheckScript}
          ${confirm}
        '';
      };
    };

    systemd.services.blueos-rollback = {
      description = "Roll back to the last known-good BlueOS generation";
      after = [ "blueos-boot-health.service" ];
      serviceConfig = {
        Type = "oneshot";
        ExecStart = rollback;
      };
    };

    systemd.timers.blueos-rollback = {
      description = "Deadline for the running BlueOS generation to confirm";
      wantedBy = [ "timers.target" ];
      timerConfig = {
        OnActiveSec = cfg.timeout;
        Unit = "blueos-rollback.service";
      };
    };

    systemd.tmpfiles.rules = [
      "d ${stateDir} 0755 root root -"
      "d /nix/var/nix/gcroots/blueos 0755 root root -"
      "d /boot/extlinux 0755 root root -"
    ];
  };
}
