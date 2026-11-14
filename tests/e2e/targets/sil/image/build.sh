#!/usr/bin/env bash
# Builds the SIL image into tests/e2e/.cache/sil.qcow2, only needs docker and /dev/kvm.
# Run it again whenever something in this folder changes. Pass "lock" to update flake.lock.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="$HERE/../../../.cache"
NIX_IMAGE="nixos/nix:2.35.4"
NIX="nix --extra-experimental-features 'nix-command flakes' --option sandbox false"
OWNER="$(id -u):$(id -g)"
mkdir -p "$OUT"

if [ "${1:-}" = "lock" ]; then
    docker run --rm -v blueos-e2e-nix:/nix -v "$HERE":/src "$NIX_IMAGE" \
        sh -c "$NIX flake lock /src && chown $OWNER /src/flake.lock"
    exit
fi

docker run --rm --device /dev/kvm -v blueos-e2e-nix:/nix -v "$HERE":/src:ro -v "$OUT":/out "$NIX_IMAGE" \
    sh -c "$NIX build --no-link --print-out-paths /src#sil > /tmp/out && \
        cp -L \$(cat /tmp/out)/*.qcow2 /out/sil.qcow2 && chown $OWNER /out/sil.qcow2"
