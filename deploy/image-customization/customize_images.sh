#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PARAMS_URL="https://docs.bluerobotics.com/Blueos-Parameter-Repository/params_v1.json"
FIRMWARE_HOST="https://firmware.ardupilot.org"
MANIFEST_URL="https://bluerobotics.github.io/BlueOS-Extensions-Repository/manifest.json"

IMAGE_PATH=""
VEHICLE_TYPE=""
FIRMWARE_VERSION=""
BOARD=""
BOARD_FROM_ARG=0
PARAM_SET=""
DRY_RUN=0
LOOP_DEVICE=""
WORK_DIR=""
EXTENSIONS=()
DOCKERD_PID=""
DOCKER_SOCK=""
MANIFEST_JSON=""
IMAGE_ROOTFS=""
RESTART_BACKUP=""
MOUNTPOINT=""

usage() {
    echo "Usage: $0 <image_path> <vehicle_type> [firmware_version] [options]"
    echo ""
    echo "Arguments:"
    echo "  image_path         Path to the BlueOS .img file"
    echo "  vehicle_type       Overlay to apply (directory overlay_<vehicle_type>/)"
    echo "  firmware_version   Optional. ArduPilot version to fetch (e.g. 4.5.3, stable-4.5.3, beta)"
    echo ""
    echo "Options:"
    echo "  --board navigator|navigator64   Autodetected from the image userland if omitted"
    echo "  --param-set NAME                Parameter set from the repository (without .params)"
    echo "  --extension ID[:TAG]            BlueOS extension to install and enable (repeatable)."
    echo "                                  Tag defaults to the newest stable manifest version."
    echo "  --dry-run                       Print firmware URL, param set, and extensions; do not write an image"
    echo ""
    echo "Examples:"
    echo "  $0 BlueOS-raspberry-linux-arm-v7-bullseye-pi4.img bluerov2 4.5.3"
    echo "  $0 BlueOS-pi5.img blueboat120 4.6.2 --board navigator64"
    echo "  $0 BlueOS-pi4.img bluerov2 4.5.3 --param-set 'Heavy BlueROV2' --dry-run"
    echo "  $0 BlueOS-pi4.img bluerov2 --extension bluerobotics.cockpit"
    echo "  $0 BlueOS-pi5.img blueboat120 4.6.2 --extension some.extension:v1.2.3 --extension another.ext"
    exit 1
}

is_mounted() {
    awk -v mp="$1" '$2 == mp { found = 1 } END { exit !found }' /proc/mounts
}

umount_nested() {
    local mp="$1"
    local mounts m
    mounts="$(awk -v mp="$mp" 'index($2, mp "/") == 1 { print $2 }' /proc/mounts | sort -r || true)"
    while IFS= read -r m; do
        [ -n "$m" ] || continue
        sudo umount "$m" || true
    done <<< "$mounts"
}

stop_image_dockerd() {
    if [ -z "${DOCKERD_PID:-}" ]; then
        return 0
    fi
    if kill -0 "$DOCKERD_PID" 2>/dev/null; then
        sudo kill "$DOCKERD_PID" 2>/dev/null || true
        local _
        for _ in $(seq 1 30); do
            kill -0 "$DOCKERD_PID" 2>/dev/null || break
            sleep 1
        done
        if kill -0 "$DOCKERD_PID" 2>/dev/null; then
            sudo kill -9 "$DOCKERD_PID" 2>/dev/null || true
        fi
    fi
    wait "$DOCKERD_PID" 2>/dev/null || true
    DOCKERD_PID=""
    return 0
}

