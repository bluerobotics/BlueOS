#!/bin/bash

set -e  # Exit on any error

# Function to display usage
usage() {
    echo "Usage: $0 <image_path> <vehicle_type>"
    echo ""
    echo "Arguments:"
    echo "  image_path   - Path to the BlueOS .img file (e.g., BlueOS-raspberry-linux-arm64-v8-bookworm-pi5.img)"
    echo "  vehicle_type - Vehicle type for overlay selection (e.g., bb120, bluerov2), this will be used to select the overlay directory"
    echo ""
    echo "Example:"
    echo "  $0 BlueOS-raspberry-linux-arm64-v8-bookworm-pi5.img boat"
    exit 1
}

# Function to cleanup on exit
cleanup() {
    echo "Cleaning up..."
    if [ -n "$LOOP_DEVICE" ] && losetup "$LOOP_DEVICE" >/dev/null 2>&1; then
        echo "Unmounting and detaching loop device: $LOOP_DEVICE"
        sudo umount ./mountpoint 2>/dev/null || true
        sudo losetup -d "$LOOP_DEVICE" 2>/dev/null || true
    fi
}

# Set trap for cleanup
trap cleanup EXIT

# Check arguments
if [ $# -ne 2 ]; then
    echo "Error: Missing required arguments"
    usage
fi

IMAGE_PATH="$1"
VEHICLE_TYPE="$2"

# Validate that the image file exists and is a .img file
if [ ! -f "$IMAGE_PATH" ]; then
    echo "Error: Image file '$IMAGE_PATH' not found"
    exit 1
fi

if [[ "$IMAGE_PATH" != *.img ]]; then
    echo "Error: File '$IMAGE_PATH' is not a .img file"
    exit 1
fi

# Validate that overlay directory exists
OVERLAY_DIR="overlay_${VEHICLE_TYPE}"
if [ ! -d "$OVERLAY_DIR" ]; then
    echo "Error: Overlay directory '$OVERLAY_DIR' not found"
    echo "Available overlay directories:"
    ls -d blueos_*_overlay 2>/dev/null || echo "No overlay directories found"
    exit 1
fi

# Validate that overlay directory contains files
if [ -z "$(ls -A "$OVERLAY_DIR" 2>/dev/null)" ]; then
    echo "Error: Overlay directory '$OVERLAY_DIR' is empty"
    exit 1
fi

# Extract base filename without extension and path
BASE_NAME=$(basename "$IMAGE_PATH" .img)

# Create meaningful name for the customized image
CUSTOMIZED_IMG_NAME="${BASE_NAME}_${VEHICLE_TYPE}_customized.img"

# Copy the original image to the new name
echo "Creating customized image: $CUSTOMIZED_IMG_NAME"
cp "$IMAGE_PATH" "$CUSTOMIZED_IMG_NAME"

echo "Using image file: $CUSTOMIZED_IMG_NAME"

# Create mountpoint directory if it doesn't exist
mkdir -p ./mountpoint

# Setup loop device
echo "Setting up loop device for $CUSTOMIZED_IMG_NAME..."
LOOP_DEVICE=$(sudo losetup -fP --show "$CUSTOMIZED_IMG_NAME")
echo "Loop device created: $LOOP_DEVICE"

# Wait a moment for the partitions to be recognized
sleep 2

# List available partitions
echo "Available partitions:"
ls -la "${LOOP_DEVICE}"* || true

# Mount the root filesystem (usually partition 2 for Raspberry Pi images)
ROOT_PARTITION="${LOOP_DEVICE}p2"
if [ ! -e "$ROOT_PARTITION" ]; then
    echo "Error: Root partition $ROOT_PARTITION not found"
    exit 1
fi

echo "Mounting $ROOT_PARTITION to ./mountpoint..."
sudo mount "$ROOT_PARTITION" ./mountpoint

# Copy overlay files
echo "Copying overlay files from $OVERLAY_DIR..."
sudo cp -r "$OVERLAY_DIR"/* ./mountpoint/

echo "Overlay applied successfully!"

# Automatically unmount and cleanup
echo "Unmounting and cleaning up..."
sudo umount ./mountpoint
sudo losetup -d "$LOOP_DEVICE"


echo ""
echo "Image customization complete!"
echo "Customized image: $CUSTOMIZED_IMG_NAME"
echo "The loop device will be automatically unmounted and detached."


