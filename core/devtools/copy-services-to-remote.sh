#!/bin/bash

set -e

# Default values
USER="pi"
HOST=""
SERVICE=""
CONTAINER_NAME="blueos-core"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICES_DIR="$(cd "$SCRIPT_DIR/../services" && pwd)"

# Colors for output
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Copy service files from local services folder to a remote BlueOS container.

OPTIONS:
    -u, --user USER         SSH user (default: pi)
    -h, --host HOST         Remote host (required)
    -s, --service SERVICE   Specific service to copy (optional, copies all if not specified)
    --help                  Show this help message

EXAMPLES:
    # Copy a specific service
    $0 --host blueos.local --service ardupilot_manager

    # Copy all services
    $0 --host 192.168.2.2 --user pi

SSH KEY SETUP:
    This script requires SSH key-based authentication.
    To set up SSH keys on the remote host, run:

        ssh-copy-id pi@blueos.local

    Or if using a different user:

        ssh-copy-id <user>@<host>

    This will copy your public SSH key to the remote host and allow
    password-less authentication.

EOF
    exit 1
}

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -u|--user)
            USER="$2"
            shift 2
            ;;
        -h|--host)
            HOST="$2"
            shift 2
            ;;
        -s|--service)
            SERVICE="$2"
            shift 2
            ;;
        -p|--password)
            log_warning "Password authentication is not supported. Please use SSH keys instead."
            log_info "Run: ssh-copy-id $USER@$HOST"
            exit 1
            ;;
        --help)
            usage
            ;;
        *)
            log_error "Unknown option: $1"
            usage
            ;;
    esac
done

# Validate required arguments
if [ -z "$HOST" ]; then
    log_error "Remote host is required"
    usage
fi

# Validate services directory exists
if [ ! -d "$SERVICES_DIR" ]; then
    log_error "Services directory not found: $SERVICES_DIR"
    exit 1
fi

# Validate specific service if provided
if [ -n "$SERVICE" ]; then
    if [ ! -d "$SERVICES_DIR/$SERVICE" ]; then
        log_error "Service '$SERVICE' not found in $SERVICES_DIR"
        log_info "Available services:"
        find "$SERVICES_DIR" -mindepth 1 -maxdepth 1 -type d -printf "  - %f\n"
        exit 1
    fi
    log_info "Will copy service: $SERVICE"
else
    log_warning "No specific service specified. Will copy ALL services."
    log_warning "This may take some time and overwrite existing files in the container."
    log_info "Available services:"
    find "$SERVICES_DIR" -mindepth 1 -maxdepth 1 -type d -printf "  - %f\n"
    echo ""
    read -p "Continue? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "Aborted by user"
        exit 0
    fi
fi

# Test SSH connection
log_info "Testing SSH connection to $USER@$HOST..."
if ! ssh -o BatchMode=yes -o ConnectTimeout=5 "$USER@$HOST" "exit" 2>/dev/null; then
    log_error "Cannot connect to $USER@$HOST using SSH keys"
    log_info "Please set up SSH key authentication first:"
    log_info "  ssh-copy-id $USER@$HOST"
    exit 1
fi
log_success "SSH connection successful"

# Check if container exists and is running
log_info "Checking if container '$CONTAINER_NAME' exists on remote host..."
# shellcheck disable=SC2029
if ! ssh "$USER@$HOST" "docker ps --format '{{.Names}}' | grep -q '^$CONTAINER_NAME\$'" 2>/dev/null; then
    log_error "Container '$CONTAINER_NAME' is not running on remote host"
    log_info "Available containers:"
    ssh "$USER@$HOST" "docker ps --format 'table {{.Names}}\t{{.Status}}'"
    exit 1
fi
log_success "Container '$CONTAINER_NAME' is running"

# Create temporary directory on remote host
TEMP_DIR="/tmp/blueos-services-$$"
log_info "Creating temporary directory on remote host: $TEMP_DIR"
# shellcheck disable=SC2029
ssh "$USER@$HOST" "mkdir -p $TEMP_DIR"

# Cleanup function
cleanup() {
    log_info "Cleaning up temporary directory on remote host..."
    # shellcheck disable=SC2029
    ssh "$USER@$HOST" "rm -rf $TEMP_DIR" 2>/dev/null || true
}
trap cleanup EXIT

# Copy services to remote host
if [ -n "$SERVICE" ]; then
    log_info "Copying service '$SERVICE' to remote host..."
    rsync -avz --progress --exclude='__pycache__' --exclude='*.pyc' --exclude='*.pyo' --exclude='.pytest_cache' -e ssh "$SERVICES_DIR/$SERVICE/" "$USER@$HOST:$TEMP_DIR/$SERVICE/"
    SERVICES_TO_COPY="$SERVICE"
else
    log_info "Copying all services to remote host..."
    rsync -avz --progress --exclude='__pycache__' --exclude='*.pyc' --exclude='*.pyo' --exclude='.pytest_cache' -e ssh "$SERVICES_DIR/" "$USER@$HOST:$TEMP_DIR/"
    SERVICES_TO_COPY=$(find "$SERVICES_DIR" -mindepth 1 -maxdepth 1 -type d -printf "%f\n")
fi

# Copy from temp directory into container
log_info "Copying files into container '$CONTAINER_NAME'..."
for svc in $SERVICES_TO_COPY; do
    log_info "  Copying $svc..."
    # shellcheck disable=SC2029
    ssh "$USER@$HOST" "docker exec $CONTAINER_NAME mkdir -p /home/pi/services/$svc"
    # shellcheck disable=SC2029
    ssh "$USER@$HOST" "docker cp $TEMP_DIR/$svc/. $CONTAINER_NAME:/home/pi/services/$svc/"
done

log_success "All files copied successfully!"
log_info "Files are now in the container at: /home/pi/services/"

# Offer to restart services
if [ -n "$SERVICE" ]; then
    echo ""
    log_info "You may need to restart the '$SERVICE' service in the container for changes to take effect."
else
    echo ""
    log_info "You may need to restart services in the container for changes to take effect."
fi