# unless-stopped containers start with this dockerd. docker stop would mark them
# manually stopped, so BlueOS would not come back on the next real boot.
# Hold restart policy at "no" for the pull, then put the originals back once dockerd is gone.
hold_container_restarts() {
    local rootfs="$1"
    local containers="${rootfs}/var/lib/docker/containers"
    RESTART_BACKUP="${WORK_DIR}/restart-backup"
    mkdir -p "$RESTART_BACKUP"
    # /var/lib/docker is root-only, so tests and globs must go through sudo
    sudo test -d "$containers" || return 0
    local dir base
    while IFS= read -r dir; do
        [ -n "$dir" ] || continue
        base="$(basename "$dir")"
        if sudo test -f "$dir/hostconfig.json"; then
            sudo cat "$dir/hostconfig.json" | tee "$RESTART_BACKUP/${base}.hostconfig.json" >/dev/null
            jq '.RestartPolicy.Name = "no"' "$RESTART_BACKUP/${base}.hostconfig.json" \
                | sudo tee "$dir/hostconfig.json" >/dev/null
        fi
        if sudo test -f "$dir/config.v2.json"; then
            sudo cat "$dir/config.v2.json" | tee "$RESTART_BACKUP/${base}.config.v2.json" >/dev/null
            jq 'if .HostConfig.RestartPolicy then .HostConfig.RestartPolicy.Name = "no" else . end' \
                "$RESTART_BACKUP/${base}.config.v2.json" \
                | sudo tee "$dir/config.v2.json" >/dev/null
        fi
    done < <(sudo find "$containers" -mindepth 1 -maxdepth 1 -type d)
}

