#!/bin/bash
# Exercises every video track of the given recordings: playback from the start plus a mid-file seek.
# Usage: yarn esbuild .mcap-harness/harness.ts --bundle --platform=node --outfile=.mcap-harness/harness.js
#        .mcap-harness/sweep.sh ~/Downloads/*.mcap
cd "$(dirname "$0")/.." || exit 1
for f in "$@"; do
  base=$(basename "$f")
  probe=$(node .mcap-harness/harness.js "$f" /tmp/probe.mp4 0.01 2>/dev/null)
  tracks=$(echo "$probe" | rg -o 'video tracks (.*)$' -r '$1')
  duration=$(echo "$probe" | rg -o 'duration ([0-9.]+) s' -r '$1' | head -1)
  size=$(du -m "$f" | cut -f1)
  echo "### $base (${size} MB, ${duration}s) tracks: $tracks"
  if [ "$tracks" = "none" ]; then continue; fi
  seek=$(python3 -c "print(round(float('$duration')*0.7, 1))")
  echo "$tracks" | tr ',' '\n' | while read -r track; do
    track=$(echo "$track" | xargs)
    for mode in start seek; do
      if [ "$mode" = start ]; then args=(2); else args=(2 "$seek"); fi
      out=$(TRACK="$track" timeout 600 node .mcap-harness/harness.js "$f" /tmp/sweep.mp4 "${args[@]}" 2>&1)
      if echo "$out" | rg -q '^Error|Error:'; then
        printf '  %-32s %-5s FAILED: %s\n' "$track" "$mode" "$(echo "$out" | rg -o 'Error.*' | head -1)"
        continue
      fi
      printf '  %-32s %-5s ok  %-26s start=%-8s covered=%-6s payload=%-7s index+lookup=%s kB\n' \
        "$track" "$mode" \
        "$(echo "$out" | rg -o 'codec: (\S+ \S+)' -r '$1')" \
        "$(echo "$out" | rg -o 'starting at ([0-9.]+)' -r '$1')s" \
        "$(echo "$out" | rg -o 'covering ([0-9.]+)' -r '$1')s" \
        "$(echo "$out" | rg -o 'downloaded ([0-9.]+) MB' -r '$1')MB" \
        "$(echo "$out" | rg -o 'keyframe lookup cost: ([0-9.]+)' -r '$1')"
    done
  done
done
