#!/usr/bin/env bash

declare -a isort_args=()
declare -a black_args=()
: "${fixing:=false}"
: "${DEFAULT_COVERAGE_FAIL_UNDER:=75}"

setup_python_environment() {
    local env_label="$1"
    local project_dir="$2"
    echo "Setting up ${env_label} environment"
    uv sync --all-groups --project "$project_dir"
    # shellcheck disable=SC1091
    source "$project_dir/.venv/bin/activate"
    export VIRTUAL_ENV="$project_dir/.venv"
    export PATH="$VIRTUAL_ENV/bin:$PATH"
}

load_secondary_scope_paths() {
    if [ -n "${BLUEOS_SECONDARY_SCOPE:-}" ]; then
        read -r -a SECONDARY_SCOPE_PATHS <<<"${BLUEOS_SECONDARY_SCOPE}"
        return
    fi

    local pyproject="$SECONDARY_PROJECT_DIR/pyproject.toml"
    if [ ! -f "$pyproject" ]; then
        echo "Missing secondary pyproject: $pyproject" >&2
        exit 1
    fi

    local scope_script="$ROOT_DIR/.hooks/lib/get_secondary_scope.py"
    if [ ! -x "$scope_script" ]; then
        echo "Missing scope helper: $scope_script"
        exit 1
    fi

    local scope_output
    if ! scope_output=$(
        "$scope_script" --core-dir "$CORE_DIR" --pyproject "$pyproject"
    ); then
        echo "Failed to load secondary scope; see errors above." >&2
        exit 1
    fi
    mapfile -t SECONDARY_SCOPE_PATHS <<<"$scope_output"
    if [ "${#SECONDARY_SCOPE_PATHS[@]}" -eq 1 ] && [ -z "${SECONDARY_SCOPE_PATHS[0]}" ]; then
        SECONDARY_SCOPE_PATHS=()
    fi
}

path_matches_any() {
    local file="$1"
    shift || true
    local scope_path
    for scope_path in "$@"; do
        [[ -z "$scope_path" ]] && continue
        [[ $file == "$scope_path" || $file == "$scope_path/"* ]] && return 0
    done
    return 1
}

collect_python_files() {
    case "$1" in
        primary|secondary) local scope="$1";;
        *) echo "${FUNCNAME[0]}: scope must be 'primary' or 'secondary'" >&2; return 1;;
    esac

    git -C "$CORE_DIR" ls-files '*.py' |
    while read -r file; do
        [[ -z "$file" ]] && continue
        if path_matches_any "$file" "${SECONDARY_SCOPE_PATHS[@]}"; then
            [[ "$scope" == secondary ]] && echo "$file"
        else
            [[ "$scope" == primary ]] && echo "$file"
        fi
    done
}

collect_mypy_targets() {
    case "$1" in
        primary|secondary) local scope="$1";;
        *) echo "${FUNCNAME[0]}: scope must be 'primary' or 'secondary'" >&2; return 1;;
    esac

    git -C "$CORE_DIR" ls-files '*/pyproject.toml' |
    while read -r project; do
        [[ $project == libs/* || $project == services/* ]] || continue

        if path_matches_any "$project" "${SECONDARY_SCOPE_PATHS[@]}"; then
            [[ $scope == secondary ]] && echo "$(dirname "$project")"
        else
            [[ $scope == primary ]] && echo "$(dirname "$project")"
        fi
    done
}

run_python_checks() {
    local env_label="$1"
    case "$2" in
        primary|secondary) local scope="$2";;
        *) echo "${FUNCNAME[0]}: scope must be 'primary' or 'secondary'" >&2; return 1;;
    esac
    local pytest_ignores_ref="$3"
    local pytest_targets_ref="$4"
    local -n pytest_ignores="$pytest_ignores_ref"
    local -n pytest_targets="$pytest_targets_ref"

    echo "Running Python tooling for ${env_label}"

    local python_files=()
    mapfile -t python_files < <(collect_python_files "$scope")

    if [ "${#python_files[@]}" -eq 0 ]; then
        echo "No Python files found for ${env_label}, skipping."
        return
    fi

    pushd "$CORE_DIR" >/dev/null || return 1

    echo "Running isort (${env_label}).."
    isort "${isort_args[@]}" "${python_files[@]}"

    echo "Running black (${env_label}).."
    black "${black_args[@]}" "${python_files[@]}"

    if [ "$fixing" = true ]; then
        popd >/dev/null || return 1
        return
    fi

    echo "Running ruff (${env_label}).."
    ruff check "${python_files[@]}"

    echo "Running pylint (${env_label}).."
    pylint "${python_files[@]}"

    local mypy_targets=()
    mapfile -t mypy_targets < <(collect_mypy_targets "$scope")
    if [ "${#mypy_targets[@]}" -gt 0 ]; then
        echo "Running mypy (${env_label}).."
        local mypy_bin="${VIRTUAL_ENV:-}/bin/mypy"
        if [ ! -x "$mypy_bin" ]; then
            mypy_bin="$(command -v mypy || true)"
        fi
        if [ -z "$mypy_bin" ]; then
            echo "mypy executable not found in virtualenv or PATH." >&2
            exit 1
        fi
        printf '%s\n' "${mypy_targets[@]}" | parallel "$mypy_bin" --config-file "$CORE_DIR/pyproject.toml" {} --cache-dir {}/__mypycache__
    fi

    echo "Running pytest (${env_label}).."
    local pytest_args=(-n 10 --durations=0 --cov="$ROOT_DIR" --cov-report html)
    local coverage_threshold="${COVERAGE_FAIL_UNDER_OVERRIDE:-$DEFAULT_COVERAGE_FAIL_UNDER}"
    pytest_args+=(--cov-fail-under "$coverage_threshold")
    local ignore_path
    for ignore_path in "${pytest_ignores[@]}"; do
        [[ -z "$ignore_path" ]] && continue
        pytest_args+=(--ignore "$ignore_path")
    done
    if [ "${#pytest_targets[@]}" -gt 0 ]; then
        pytest_args+=("${pytest_targets[@]}")
    fi
    pytest "${pytest_args[@]}"

    popd >/dev/null || return 1
}

run_environment_phase() {
    local env_label="$1"
    local project_dir="$2"
    case "$3" in
        primary|secondary) local scope="$3";;
        *) echo "${FUNCNAME[0]}: scope must be 'primary' or 'secondary'" >&2; return 1;;
    esac
    local pytest_ignores_ref="$4"
    local pytest_targets_ref="$5"
    local run_bootstrap="${6:-false}"
    local coverage_threshold="${7:-}"

    (
        setup_python_environment "$env_label" "$project_dir"
        if [ "$run_bootstrap" = true ]; then
            bootstrap_runtime_dependencies
        fi
        if [ -n "$coverage_threshold" ]; then
            COVERAGE_FAIL_UNDER_OVERRIDE="$coverage_threshold"
        else
            unset COVERAGE_FAIL_UNDER_OVERRIDE
        fi
        run_python_checks "$env_label" "$scope" "$pytest_ignores_ref" "$pytest_targets_ref"
    )
}
