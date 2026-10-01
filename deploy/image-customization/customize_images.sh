#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PARAMS_URL="https://docs.bluerobotics.com/Blueos-Parameter-Repository/params_v1.json"
FIRMWARE_HOST="https://firmware.ardupilot.org"

IMAGE_PATH=""
VEHICLE_TYPE=""
FIRMWARE_VERSION=""
BOARD=""
BOARD_FROM_ARG=0
PARAM_SET=""
DRY_RUN=0
LOOP_DEVICE=""
WORK_DIR=""

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
    echo "  --dry-run                       Print firmware URL and param set, do not write an image"
    echo ""
    echo "Examples:"
    echo "  $0 BlueOS-raspberry-linux-arm-v7-bullseye-pi4.img bluerov2 4.5.3"
    echo "  $0 BlueOS-pi5.img blueboat120 4.6.2 --board navigator64"
    echo "  $0 BlueOS-pi4.img bluerov2 4.5.3 --param-set 'Heavy BlueROV2' --dry-run"
    exit 1
}

cleanup() {
    echo "Cleaning up..."
    if [ -n "${WORK_DIR:-}" ]; then
        rm -rf "$WORK_DIR"
    fi
    if [ -n "$LOOP_DEVICE" ] && losetup "$LOOP_DEVICE" >/dev/null 2>&1; then
        echo "Unmounting and detaching loop device: $LOOP_DEVICE"
        sudo umount ./mountpoint 2>/dev/null || true
        sudo losetup -d "$LOOP_DEVICE" 2>/dev/null || true
    fi
}

trap cleanup EXIT

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

# --- args ---
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
    if [ -z "$BOARD" ]; then
        BOARD="$(infer_board)"
    fi
    case "$BOARD" in
        navigator | navigator64) ;;
        *)
            echo "Error: --board must be navigator or navigator64 (got '$BOARD')"
            exit 1
            ;;
    esac
elif [ "$DRY_RUN" -eq 1 ]; then
    echo "Error: --dry-run requires a firmware version"
    exit 1
fi

apply_firmware_and_params() {
    local rootfs="$1"
    require_cmd curl
    require_cmd jq

    if [ "$BOARD_FROM_ARG" -eq 0 ] && [ -n "$rootfs" ]; then
        BOARD="$(board_from_rootfs "$rootfs")"
        echo "Detected board from image userland: $BOARD"
    fi

    WORK_DIR="$(mktemp -d)"
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

if [ -n "$FIRMWARE_VERSION" ] && [ "$DRY_RUN" -eq 1 ]; then
    apply_firmware_and_params ""
    rm -rf "$WORK_DIR"
    echo "Dry run complete."
    exit 0
fi

cd "$SCRIPT_DIR"

BASE_NAME="$(basename "$IMAGE_PATH" .img)"
CUSTOMIZED_IMG_NAME="${BASE_NAME}_${VEHICLE_TYPE}_customized.img"

echo "Creating customized image: $CUSTOMIZED_IMG_NAME"
cp "$IMAGE_PATH" "$CUSTOMIZED_IMG_NAME"

mkdir -p ./mountpoint

echo "Setting up loop device for $CUSTOMIZED_IMG_NAME..."
LOOP_DEVICE="$(sudo losetup -fP --show "$CUSTOMIZED_IMG_NAME")"
echo "Loop device created: $LOOP_DEVICE"
sleep 2

echo "Available partitions:"
ls -la "${LOOP_DEVICE}"* || true

ROOT_PARTITION="${LOOP_DEVICE}p2"
if [ ! -e "$ROOT_PARTITION" ]; then
    echo "Error: Root partition $ROOT_PARTITION not found"
    exit 1
fi

echo "Mounting $ROOT_PARTITION to ./mountpoint..."
sudo mount "$ROOT_PARTITION" ./mountpoint

echo "Copying overlay files from $OVERLAY_DIR..."
sudo cp -r "$OVERLAY_DIR"/. ./mountpoint/
sudo rm -f ./mountpoint/usr/blueos/userdata/firmware/extra.params

echo "Overlay applied successfully!"

if [ -n "$FIRMWARE_VERSION" ]; then
    apply_firmware_and_params ./mountpoint
    rm -rf "$WORK_DIR"
fi

echo "Unmounting and cleaning up..."
sudo umount ./mountpoint
sudo losetup -d "$LOOP_DEVICE"
LOOP_DEVICE=""

echo ""
echo "Image customization complete!"
echo "Customized image: $CUSTOMIZED_IMG_NAME"
