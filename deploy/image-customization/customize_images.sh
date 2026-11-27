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
EXTENSION_ENABLED=()
DOCKERD_PID=""
DOCKER_SOCK=""
MANIFEST_JSON=""
IMAGE_ROOTFS=""
RESTART_BACKUP=""
MOUNTPOINT=""
SIZE_ARG=""
IMAGE_SIZE=""
EXPAND_FS=1
OUTPUT_PATH=""
COMPRESS=""

usage() {
    echo "Usage: $0 <image_path> <vehicle_type> <firmware_version> [options]"
    echo ""
    echo "Arguments:"
    echo "  image_path         Path to the BlueOS .img file"
    echo "  vehicle_type       Overlay to apply (directory overlay_<vehicle_type>/)"
    echo "  firmware_version   ArduPilot version to fetch (e.g. 4.5.3, stable-4.5.3, beta)"
    echo ""
    echo "Options:"
    echo "  --board navigator|navigator64   Autodetected from the image userland if omitted"
    echo "  --param-set NAME                Parameter set from the repository (without .params)"
    echo "  --extension ID[:TAG]            Install the image and enable it (repeatable)."
    echo "  --extension-disabled ID[:TAG]   Install the image but leave it disabled (repeatable)."
    echo "                                  Tag defaults to the newest stable manifest version."
    echo "  --size SIZE                     Grow the image to SIZE bytes (IEC suffixes allowed, e.g. 113G),"
    echo "                                  rounded down to 1 MiB. Must not be smaller than the image. Implies --no-expand."
    echo "  --no-expand                     Install expand_fs.service but leave it disabled, the partition is never grown"
    echo "  --output PATH                   Output .img path (default: <image>_<vehicle_type>_customized.img here)"
    echo "  --compress zip|xz               Trim free space, then write PATH.zip or PATH.img.xz plus .sha256 files"
    echo "  --dry-run                       Print firmware URL, param set, and extensions; do not write an image"
    echo ""
    echo "Examples:"
    echo "  $0 BlueOS-raspberry-linux-arm-v7-bullseye-pi4.img bluerov2 4.5.3"
    echo "  $0 BlueOS-pi5.img blueboat120 4.6.2 --board navigator64"
    echo "  $0 BlueOS-pi4.img bluerov2 4.5.3 --param-set 'Heavy BlueROV2' --dry-run"
    echo "  $0 BlueOS-pi4.img bluerov2 4.5.3 --extension bluerobotics.cockpit"
    echo "  $0 BlueOS-pi5.img blueboat120 4.6.2 --extension some.extension:v1.2.3 --extension-disabled another.ext"
    echo "  $0 BlueOS-pi4.img bluerov2 4.7.3 --size 113G --output /tmp/production.img --compress zip"
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
    local enabled="${6:-true}"
    local settings_file="${7:-}"
    # shellcheck disable=SC2016 # jq variables, not shell
    local filter='
        def blank: {VERSION: 2, extensions: [], manifests: []};
        def entry: {
            docker: $docker,
            enabled: $enabled,
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
            --argjson enabled "$enabled" \
            "$filter" \
            "$settings_file"
    else
        echo '{}' | jq \
            --arg identifier "$identifier" \
            --arg name "$name" \
            --arg docker "$docker" \
            --arg tag "$tag" \
            --arg permissions "$permissions" \
            --argjson enabled "$enabled" \
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

    local i spec enabled old_ref state
    for i in "${!EXTENSIONS[@]}"; do
        spec="${EXTENSIONS[$i]}"
        enabled="${EXTENSION_ENABLED[$i]}"
        resolve_extension "$spec"
        state="enabled"
        [ "$enabled" = "true" ] || state="disabled"
        echo "Extension: ${EXT_IDENTIFIER} ${EXT_DOCKER}:${EXT_TAG} (${EXT_PLATFORM}, ${state})"
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
            "$EXT_IDENTIFIER" "$EXT_NAME" "$EXT_DOCKER" "$EXT_TAG" "$EXT_PERMISSIONS" "$enabled" "$current" \
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

# Expects the boot partition mounted at rootfs/boot
prepare_first_boot() {
    local rootfs="$1"
    local cmdline="${rootfs}/boot/cmdline.txt"
    if [ ! -f "$cmdline" ]; then
        echo "Error: $cmdline not found" >&2
        exit 1
    fi
    # init_resize.sh reboots even when the partition already fills the card, expand_fs.service grows it online instead
    sudo sed -i -E 's# init=/usr/lib/raspi-config/init_resize\.sh( |$)#\1#; s# quiet( |$)#\1#' "$cmdline"
    sudo install -m 755 "${SCRIPT_DIR}/../expand_fs.sh" "${rootfs}/usr/bin/expand_fs.sh"
    sudo install -m 644 "${SCRIPT_DIR}/files/expand_fs.service" "${rootfs}/etc/systemd/system/expand_fs.service"
    local expand_wants="${rootfs}/etc/systemd/system/multi-user.target.wants/expand_fs.service"
    if [ "$EXPAND_FS" -eq 1 ]; then
        sudo ln -sf /etc/systemd/system/expand_fs.service "$expand_wants"
    else
        # production images are built at their final size, the unit must keep the partition as shipped
        sudo rm -f "$expand_wants"
    fi
    # Raspberry Pi OS one-shot that only runs resize2fs, which expand_fs.sh already does (or is not wanted)
    sudo rm -f "${rootfs}/etc/init.d/resize2fs_once" "${rootfs}"/etc/rc?.d/[SK]??resize2fs_once

    # fake-hwclock restores this before NTP syncs; the stock 2022 date would stamp first boot host keys and logs
    if [ -f "${rootfs}/etc/fake-hwclock.data" ]; then
        date -u '+%Y-%m-%d %H:%M:%S' | sudo tee "${rootfs}/etc/fake-hwclock.data" >/dev/null
    fi

    # bcm_27xx.sh reboots as soon as an EEPROM update is staged in /boot. The bootloader applies it on the next boot.
    local eeprom="${rootfs}/lib/systemd/system/rpi-eeprom-update.service"
    if [ -f "$eeprom" ]; then
        sudo sed -i '/^ExecStart=.*rpi-eeprom-update.*reboot/c\ExecStart=/usr/bin/rpi-eeprom-update -a -d' "$eeprom"
        if grep -q reboot "$eeprom"; then
            echo "Error: $eeprom still reboots" >&2
            exit 1
        fi
    fi
}

# Value KEY is left with after sourcing a dphys-swapfile config (last assignment wins), FALLBACK when unset.
# The image's file is parsed instead of sourced so none of it runs on the build host.
dphys_conf_value() {
    local conf="$1"
    local key="$2"
    local fallback="${3:-}"
    awk -v key="$key" -v fallback="$fallback" '
        { sub(/^[[:space:]]+/, "") }
        index($0, key "=") == 1 {
            v = substr($0, length(key) + 2)
            sub(/[[:space:]]+#.*$/, "", v)
            sub(/[[:space:]]+$/, "", v)
            gsub(/^["\047]|["\047]$/, "", v)
            found = 1
        }
        END { print (found ? v : fallback) }
    ' "$conf"
}

# dphys-swapfile dd's its whole swap file on first boot, ~40 s of SD IO fighting containerd.
# Its setup keeps an existing file whose byte size is CONF_SWAPSIZE MiB, so writing that file here skips the work.
prepare_swapfile() {
    local rootfs="$1"
    local conf="${rootfs}/etc/dphys-swapfile"
    if [ ! -f "$conf" ] || [ ! -f "${rootfs}/sbin/dphys-swapfile" ] \
        || ! sudo test -L "${rootfs}/etc/systemd/system/multi-user.target.wants/dphys-swapfile.service"; then
        echo "Note: dphys-swapfile is not installed and enabled in the image, no swap file prepared"
        return 0
    fi
    # Pi 5 kernels use 16 KiB pages and reject a 4 KiB swap header, and dphys-swapfile would keep the file anyway
    if [ -e "${rootfs}/boot/kernel_2712.img" ]; then
        echo "Note: image ships the 16 KiB page Pi 5 kernel, swap file left to dphys-swapfile"
        return 0
    fi
    local swapfile size maxswap
    swapfile="$(dphys_conf_value "$conf" CONF_SWAPFILE /var/swap)"
    size="$(dphys_conf_value "$conf" CONF_SWAPSIZE)"
    maxswap="$(dphys_conf_value "$conf" CONF_MAXSWAP 2048)"
    if [ -z "$size" ]; then
        echo "Note: CONF_SWAPSIZE is empty, swap size depends on the unit's RAM and can't be precomputed"
        return 0
    fi
    if ! [[ "$size" =~ ^[1-9][0-9]*$ && "$maxswap" =~ ^[0-9]*$ && "$swapfile" == /* ]]; then
        echo "Error: unsupported dphys-swapfile config in $conf" \
            "(CONF_SWAPFILE='$swapfile' CONF_SWAPSIZE='$size' CONF_MAXSWAP='$maxswap')" >&2
        exit 1
    fi
    # an empty CONF_MAXSWAP means no limit
    if [ -n "$maxswap" ] && [ "$size" -gt "$maxswap" ]; then
        size="$maxswap"
    fi

    local file="${rootfs}${swapfile}"
    local avail current=0
    avail="$(df -m --output=avail "$(dirname "$file")" | tail -n 1 | tr -d ' ')"
    if sudo test -f "$file"; then
        current=$(($(sudo stat -c %s "$file") / 1048576))
    fi
    # dphys-swapfile caps the size at 50% of free space plus the current file. Below 2x it would shrink and
    # rewrite the file on first boot. The 6G stock image has ~2.4G free, plenty for the overlays' 1024 MiB.
    if [ $((avail + current)) -lt $((size * 2)) ]; then
        echo "Error: a ${size} MiB swap file needs $((size * 2)) MiB free on the image rootfs," \
            "only $((avail + current)) MiB available. Use --size or lower CONF_SWAPSIZE" >&2
        exit 1
    fi

    # swapon rejects files with holes, so write real zeros instead of fallocate
    sudo rm -f "$file"
    sudo dd if=/dev/zero of="$file" bs=1M count="$size" conv=fsync status=none
    sudo chown root:root "$file"
    sudo chmod 600 "$file"
    # Every flashed unit shares this header. Nothing refers to swap by UUID, a cleared one just avoids a shared value.
    if ! sudo mkswap -p 4096 -U clear "$file" >/dev/null 2>&1; then
        sudo mkswap -p 4096 "$file" >/dev/null
    fi

    local nblocks bsize
    read -r nblocks bsize < <(sudo stat -c '%b %B' "$file")
    if [ "$(sudo stat -c %s "$file")" -ne $((size * 1048576)) ] || [ $((nblocks * bsize)) -lt $((size * 1048576)) ] \
        || [ "$(sudo blkid -p -o value -s TYPE "$file")" != "swap" ]; then
        echo "Error: $file is not a fully allocated ${size} MiB swap file" >&2
        exit 1
    fi

    # same comment lines dphys-swapfile appends to fstab when it creates the file
    local fstab="${rootfs}/etc/fstab"
    local note1="# a swapfile is not a swap partition, no line here"
    local note2="#   use  dphys-swapfile swap[on|off]  for that"
    local kept
    kept="$(sudo grep -vxF -e "$note1" -e "$note2" "$fstab" || true)"
    {
        [ -z "$kept" ] || printf '%s\n' "$kept"
        printf '%s\n' "$note1" "$note2"
    } | sudo tee "$fstab" >/dev/null

    echo "Prepared swap file ${swapfile} (${size} MiB)"
}

# Prints SIZE in bytes, rounded down to 1 MiB so the grown partition still ends on a MiB boundary
parse_image_size() {
    local size="$1"
    local current="${2:-0}"
    local bytes
    if ! bytes="$(numfmt --from=iec "$size" 2>/dev/null)" || ! [[ "$bytes" =~ ^[0-9]+$ ]]; then
        echo "Error: --size must be bytes or a K/M/G/T size (got '$size')" >&2
        exit 1
    fi
    bytes=$((bytes / 1048576 * 1048576))
    if [ "$bytes" -eq 0 ] || [ "$bytes" -lt "$current" ]; then
        echo "Error: --size $size (${bytes} bytes) is smaller than the image (${current} bytes)" >&2
        exit 1
    fi
    echo "$bytes"
}

# Grows the image file and its root partition to SIZE, so the unit never resizes on first boot.
# The image stays sparse. PARTUUIDs in cmdline.txt and fstab derive from the disk identifier, so it must survive.
grow_image_offline() {
    local img="$1"
    local size="$2"
    local disk_id
    disk_id="$(sfdisk --disk-id "$img")"
    truncate -s "$size" "$img"
    echo ", +" | sfdisk --no-reread --no-tell-kernel --wipe never --wipe-partitions never -N 2 "$img"
    if [ "$(sfdisk --disk-id "$img")" != "$disk_id" ]; then
        echo "Error: sfdisk changed the disk identifier of $img" >&2
        exit 1
    fi
}

# resize2fs refuses an unmounted filesystem that was not checked first
resize_rootfs_offline() {
    local part="$1"
    local rc=0
    # 1 means e2fsck fixed something and the filesystem is now clean
    sudo e2fsck -f -p "$part" || rc=$?
    if [ "$rc" -gt 1 ]; then
        echo "Error: e2fsck on $part failed with exit code $rc" >&2
        exit 1
    fi
    sudo resize2fs "$part"
}

# find runs as root since most of the rootfs is root-only. Extra arguments are find tests, -mindepth 1 is implied.
remove_found() {
    local rootfs="$1"
    local dir="${rootfs}/$2"
    shift 2
    sudo test -d "$dir" || return 0
    local f
    while IFS= read -r -d '' f; do
        echo "Removing ${f#"${rootfs}/"}"
        sudo rm -rf "$f"
    done < <(sudo find "$dir" -mindepth 1 "$@" -print0)
}

# Drops the BlueOS core key that is about to be deleted. Keys shipped on purpose stay.
remove_core_authorized_key() {
    local rootfs="$1"
    local pub="${rootfs}/root/.config/blueos/.ssh/id_rsa.pub"
    local keys="${rootfs}/home/pi/.ssh/authorized_keys"
    if ! sudo test -f "$pub" || ! sudo test -f "$keys"; then
        return 0
    fi
    local key remaining
    key="$(sudo awk '{ print $2; exit }' "$pub")"
    if [ -z "$key" ] || ! sudo grep -qF -- "$key" "$keys"; then
        return 0
    fi
    remaining="$(sudo grep -vF -- "$key" "$keys" || true)"
    if [ -z "${remaining//[[:space:]]/}" ]; then
        echo "Removing home/pi/.ssh/authorized_keys (only held the BlueOS core key)"
        sudo rm -f "$keys"
    else
        echo "Removing the BlueOS core key from home/pi/.ssh/authorized_keys"
        printf '%s\n' "$remaining" | sudo tee "$keys" >/dev/null
    fi
}

# Every unit flashed from this image must generate its own identity on first boot. Anything the build
# (overlays, dockerd, chroot tools) left behind would otherwise be shared by all of them.
sanitize_identity() {
    local rootfs="$1"
    # an empty rootfs would point the removals below at the build host
    if [ -z "$rootfs" ] || [ "$rootfs" = "/" ]; then
        echo "Error: sanitize_identity needs an image rootfs (got '$rootfs')" >&2
        exit 1
    fi
    local machine_id="${rootfs}/etc/machine-id"
    local id=""
    if sudo test -f "$machine_id"; then
        id="$(sudo cat "$machine_id")"
    fi
    if ! sudo test -f "$machine_id" || { [ -n "$id" ] && [ "$id" != "uninitialized" ]; }; then
        # systemd's first boot marker, the stock image ships it
        echo "Resetting etc/machine-id to uninitialized"
        echo "uninitialized" | sudo tee "$machine_id" >/dev/null
    fi
    local dbus_id="${rootfs}/var/lib/dbus/machine-id"
    if sudo test -f "$dbus_id" && ! sudo test -L "$dbus_id"; then
        echo "Replacing var/lib/dbus/machine-id with a link to /etc/machine-id"
        sudo ln -sf /etc/machine-id "$dbus_id"
    fi

    remove_found "$rootfs" etc/ssh -maxdepth 1 -name 'ssh_host_*'
    local regen="regenerate_ssh_host_keys.service"
    local regen_wants="${rootfs}/etc/systemd/system/multi-user.target.wants/${regen}"
    # the unit disables itself after creating the keys, so it must be enabled again
    if [ -f "${rootfs}/lib/systemd/system/${regen}" ] && ! sudo test -L "$regen_wants"; then
        echo "Enabling ${regen}"
        sudo mkdir -p "$(dirname "$regen_wants")"
        sudo ln -sf "/lib/systemd/system/${regen}" "$regen_wants"
    fi

    # dockerd writes engine-id when it starts, so this runs after the extensions pull
    remove_found "$rootfs" var/lib/docker -maxdepth 1 -name engine-id
    local log
    if sudo test -d "${rootfs}/var/lib/docker/containers"; then
        while IFS= read -r -d '' log; do
            echo "Truncating ${log#"${rootfs}/"}"
            sudo truncate -s 0 "$log"
        done < <(sudo find "${rootfs}/var/lib/docker/containers" -mindepth 2 -maxdepth 2 -name '*-json.log' -size +0 -print0)
    fi

    # BlueOS core generates this pair per unit and authorizes the public key for pi
    remove_core_authorized_key "$rootfs"
    remove_found "$rootfs" root/.config/blueos/.ssh -maxdepth 1 \( -name id_rsa -o -name id_rsa.pub \)

    remove_found "$rootfs" var/lib/systemd -maxdepth 1 -name random-seed
    remove_found "$rootfs" var/lib/dhcpcd -maxdepth 1 -name '*.lease*'
    remove_found "$rootfs" var/lib/dhcpcd5 -maxdepth 1 -name '*.lease*'
    remove_found "$rootfs" root -maxdepth 1 -name .bash_history
    remove_found "$rootfs" home -maxdepth 2 -name .bash_history
    remove_found "$rootfs" tmp -maxdepth 1
    remove_found "$rootfs" var/tmp -maxdepth 1
}

attach_image() {
    local img="$1"
    echo "Setting up loop device for $img..."
    LOOP_DEVICE="$(sudo losetup -fP --show "$img")"
    echo "Loop device created: $LOOP_DEVICE"
    sleep 2

    echo "Available partitions:"
    ls -la "${LOOP_DEVICE}"* || true

    if [ ! -e "${LOOP_DEVICE}p2" ]; then
        echo "Error: Root partition ${LOOP_DEVICE}p2 not found"
        exit 1
    fi
}

mount_image() {
    echo "Mounting ${LOOP_DEVICE}p2 to $MOUNTPOINT..."
    sudo mount "${LOOP_DEVICE}p2" "$MOUNTPOINT"
    IMAGE_ROOTFS="$MOUNTPOINT"
    sudo mount "${LOOP_DEVICE}p1" "$MOUNTPOINT/boot"
}

detach_image() {
    if is_mounted "$IMAGE_ROOTFS"; then
        restore_container_restarts "$IMAGE_ROOTFS"
        umount_nested "$IMAGE_ROOTFS"
        sudo umount "$IMAGE_ROOTFS"
    fi
    sudo losetup -d "$LOOP_DEVICE"
    LOOP_DEVICE=""
    IMAGE_ROOTFS=""
}

# Discards on a loop device punch holes in the file, so free space stays sparse and compresses to nothing.
# zerofree is not available on the build hosts. fstrim only discards free blocks, the written swap file stays.
trim_image() {
    local img="$1"
    attach_image "$img"
    mount_image
    sudo fstrim -v "$MOUNTPOINT/boot" || echo "Warning: could not trim the boot partition" >&2
    sudo fstrim -v "$MOUNTPOINT"
    detach_image
}

# Checksums hold basenames so they verify from wherever the files are copied to
compress_image() {
    local img="$1"
    local dir name out
    dir="$(dirname "$img")"
    name="$(basename "$img")"
    case "$COMPRESS" in
        zip) out="${name%.img}.zip" ;;
        xz) out="${name}.xz" ;;
    esac
    (
        cd "$dir"
        # zip would add to a stale archive instead of replacing it
        rm -f "$out"
        echo "Compressing $name to $out..."
        case "$COMPRESS" in
            zip) zip -9 -j "$out" "$name" ;;
            xz) xz -T0 -9 -k "$name" ;;
        esac
        sha256sum "$name" >"${name}.sha256"
        sha256sum "$out" >"${out}.sha256"
    )
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
            --extension | --extension-disabled)
                if [ $# -lt 2 ]; then
                    echo "Error: $1 requires identifier[:tag]"
                    usage
                fi
                EXTENSIONS+=("$2")
                if [ "$1" = "--extension" ]; then
                    EXTENSION_ENABLED+=(true)
                else
                    EXTENSION_ENABLED+=(false)
                fi
                shift 2
                ;;
            --size | --output | --compress)
                if [ $# -lt 2 ]; then
                    echo "Error: $1 requires a value"
                    usage
                fi
                case "$1" in
                    --size)
                        parse_image_size "$2" >/dev/null
                        SIZE_ARG="$2"
                        EXPAND_FS=0
                        ;;
                    --output)
                        if [[ "$2" != *.img ]]; then
                            echo "Error: --output must end in .img (got '$2')"
                            exit 1
                        fi
                        OUTPUT_PATH="$2"
                        ;;
                    --compress)
                        if [ "$2" != "zip" ] && [ "$2" != "xz" ]; then
                            echo "Error: --compress must be zip or xz (got '$2')"
                            exit 1
                        fi
                        COMPRESS="$2"
                        ;;
                esac
                shift 2
                ;;
            --no-expand)
                EXPAND_FS=0
                shift
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

    if [ -z "$IMAGE_PATH" ] || [ -z "$VEHICLE_TYPE" ] || [ -z "$FIRMWARE_VERSION" ]; then
        echo "Error: image, vehicle type, and ArduPilot version are required"
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
        if [ -n "$OUTPUT_PATH" ]; then
            if [ ! -d "$(dirname "$OUTPUT_PATH")" ]; then
                echo "Error: Output directory '$(dirname "$OUTPUT_PATH")' not found"
                exit 1
            fi
            # main works from SCRIPT_DIR, a relative --output must stay relative to the caller
            OUTPUT_PATH="$(cd "$(dirname "$OUTPUT_PATH")" && pwd)/$(basename "$OUTPUT_PATH")"
        fi
        if [ -n "$SIZE_ARG" ]; then
            IMAGE_SIZE="$(parse_image_size "$SIZE_ARG" "$(stat -c %s "$IMAGE_PATH")")"
        fi
        if [ -n "$COMPRESS" ]; then
            require_cmd "$COMPRESS"
        fi
    elif [ -n "$SIZE_ARG" ]; then
        IMAGE_SIZE="$(parse_image_size "$SIZE_ARG")"
    fi

    configure_vehicle
    ensure_board

    if [ "$DRY_RUN" -eq 1 ]; then
        if [ -n "$IMAGE_SIZE" ]; then
            echo "Image size: ${IMAGE_SIZE} bytes"
        fi
        if [ "$EXPAND_FS" -eq 0 ]; then
            echo "expand_fs.service: disabled"
        fi
        if [ -n "$COMPRESS" ]; then
            echo "Compression: $COMPRESS"
        fi
        ensure_work_dir
        apply_firmware_and_params ""
        if [ "${#EXTENSIONS[@]}" -gt 0 ]; then
            apply_extensions ""
        fi
        echo "Dry run complete."
        exit 0
    fi

    cd "$SCRIPT_DIR"

    local base_name customized_img
    base_name="$(basename "$IMAGE_PATH" .img)"
    customized_img="${OUTPUT_PATH:-${base_name}_${VEHICLE_TYPE}_customized.img}"
    MOUNTPOINT="${SCRIPT_DIR}/mountpoint"

    echo "Creating customized image: $customized_img"
    cp "$IMAGE_PATH" "$customized_img"
    if [ -n "$IMAGE_SIZE" ]; then
        echo "Growing $customized_img to ${IMAGE_SIZE} bytes..."
        grow_image_offline "$customized_img" "$IMAGE_SIZE"
    fi

    mkdir -p "$MOUNTPOINT"

    attach_image "$customized_img"
    if [ -n "$IMAGE_SIZE" ]; then
        resize_rootfs_offline "${LOOP_DEVICE}p2"
    fi
    mount_image

    echo "Copying overlay files from $OVERLAY_DIR..."
    sudo cp -r "$OVERLAY_DIR"/. "$MOUNTPOINT/"
    sudo rm -f "$MOUNTPOINT/usr/blueos/userdata/firmware/extra.params"

    echo "Overlay applied successfully!"

    prepare_first_boot "$MOUNTPOINT"

    apply_rootfs_board "$MOUNTPOINT"
    ensure_work_dir
    if [ "${#EXTENSIONS[@]}" -gt 0 ]; then
        apply_extensions "$MOUNTPOINT"
    fi
    apply_firmware_and_params "$MOUNTPOINT"
    stop_image_dockerd
    prepare_swapfile "$MOUNTPOINT"

    echo "Unmounting and cleaning up..."
    sanitize_identity "$MOUNTPOINT"
    detach_image

    if [ -n "$IMAGE_SIZE" ] || [ -n "$COMPRESS" ]; then
        trim_image "$customized_img"
    fi
    if [ -n "$COMPRESS" ]; then
        compress_image "$customized_img"
    fi

    echo ""
    echo "Image customization complete!"
    echo "Customized image: $customized_img"
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    main "$@"
fi
