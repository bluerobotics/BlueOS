#!/usr/bin/env bash
# The image repository is the GitHub owner. This stays a script, not a job output,
# because GitHub deletes an output whose value equals a secret.
# A non-fork pull request is a committer with write access, the same trust as the workflow
# that sources this file. A fork pull request has no registry secrets.
registry_user() {
    local owner_repo="${HEAD_REPOSITORY:-$GITHUB_REPOSITORY}"
    owner_repo=$(printf '%s' "$owner_repo" | tr '[:upper:]' '[:lower:]')
    local user="${owner_repo%%/*}"
    if [[ ! "$user" =~ ^[a-z0-9]([a-z0-9-]{0,37}[a-z0-9])?$ ]]; then
        echo "::error::Registry user '${user}' is not a Docker Hub namespace" >&2
        return 1
    fi
    printf '%s' "$user"
    return 0
}

image_tag_ok() {
    local tag="$1"
    if [[ ! "$tag" =~ ^[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}$ ]]; then
        echo "::error::Image tag '${tag}' is not a Docker tag" >&2
        return 1
    fi
    return 0
}