restore_container_restarts() {
    local rootfs="$1"
    [ -n "${RESTART_BACKUP:-}" ] || return 0
    [ -d "$RESTART_BACKUP" ] || return 0
    local backup base dest
    for backup in "$RESTART_BACKUP"/*; do
        [ -f "$backup" ] || continue
        base="$(basename "$backup")"
        case "$base" in
            *.hostconfig.json)
                dest="${rootfs}/var/lib/docker/containers/${base%.hostconfig.json}/hostconfig.json"
                ;;
            *.config.v2.json)
                dest="${rootfs}/var/lib/docker/containers/${base%.config.v2.json}/config.v2.json"
                ;;
            *) continue ;;
        esac
        sudo cp "$backup" "$dest"
    done
}

cleanup() {
    # set -e in a trap would skip the unmount if an earlier command fails
    set +e
    echo "Cleaning up..."
    stop_image_dockerd
    if [ -n "$IMAGE_ROOTFS" ] && is_mounted "$IMAGE_ROOTFS"; then
        restore_container_restarts "$IMAGE_ROOTFS"
        umount_nested "$IMAGE_ROOTFS"
        sudo umount "$IMAGE_ROOTFS" || true
    fi
    if [ -n "$LOOP_DEVICE" ] && losetup "$LOOP_DEVICE" >/dev/null 2>&1; then
        echo "Unmounting and detaching loop device: $LOOP_DEVICE"
        sudo umount "$MOUNTPOINT" 2>/dev/null || true
        sudo losetup -d "$LOOP_DEVICE" 2>/dev/null || true
    fi
    if [ -n "${WORK_DIR:-}" ] && [ "$WORK_DIR" != "/" ]; then
        rm -rf "$WORK_DIR" 2>/dev/null || sudo rm -rf "$WORK_DIR"
    fi
    return 0
}

require_cmd() {
    command -v "$1" >/dev/null 2>&1 || {
        echo "Error: '$1' is required"
        exit 1
    }
}

configure_vehicle() {
    case "$VEHICLE_TYPE" in
        bluerov2)
            AP_VEHICLE_DIR="Sub"
            AP_VEHICLE_JSON="ArduSub"
            AP_BINARY="ardusub"
            DEFAULT_PARAM_SET="Standard BlueROV2"
            ;;
        blueboat120)
            AP_VEHICLE_DIR="Rover"
            AP_VEHICLE_JSON="ArduRover"
            AP_BINARY="ardurover"
            DEFAULT_PARAM_SET="BlueBoat120"
            ;;
        *)
            echo "Error: No firmware/param mapping for vehicle '$VEHICLE_TYPE'"
            echo "Known types: bluerov2, blueboat120"
            exit 1
            ;;
    esac
    if [ -z "$PARAM_SET" ]; then
        PARAM_SET="$DEFAULT_PARAM_SET"
    fi
}

infer_board() {
    local name
    name="$(basename "$IMAGE_PATH")"
    if [[ "$name" =~ (arm64|aarch64|v8|pi5) ]]; then
        echo "navigator64"
    else
        echo "navigator"
    fi
}

# Same rule as ardupilot_manager/flight_controller_detector/linux/navigator.py: ELF class of the rootfs userland.
board_from_rootfs() {
    local elf="$1/bin/ls"
    [ -e "$elf" ] || return 1
    if [ "$(od -An -t u1 -j4 -N1 "$elf" | tr -d ' ')" = "2" ]; then
        echo "navigator64"
    else
        echo "navigator"
    fi
}

validate_board() {
    case "$BOARD" in
        navigator | navigator64) ;;
        *)
            echo "Error: --board must be navigator or navigator64 (got '$BOARD')"
            exit 1
            ;;
    esac
}

ensure_board() {
    if [ -z "$BOARD" ]; then
        BOARD="$(infer_board)"
    fi
    validate_board
}

apply_rootfs_board() {
    local rootfs="$1"
    if [ "$BOARD_FROM_ARG" -eq 0 ]; then
        if ! BOARD="$(board_from_rootfs "$rootfs")"; then
            echo "Error: could not detect board from ${rootfs}/bin/ls" >&2
            exit 1
        fi
        echo "Detected board from image userland: $BOARD"
        validate_board
    fi
}

firmware_channel() {
    local version="$1"
    case "$version" in
        stable | beta | latest) echo "$version" ;;
        stable-* | beta-* | latest-*) echo "$version" ;;
        *) echo "stable-${version}" ;;
    esac
}

# Leading X.Y or X.Y.Z from a version string (stable-4.5.3, 4.5.3-44-gabc, …)
numeric_version() {
    local src="${1:-}"
    if [ -z "$src" ]; then
        src="$(cat)"
    fi
    echo "$src" | grep -oE '[0-9]+\.[0-9]+([.][0-9]+)?' | head -n1 || true
}

firmware_url() {
    echo "${FIRMWARE_HOST}/${AP_VEHICLE_DIR}/$(firmware_channel "$FIRMWARE_VERSION")/${BOARD}/${AP_BINARY}"
}

resolve_param_version() {
    local numeric
    numeric="$(numeric_version "$FIRMWARE_VERSION")"
    if [ -n "$numeric" ]; then
        echo "$numeric"
        return
    fi
    local version_url
    version_url="${FIRMWARE_HOST}/${AP_VEHICLE_DIR}/$(firmware_channel "$FIRMWARE_VERSION")/${BOARD}/firmware-version.txt"
    echo "Firmware channel has no numeric version, reading $version_url" >&2
    numeric="$(curl -fsSL "$version_url" | numeric_version)"
    if [ -z "$numeric" ]; then
        echo "Error: could not determine numeric firmware version from $version_url" >&2
        exit 1
    fi
    echo "$numeric"
}

# Same rule as core/frontend/src/libs/parameter_repository.ts: same major, newest set <= firmware version.
select_param_key() {
    local params_json="$1"
    local fw_ver="$2"
    local wanted_set="${PARAM_SET%.params}.params"
    jq -r --arg vehicle "$AP_VEHICLE_JSON" --arg board "$BOARD" --arg set "$wanted_set" --arg fwver "$fw_ver" '
        def parse:
            split(".") | map(tonumber? // 0) | . + [0, 0, 0] | .[0:3];
        def cmp(a; b):
            if a[0] != b[0] then a[0] - b[0]
            elif a[1] != b[1] then a[1] - b[1]
            else a[2] - b[2] end;
        def lte(a; b): cmp(a; b) <= 0;
        [
            to_entries[]
            | .key as $k
            | ($k | split("/")) as $p
            | select(($p | length) == 6)
            | select($p[2] == $vehicle)
            | select(($p[4] | ascii_downcase) == ($board | ascii_downcase))
            | select($p[5] == $set)
            | ($p[3] | parse) as $pv
            | ($fwver | parse) as $fv
            | select($pv[0] == $fv[0] and lte($pv; $fv))
            | {key: $k, ver: $pv}
        ]
        | if length == 0 then empty else max_by(.ver) | .key end
    ' "$params_json"
}

list_matching_param_sets() {
    local params_json="$1"
    jq -r --arg vehicle "$AP_VEHICLE_JSON" --arg board "$BOARD" '
        to_entries[]
        | .key as $k
        | ($k | split("/")) as $p
        | select(($p | length) == 6)
        | select($p[2] == $vehicle)
        | select(($p[4] | ascii_downcase) == ($board | ascii_downcase))
        | $k
    ' "$params_json"
}

write_params_csv() {
    local params_json="$1"
    local key="$2"
    local dest="$3"
    jq -r --arg key "$key" '.[$key] | to_entries[] | "\(.key),\(.value)"' "$params_json" >"$dest"
}

# Last file wins per parameter name. Overlay extras (manufacturing tweaks) go last.
merge_params() {
    awk -F, '
        $0 ~ /^[[:space:]]*#/ { next }
        NF < 2 { next }
        {
            key = $1
            val = substr($0, index($0, ",") + 1)
            map[key] = val
            if (!(key in seen)) { order[++n] = key; seen[key] = 1 }
        }
        END { for (i = 1; i <= n; i++) print order[i] "," map[order[i]] }
    ' "$@"
}

fetch_params_file() {
    local dest="$1"
    echo "Downloading parameter repository..."
    curl -fsSL "$PARAMS_URL" -o "$dest"
}

# Newest stable semver tag. Leading v is allowed. Prereleases and non-semver tags are skipped.
# Same rule as kraken manifest.versions_from_entry(..., stable=True). Reads a versions object on stdin.
select_stable_tag() {
    jq -r '
        def parsed:
            ltrimstr("v")
            | try capture("^(?<maj>[0-9]+)\\.(?<min>[0-9]+)\\.(?<pat>[0-9]+)(?<pre>-[^+]+)?(?<build>\\+.*)?$")
              catch null;
        if . == null or type != "object" then empty
        else
            [
                to_entries[]
                | .key as $k
                | ($k | parsed) as $v
                | select($v != null and ($v.pre == null))
                | {key: $k, ver: [($v.maj | tonumber), ($v.min | tonumber), ($v.pat | tonumber)]}
            ]
            | if length == 0 then empty else max_by(.ver) | .key end
        end
    '
}

# Reads an extension entry on stdin. Empty requested tag selects the newest stable version.
# An explicit tag also matches with or without a leading v, as kraken fetch_extension_version does.
resolve_version_tag() {
    local requested="${1:-}"
    if [ -z "$requested" ]; then
        jq -c '.versions' | select_stable_tag
        return
    fi
    jq -r --arg tag "$requested" '
        .versions as $v
        | if ($v | has($tag)) then $tag
          elif ($v | has("v" + $tag)) then "v" + $tag
          elif ($tag | startswith("v")) and ($v | has($tag[1:])) then $tag[1:]
          else empty end
    '
}

platform_for_board() {
    case "$BOARD" in
        navigator) echo "linux/arm/v7" ;;
        navigator64) echo "linux/arm64" ;;
        *)
            echo "Error: --board must be navigator or navigator64 (got '$BOARD')" >&2
            exit 1
            ;;
    esac
}

# Reads one manifest version object on stdin.
version_matches_board() {
    local board="$1"
    local arch variant
    case "$board" in
        navigator)
            arch="arm"
            variant="v7"
            ;;
        navigator64)
            arch="arm64"
            variant=""
            ;;
        *) return 1 ;;
    esac
    jq -e --arg arch "$arch" --arg variant "$variant" '
        any(.images[]?;
            .platform.architecture == $arch
            and ((.platform.variant // "") == $variant)
        )
    ' >/dev/null
}

# Prints merged kraken settings. A missing settings file becomes VERSION 2 with empty manifests.
merge_extension_settings() {
    local identifier="$1"
    local name="$2"
    local docker="$3"
    local tag="$4"
    local permissions="$5"
    local settings_file="${6:-}"
    # shellcheck disable=SC2016 # jq variables, not shell
    local filter='
        def blank: {VERSION: 2, extensions: [], manifests: []};
        def entry: {
            docker: $docker,
            enabled: true,
            identifier: $identifier,
            name: $name,
            permissions: $permissions,
            tag: $tag,
            user_permissions: ""
        };
        (if type == "object" and ((.extensions | type) == "array") then . else blank end)
        | .extensions |= (
            if any(.identifier == $identifier) then
                map(if .identifier == $identifier then entry else . end)
            else
                . + [entry]
            end
        )
    '
    if [ -n "$settings_file" ] && [ -f "$settings_file" ]; then
        jq \
            --arg identifier "$identifier" \
            --arg name "$name" \
            --arg docker "$docker" \
            --arg tag "$tag" \
            --arg permissions "$permissions" \
            "$filter" \
            "$settings_file"
    else
        echo '{}' | jq \
            --arg identifier "$identifier" \
            --arg name "$name" \
            --arg docker "$docker" \
            --arg tag "$tag" \
            --arg permissions "$permissions" \
            "$filter"
    fi
}

ensure_work_dir() {
    if [ -z "${WORK_DIR:-}" ]; then
        WORK_DIR="$(mktemp -d)"
    fi
}

fetch_manifest() {
    require_cmd curl
    require_cmd jq
    ensure_work_dir
    if [ -n "${MANIFEST_JSON:-}" ] && [ -f "$MANIFEST_JSON" ]; then
        return 0
    fi
    MANIFEST_JSON="${WORK_DIR}/extensions-manifest.json"
    echo "Downloading extensions manifest..."
    curl -fsSL "$MANIFEST_URL" -o "$MANIFEST_JSON"
}

resolve_extension() {
    local spec="$1"
    local id="${spec%%:*}"
    local tag_req=""
    if [[ "$spec" == *:* ]]; then
        tag_req="${spec#*:}"
    fi
    if [ -z "$id" ] || { [[ "$spec" == *:* ]] && [ -z "$tag_req" ]; }; then
        echo "Error: --extension must be identifier or identifier:tag (got '$spec')" >&2
        exit 1
    fi

    local entry="${WORK_DIR}/entry.json"
    jq -c --arg id "$id" '
        [.[] | select(.identifier == $id)] | if length == 0 then empty else .[0] end
    ' "$MANIFEST_JSON" >"$entry"
    if [ ! -s "$entry" ]; then
        echo "Error: extension '$id' not found in the extensions manifest" >&2
        exit 1
    fi

    local tag
    tag="$(resolve_version_tag "$tag_req" <"$entry")"
    if [ -z "$tag" ]; then
        if [ -z "$tag_req" ]; then
            echo "Error: extension '$id' has no stable version" >&2
        else
            echo "Error: extension '$id' has no version '$tag_req'" >&2
        fi
        exit 1
    fi

    local version="${WORK_DIR}/version.json"
    jq -c --arg tag "$tag" '.versions[$tag]' "$entry" >"$version"
    if ! version_matches_board "$BOARD" <"$version"; then
        echo "Error: ${id}:${tag} has no image for ${BOARD}" >&2
        exit 1
    fi

    EXT_IDENTIFIER="$id"
    EXT_TAG="$tag"
    EXT_NAME="$(jq -r '.name' "$entry")"
    EXT_DOCKER="$(jq -r '.docker' "$entry")"
    EXT_PERMISSIONS="$(jq -c '.permissions // {}' "$version")"
    EXT_PLATFORM="$(platform_for_board)"
}

start_image_dockerd() {
    local rootfs="$1"
    require_cmd docker
    require_cmd dockerd
    DOCKER_SOCK="${WORK_DIR}/docker.sock"
    local exec_root="${WORK_DIR}/docker-exec"
    local daemon_json="${WORK_DIR}/daemon.json"
    mkdir -p "$exec_root"
    # Host Docker 29+ stores images in containerd. The dockerd that boots on the Pi
    # does not, so a pull through the host socket would be invisible on the image.
    cat >"$daemon_json" <<'EOF'
{
    "features": {
        "containerd-snapshotter": false
    }
}
EOF
    sudo mkdir -p "${rootfs}/var/lib/docker"
    # The redirect stays in this shell so a failed start can be read without root.
    # shellcheck disable=SC2024
    sudo dockerd \
        --config-file "$daemon_json" \
        --data-root "${rootfs}/var/lib/docker" \
        --exec-root "$exec_root" \
        --pidfile "${WORK_DIR}/dockerd.pid" \
        --host "unix://${DOCKER_SOCK}" \
        --bridge=none \
        --iptables=false \
        --ip6tables=false \
        >"${WORK_DIR}/dockerd.log" 2>&1 &
    DOCKERD_PID=$!

    local _
    for _ in $(seq 1 60); do
        if sudo docker --host "unix://${DOCKER_SOCK}" info >/dev/null 2>&1; then
            return 0
        fi
        if ! kill -0 "$DOCKERD_PID" 2>/dev/null; then
            echo "Error: dockerd exited. Log:" >&2
            tail -n 50 "${WORK_DIR}/dockerd.log" >&2 || true
            exit 1
        fi
        sleep 1
    done
    echo "Error: dockerd did not become ready. Log:" >&2
    tail -n 50 "${WORK_DIR}/dockerd.log" >&2 || true
    exit 1
}

extension_image_ref() {
    local settings_file="$1"
    local identifier="$2"
    jq -r --arg id "$identifier" '
        ((.extensions // []) | map(select(.identifier == $id)) | .[0]) as $ext
        | if $ext == null then empty else "\($ext.docker):\($ext.tag)" end
    ' "$settings_file"
}

apply_extensions() {
    local rootfs="$1"
    fetch_manifest
    local current=""
    local settings_path=""
    if [ "$DRY_RUN" -eq 0 ]; then
        hold_container_restarts "$rootfs"
        start_image_dockerd "$rootfs"
        settings_path="${rootfs}/root/.config/blueos/kraken/settings-2.json"
        current="${WORK_DIR}/kraken-settings.json"
        # /root is root-only, a plain -f would read an existing file as missing
        if sudo test -f "$settings_path"; then
            sudo cat "$settings_path" | tee "$current" >/dev/null
        else
            echo '{"VERSION":2,"extensions":[],"manifests":[]}' >"$current"
        fi
    fi

    local spec old_ref
    for spec in "${EXTENSIONS[@]}"; do
        resolve_extension "$spec"
        echo "Extension: ${EXT_IDENTIFIER} ${EXT_DOCKER}:${EXT_TAG} (${EXT_PLATFORM})"
        if [ "$DRY_RUN" -eq 1 ]; then
            continue
        fi
        old_ref="$(extension_image_ref "$current" "$EXT_IDENTIFIER")"
        echo "Pulling ${EXT_DOCKER}:${EXT_TAG}..."
        sudo docker --host "unix://${DOCKER_SOCK}" pull --platform "$EXT_PLATFORM" "${EXT_DOCKER}:${EXT_TAG}"
        if [ -n "$old_ref" ] && [ "$old_ref" != "${EXT_DOCKER}:${EXT_TAG}" ]; then
            echo "Removing previous image ${old_ref}"
            if ! sudo docker --host "unix://${DOCKER_SOCK}" image rm "$old_ref"; then
                echo "Warning: could not remove previous image ${old_ref}" >&2
            fi
        fi
        merge_extension_settings \
            "$EXT_IDENTIFIER" "$EXT_NAME" "$EXT_DOCKER" "$EXT_TAG" "$EXT_PERMISSIONS" "$current" \
            >"${WORK_DIR}/kraken-settings.next"
        mv "${WORK_DIR}/kraken-settings.next" "$current"
    done

    if [ "$DRY_RUN" -eq 0 ]; then
        sudo mkdir -p "$(dirname "$settings_path")"
        sudo cp "$current" "$settings_path"
        stop_image_dockerd
        restore_container_restarts "$rootfs"
    fi
}

apply_firmware_and_params() {
    local rootfs="$1"
    require_cmd curl
    require_cmd jq
    ensure_work_dir

    local params_json="$WORK_DIR/params_v1.json"
    local firmware_bin="$WORK_DIR/$AP_BINARY"
    local params_csv="$WORK_DIR/params.csv"
    local extra_params="${OVERLAY_DIR}/usr/blueos/userdata/firmware/extra.params"
    local fw_url
    fw_url="$(firmware_url)"
    local param_ver
    param_ver="$(resolve_param_version)"

    fetch_params_file "$params_json"
    local param_key
    param_key="$(select_param_key "$params_json" "$param_ver")"
    if [ -z "$param_key" ]; then
        echo "Error: no parameter set '${PARAM_SET}' for ${AP_VEHICLE_JSON}/${BOARD} at firmware ${param_ver}"
        echo "Available sets for this vehicle/board:"
        list_matching_param_sets "$params_json"
        exit 1
    fi

    echo "Firmware URL: $fw_url"
    echo "Parameter set: $param_key (matched firmware ${param_ver})"

    if [ "$DRY_RUN" -eq 1 ]; then
        return 0
    fi

    echo "Downloading firmware..."
    curl -fL --progress-bar "$fw_url" -o "$firmware_bin"
    chmod +x "$firmware_bin"

    write_params_csv "$params_json" "$param_key" "$params_csv"
    if [ -f "$extra_params" ]; then
        echo "Merging overlay extras from extra.params"
        merge_params "$params_csv" "$extra_params" >"$WORK_DIR/params.merged.csv"
        mv "$WORK_DIR/params.merged.csv" "$params_csv"
    fi

    local userdata="${rootfs}/usr/blueos/userdata/firmware"
    # bootstrap binds host $HOME/.config/blueos to /root/.config inside blueos-core, so the running
    # firmware lives here on the host. /root/blueos-files is inside the core image, not on the host.
    local installed_dir="${rootfs}/root/.config/blueos/ardupilot-manager/firmware"
    local other_board="navigator64"
    [ "$BOARD" = "navigator64" ] && other_board="navigator"
    sudo mkdir -p "$userdata" "$installed_dir"

    sudo cp "$firmware_bin" "${userdata}/ardupilot_${BOARD}_default"
    sudo cp "$firmware_bin" "${installed_dir}/ardupilot_${BOARD}"
    sudo chmod +x "${userdata}/ardupilot_${BOARD}_default" "${installed_dir}/ardupilot_${BOARD}"
    sudo cp "$params_csv" "${userdata}/ardupilot_${BOARD}params.params"
    sudo rm -f "${userdata}/extra.params"
    # overlays ship firmware for both boards; drop the one this image can't run so no stale build survives
    sudo rm -f "${userdata}/ardupilot_${other_board}_default" "${installed_dir}/ardupilot_${other_board}"
    # persisted ArduPilot storage beats --defaults; drop overlay .stg so the fetched params apply
    sudo rm -f "${installed_dir}/storage/"*.stg

    echo "Installed firmware to:"
    echo "  ${userdata}/ardupilot_${BOARD}_default"
    echo "  ${installed_dir}/ardupilot_${BOARD}"
    echo "Installed params to ${userdata}/ardupilot_${BOARD}params.params"
}

main() {
    trap cleanup EXIT

    while [ $# -gt 0 ]; do
        case "$1" in
            -h | --help) usage ;;
            --board)
                BOARD="$2"
                BOARD_FROM_ARG=1
                shift 2
                ;;
            --param-set)
                PARAM_SET="$2"
                shift 2
                ;;
            --extension)
                if [ $# -lt 2 ]; then
                    echo "Error: --extension requires identifier[:tag]"
                    usage
                fi
                EXTENSIONS+=("$2")
                shift 2
                ;;
            --dry-run)
                DRY_RUN=1
                shift
                ;;
            --*)
                echo "Error: unknown option $1"
                usage
                ;;
            *)
                if [ -z "$IMAGE_PATH" ]; then
                    IMAGE_PATH="$1"
                elif [ -z "$VEHICLE_TYPE" ]; then
                    VEHICLE_TYPE="$1"
                elif [ -z "$FIRMWARE_VERSION" ]; then
                    FIRMWARE_VERSION="$1"
                else
                    echo "Error: unexpected argument $1"
                    usage
                fi
                shift
                ;;
        esac
    done

    if [ -z "$IMAGE_PATH" ] || [ -z "$VEHICLE_TYPE" ]; then
        echo "Error: Missing required arguments"
        usage
    fi

    OVERLAY_DIR="${SCRIPT_DIR}/overlay_${VEHICLE_TYPE}"
    if [ ! -d "$OVERLAY_DIR" ]; then
        echo "Error: Overlay directory '$OVERLAY_DIR' not found"
        echo "Available overlay directories:"
        ls -d "${SCRIPT_DIR}"/overlay_* 2>/dev/null || echo "No overlay directories found"
        exit 1
    fi

    if [ -z "$(ls -A "$OVERLAY_DIR" 2>/dev/null)" ]; then
        echo "Error: Overlay directory '$OVERLAY_DIR' is empty"
        exit 1
    fi

    if [ "$DRY_RUN" -eq 0 ]; then
        if [ ! -f "$IMAGE_PATH" ]; then
            echo "Error: Image file '$IMAGE_PATH' not found"
            exit 1
        fi
        if [[ "$IMAGE_PATH" != *.img ]]; then
            echo "Error: File '$IMAGE_PATH' is not a .img file"
            exit 1
        fi
        IMAGE_PATH="$(cd "$(dirname "$IMAGE_PATH")" && pwd)/$(basename "$IMAGE_PATH")"
    fi

    if [ -n "$FIRMWARE_VERSION" ]; then
        configure_vehicle
    fi
    if [ -n "$FIRMWARE_VERSION" ] || [ "${#EXTENSIONS[@]}" -gt 0 ]; then
        ensure_board
    fi

    if [ "$DRY_RUN" -eq 1 ]; then
        if [ -z "$FIRMWARE_VERSION" ] && [ "${#EXTENSIONS[@]}" -eq 0 ]; then
            echo "Error: --dry-run requires a firmware version or --extension"
            exit 1
        fi
        ensure_work_dir
        if [ -n "$FIRMWARE_VERSION" ]; then
            apply_firmware_and_params ""
        fi
        if [ "${#EXTENSIONS[@]}" -gt 0 ]; then
            apply_extensions ""
        fi
        echo "Dry run complete."
        exit 0
    fi

    cd "$SCRIPT_DIR"

    local base_name customized_img
    base_name="$(basename "$IMAGE_PATH" .img)"
    customized_img="${base_name}_${VEHICLE_TYPE}_customized.img"
    MOUNTPOINT="${SCRIPT_DIR}/mountpoint"

    echo "Creating customized image: $customized_img"
    cp "$IMAGE_PATH" "$customized_img"

    mkdir -p "$MOUNTPOINT"

    echo "Setting up loop device for $customized_img..."
    LOOP_DEVICE="$(sudo losetup -fP --show "$customized_img")"
    echo "Loop device created: $LOOP_DEVICE"
    sleep 2

    echo "Available partitions:"
    ls -la "${LOOP_DEVICE}"* || true

    local root_partition="${LOOP_DEVICE}p2"
    if [ ! -e "$root_partition" ]; then
        echo "Error: Root partition $root_partition not found"
        exit 1
    fi

    echo "Mounting $root_partition to $MOUNTPOINT..."
    sudo mount "$root_partition" "$MOUNTPOINT"
    IMAGE_ROOTFS="$MOUNTPOINT"

    echo "Copying overlay files from $OVERLAY_DIR..."
    sudo cp -r "$OVERLAY_DIR"/. "$MOUNTPOINT/"
    sudo rm -f "$MOUNTPOINT/usr/blueos/userdata/firmware/extra.params"

    echo "Overlay applied successfully!"

    if [ -n "$FIRMWARE_VERSION" ] || [ "${#EXTENSIONS[@]}" -gt 0 ]; then
        apply_rootfs_board "$MOUNTPOINT"
        ensure_work_dir
    fi
    if [ "${#EXTENSIONS[@]}" -gt 0 ]; then
        apply_extensions "$MOUNTPOINT"
    fi
    if [ -n "$FIRMWARE_VERSION" ]; then
        apply_firmware_and_params "$MOUNTPOINT"
    fi

    echo "Unmounting and cleaning up..."
    stop_image_dockerd
    if is_mounted "$IMAGE_ROOTFS"; then
        restore_container_restarts "$IMAGE_ROOTFS"
        umount_nested "$IMAGE_ROOTFS"
        sudo umount "$IMAGE_ROOTFS"
    fi
    sudo losetup -d "$LOOP_DEVICE"
    LOOP_DEVICE=""
    IMAGE_ROOTFS=""

    echo ""
    echo "Image customization complete!"
    echo "Customized image: $customized_img"
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    main "$@"
fi
