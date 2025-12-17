#!/usr/bin/env bash

print_usage() {
    cat <<'EOF'
Usage: .hooks/pre-push [options]

Options:
  --fix                   Run formatters (isort/black) for both environments and skip other checks.
  --fix-primary           Same as --fix but limited to the primary environment.
  --fix-secondary         Same as --fix but limited to the secondary environment.
  -h, --help              Show this help message.
EOF
}

require_commands() {
  for cmd in "$@"; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
      printf 'Required tool not found: %s\n' "$cmd" >&2
      exit 1
    fi
  done
}

check_required_tools() {
  require_commands python3 parallel uv poetry shellcheck
}

run_nginx_validation() {
    local nginx_version=1.22.1
    docker run --rm -v "$CORE_DIR/tools/nginx/:/nginx/:ro" nginx:"$nginx_version" nginx -c /nginx/nginx.conf -t
}

bootstrap_runtime_dependencies() {
    echo "installing mavlink-server"
    "$CORE_DIR/tools/mavlink_server/bootstrap.sh"
    echo "installing ardupilot_tools"
    NOSUDO=1 "$CORE_DIR/tools/ardupilot_tools/bootstrap.sh"
    "$CORE_DIR/tools/ardupilot_tools/setup-python-libs.sh"
}

verify_tag_if_needed() {
    local tag_name
    tag_name=$(git tag --points-at=HEAD | head -n 1)

    if [ -z "$tag_name" ]; then
        return
    fi

    echo "Current reference has the following tag: ${tag_name}"
    if dialog --defaultno --yesno "Are you pushing a tag ?" 20 60; then
        echo "Checking tag name.."
        if ! echo "$tag_name" | grep -Po "^\d+\.\d+\.\d+(\-[A-z]+\.\d+)?$|^\d+\.\d+\.\d+$" >/dev/null; then
            echo "Invalid tag name!"
            exit 1
        fi
        echo "Tag name is valid, congratulations for the new release!"
    fi
}

run_shellcheck_suite() {
    echo "Running shellcheck..."
    #SC2005: Allow us to break line while running command
    #SC2015: Allow us to use short circuit
    #SC2046: Allow word splitting
    #SC2048: Allow word splitting
    #SC2086: Allow word splitting
    git ls-files '*.sh' | xargs -L 1 shellcheck --exclude=SC2005,SC2015,SC2046,SC2048,SC2086
}
