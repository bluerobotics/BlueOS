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

Pull service files from a remote BlueOS container to local services folder.

OPTIONS:
    -u, --user USER         SSH user (default: pi)
    -h, --host HOST         Remote host (required)
    -s, --service SERVICE   Specific service to pull (optional, pulls all if not specified)
    --help                  Show this help message

EXAMPLES:
    # Pull a specific service
    $0 --host blueos.local --service ardupilot_manager

    # Pull all services
    $0 --host 192.168.2.2 --user pi

WARNING:
    This script will OVERWRITE local files in your services directory!
    Make sure you have committed any local changes before running this script.

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

# Check for uncommitted changes in git
if [ -d "$(cd "$SCRIPT_DIR/../.." && pwd)/.git" ]; then
    log_info "Checking for uncommitted changes in git repository..."
    cd "$(cd "$SCRIPT_DIR/../.." && pwd)"
    if ! git diff --quiet 2>/dev/null || ! git diff --cached --quiet 2>/dev/null; then
        log_warning "You have uncommitted changes in your git repository!"
        log_warning "Pulling services from remote will overwrite local files."
        echo ""
        read -p "Continue anyway? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "Aborted by user"
            exit 0
        fi
    else
        log_success "No uncommitted changes detected"
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

# Check what services exist in the container
log_info "Checking available services in container..."
# shellcheck disable=SC2029
AVAILABLE_SERVICES=$(ssh "$USER@$HOST" "docker exec $CONTAINER_NAME ls /home/pi/services 2>/dev/null" || echo "")
if [ -z "$AVAILABLE_SERVICES" ]; then
    log_error "No services found in container at /home/pi/services"
    exit 1
fi

# Validate specific service if provided
if [ -n "$SERVICE" ]; then
    if ! echo "$AVAILABLE_SERVICES" | grep -q "^${SERVICE}$"; then
        log_error "Service '$SERVICE' not found in container"
        log_info "Available services in container:"
        while IFS= read -r svc; do
            echo "  - $svc"
        done <<< "$AVAILABLE_SERVICES"
        exit 1
    fi
    log_info "Will pull service: $SERVICE"
else
    log_warning "No specific service specified. Will pull ALL services from container."
    log_warning "This will OVERWRITE existing local files in $SERVICES_DIR"
    log_info "Available services in container:"
    while IFS= read -r svc; do
        echo "  - $svc"
    done <<< "$AVAILABLE_SERVICES"
    echo ""
    read -p "Continue? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "Aborted by user"
        exit 0
    fi
fi

# Create temporary directory on remote host
TEMP_DIR="/tmp/blueos-services-pull-$$"
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

# Copy services from container to temp directory on remote
if [ -n "$SERVICE" ]; then
    log_info "Extracting service '$SERVICE' from container..."
    # shellcheck disable=SC2029
    ssh "$USER@$HOST" "docker cp $CONTAINER_NAME:/home/pi/services/$SERVICE $TEMP_DIR/"
    SERVICES_TO_PULL="$SERVICE"
else
    log_info "Extracting all services from container..."
    for svc in $AVAILABLE_SERVICES; do
        log_info "  Extracting $svc..."
        # shellcheck disable=SC2029
        ssh "$USER@$HOST" "docker cp $CONTAINER_NAME:/home/pi/services/$svc $TEMP_DIR/" 2>/dev/null || log_warning "Could not extract $svc"
    done
    SERVICES_TO_PULL="$AVAILABLE_SERVICES"
fi

# Pull services from remote to local
log_info "Pulling files from remote to local..."
if [ -n "$SERVICE" ]; then
    log_info "Syncing service '$SERVICE' to local..."
    mkdir -p "$SERVICES_DIR/$SERVICE"
    rsync -avz --progress --delete --exclude='__pycache__' --exclude='*.pyc' --exclude='*.pyo' --exclude='.pytest_cache' -e ssh "$USER@$HOST:$TEMP_DIR/$SERVICE/" "$SERVICES_DIR/$SERVICE/"
else
    log_info "Syncing all services to local..."
    for svc in $SERVICES_TO_PULL; do
        log_info "  Syncing $svc..."
        mkdir -p "$SERVICES_DIR/$svc"
        rsync -avz --progress --delete --exclude='__pycache__' --exclude='*.pyc' --exclude='*.pyo' --exclude='.pytest_cache' -e ssh "$USER@$HOST:$TEMP_DIR/$svc/" "$SERVICES_DIR/$svc/" 2>/dev/null || log_warning "Could not sync $svc"
    done
fi

log_success "All files pulled successfully!"
log_info "Files are now in: $SERVICES_DIR"

# Show git status if in a git repo
if [ -d "$(cd "$SCRIPT_DIR/../.." && pwd)/.git" ]; then
    echo ""
    log_info "Git status:"
    cd "$(cd "$SCRIPT_DIR/../.." && pwd)"
    git status --short core/services/ || true
fi

