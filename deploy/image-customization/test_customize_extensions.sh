#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/customize_images.sh"

fail() {
    echo "FAIL: $*" >&2
    exit 1
}

tag="$(printf '%s' '{"v1.18.3":{},"v1.18.3-video-backports":{},"v1.18.4":{},"v1.19.0-beta.10":{},"latest":{}}' | select_stable_tag)"
[ "$tag" = "v1.18.4" ] || fail "stable tag: got '${tag}'"

tag="$(printf '%s' '{"1.2.0":{},"v1.10.0":{},"v1.9.9":{}}' | select_stable_tag)"
[ "$tag" = "v1.10.0" ] || fail "numeric sort: got '${tag}'"

tag="$(printf '%s' '{"v2.0.0-rc.1":{},"v1.0.0":{}}' | select_stable_tag)"
[ "$tag" = "v1.0.0" ] || fail "prerelease skipped: got '${tag}'"

tag="$(printf '%s' '{"v1.0.0-beta.1":{}}' | select_stable_tag || true)"
[ -z "$tag" ] || fail "prerelease-only should be empty, got '${tag}'"

entry='{"versions":{"v1.2.3":{},"v1.0.0":{}}}'
tag="$(printf '%s' "$entry" | resolve_version_tag "1.2.3")"
[ "$tag" = "v1.2.3" ] || fail "tag alias: got '${tag}'"
tag="$(printf '%s' "$entry" | resolve_version_tag "")"
[ "$tag" = "v1.2.3" ] || fail "empty tag should be stable, got '${tag}'"
tag="$(printf '%s' "$entry" | resolve_version_tag "missing" || true)"
[ -z "$tag" ] || fail "missing tag should be empty, got '${tag}'"

arm='{"images":[{"platform":{"architecture":"arm","variant":"v7"}},{"platform":{"architecture":"arm64","variant":null}}]}'
printf '%s' "$arm" | version_matches_board navigator || fail "navigator should match arm/v7"
printf '%s' "$arm" | version_matches_board navigator64 || fail "navigator64 should match arm64"
if printf '%s' '{"images":[{"platform":{"architecture":"amd64","variant":null}}]}' | version_matches_board navigator; then
    fail "amd64 matched navigator"
fi

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
cat >"$tmp/settings.json" <<'EOF'
{
  "VERSION": 2,
  "extensions": [
    {
      "docker": "bluerobotics/cockpit",
      "enabled": true,
      "identifier": "bluerobotics.cockpit",
      "name": "Cockpit",
      "permissions": "{}",
      "tag": "v1.0.0",
      "user_permissions": ""
    }
  ],
  "manifests": [{"identifier": "keep-me"}]
}
EOF

merged="$(merge_extension_settings "bluerobotics.sonar" "Sonar" "bluerobotics/sonar" "v1.2.3" '{"ExposedPorts":{}}' true "$tmp/settings.json")"
echo "$merged" | jq -e '
    (.extensions | length) == 2
    and .extensions[0].identifier == "bluerobotics.cockpit"
    and .extensions[0].tag == "v1.0.0"
    and .extensions[1].identifier == "bluerobotics.sonar"
    and .extensions[1].enabled == true
    and (.extensions[1].permissions | type) == "string"
    and .extensions[1].permissions == "{\"ExposedPorts\":{}}"
    and .manifests[0].identifier == "keep-me"
    and .VERSION == 2
' >/dev/null || fail "append dropped or rewrote existing settings"

printf '%s' "$merged" >"$tmp/settings.json"
merged="$(merge_extension_settings "bluerobotics.cockpit" "Cockpit" "bluerobotics/cockpit" "v9.9.9" "{}" true "$tmp/settings.json")"
cockpit_count="$(echo "$merged" | jq '[.extensions[] | select(.identifier == "bluerobotics.cockpit")] | length')"
[ "$cockpit_count" = "1" ] || fail "replace duplicated cockpit (${cockpit_count})"
cockpit_tag="$(echo "$merged" | jq -r '.extensions[] | select(.identifier == "bluerobotics.cockpit") | .tag')"
[ "$cockpit_tag" = "v9.9.9" ] || fail "replace tag: got '${cockpit_tag}'"
echo "$merged" | jq -e '.extensions[] | select(.identifier == "bluerobotics.sonar")' >/dev/null \
    || fail "replace dropped the other extension"

created="$(merge_extension_settings "a.b" "Name" "img/name" "v1.0.0" "{}")"
echo "$created" | jq -e '.VERSION == 2 and .manifests == [] and (.extensions | length) == 1 and .extensions[0].enabled == true' \
    >/dev/null || fail "missing settings file should create a v2 document"

disabled="$(merge_extension_settings "bluerobotics.sonar" "Sonar" "bluerobotics/sonar" "v1.2.3" "{}" false "$tmp/settings.json")"
echo "$disabled" | jq -e '
    (.extensions | length) == 2
    and (.extensions[] | select(.identifier == "bluerobotics.cockpit") | .enabled) == true
    and (.extensions[] | select(.identifier == "bluerobotics.sonar") | .enabled) == false
' >/dev/null || fail "disabled extension should stay disabled without turning others off"

echo "ok"
