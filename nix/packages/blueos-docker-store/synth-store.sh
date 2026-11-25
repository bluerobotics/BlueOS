#!/usr/bin/env bash
# Populate a Docker data-root from `docker save` archives, without dockerd.
#
# Read stdin as lines of "<archive> <repository:tag>", each archive being the
# output of `docker save <repository:tag>`.
#
# What this reproduces, taken from moby v29.9.2:
#
#   image/overlay2/layerdb/sha256/<chainid>/diff      "sha256:<diffid>"
#   image/overlay2/layerdb/sha256/<chainid>/size      sum of file sizes
#   image/overlay2/layerdb/sha256/<chainid>/parent    "sha256:<parent chainid>"
#   image/overlay2/layerdb/sha256/<chainid>/cache-id  the overlay2 directory
#   overlay2/<cacheid>/diff/                          unpacked layer contents
#   overlay2/<cacheid>/link                           a 26-character link id
#   overlay2/<cacheid>/lower                          "l/<id>:l/<id>:...", i > 0
#   overlay2/<cacheid>/work                           i > 0
#   overlay2/<cacheid>/committed                      every layer but the top
#   overlay2/l/<linkid> -> ../<cacheid>/diff
#   image/overlay2/imagedb/content/sha256/<imageid>   the image config JSON
#   image/overlay2/repositories.json                  repository -> tag -> id
#
# The chain id is digest.FromBytes(parent + " " + diffid); a first layer's
# chain id is its own diff id. This is the same recurrence Podman uses, via
# opencontainers/image-spec/identity, and it was checked against the chain ids
# a real dockerd wrote for the same layers.
#
# Whiteouts are the part a plain tar extraction gets wrong:
#
#   .wh.<name>       a later layer deletes <name>  -> mode-0 char device 0:0
#   .wh..wh..opq     this directory is opaque      -> user.overlay.opaque=y
#
# `user.overlay.opaque`, not `trusted.overlay.opaque`: moby mounts its layers
# with `userxattr`, so it writes and reads the user namespace form. Confirmed by
# inspecting a live store. It is also why this needs no privileges.
#
# Not reproduced: tar-split.json.gz. dockerd only reads it to rebuild the
# original layer tar for `docker save` and for `docker commit`; running,
# inspecting and removing images all work without it. A synthesized image
# therefore cannot be `docker save`d, which nothing in BlueOS does -- the
# version chooser only pulls, loads, tags and removes.
set -euo pipefail

store=${1:?usage: synth-store.sh <data-root> <output.tar> <tmpdir>}
outtar=${2:?usage: synth-store.sh <data-root> <output.tar> <tmpdir>}
tmp=${3:?usage: synth-store.sh <data-root> <output.tar> <tmpdir>}

layerdb=$store/image/overlay2/layerdb/sha256
imgdb=$store/image/overlay2/imagedb/content/sha256
links=$store/overlay2/l
mkdir -p "$layerdb" "$imgdb" "$links" "$store/overlay2"

# Deliberately no image/overlay2/repositories.json. dockerd creates it on
# first start, and shipping one would mean re-extracting the store over a data
# root that the version chooser has since pulled into would replace the tag
# list with the shipped one, dropping every image the vehicle installed. The
# tags are recorded in `images` instead and applied with `docker tag` after the
# daemon is up.
images=$tmp/images
: > "$images"

# The digest of a byte stream, without the algorithm prefix tar/docker use.
sha() { sha256sum | cut -d' ' -f1; }

# Rewrite AUFS markers into the overlay2 representation, in place.
#
# A marker and the entry it annihilates share a path, which is why this runs per
# layer rather than over the whole store: `.wh.cache` in layer 3 has to become
# the deleted `cache` in layer 3, not in the layer that created it.
convert_whiteouts() {
  local diff=$1
  # Opaque markers describe their own directory, so they are applied to the
  # parent before the directory's contents are considered.
  while IFS= read -r -d '' opq; do
    setfattr -n user.overlay.opaque -v y "$(dirname "$opq")"
    rm -f "$opq"
  done < <(find "$diff" -name '.wh..wh..opq' -print0)

  while IFS= read -r -d '' wh; do
    local name
    name=$(basename "$wh")
    rm -f "$wh"
    mknod -m 0 "$(dirname "$wh")/${name#.wh.}" c 0 0
  done < <(find "$diff" -name '.wh.*' -print0)
}

addtag() {
  local repo=$1 tag=$2 id=$3
  # Familiar form, which is what dockerd looks a reference up by:
  # docker.io/library/alpine is "alpine", while a repository with an explicit
  # owner such as bluerobotics/blueos-core stays verbatim.
  case $repo in
    docker.io/library/*) repo=${repo#docker.io/library/} ;;
    docker.io/*) repo=${repo#docker.io/} ;;
  esac
  printf '%s %s %s\n' "$repo:$tag" "${id#sha256:}" "$repo" >> "$images"
}

while read -r archive image; do
  [ -n "${archive:-}" ] || continue
  # Unpacked one archive at a time, reusing one directory: the core image alone
  # is 1.3GB of layer content, and a sandbox has a tmpfs for /build.
  scratch=$tmp/unpack
  rm -rf "$scratch"; mkdir -p "$scratch"
  tar -xf "$archive" -C "$scratch"

  repo=${image%%:*}
  tag=${image##*:}

  jq -c '.[]' "$scratch/manifest.json" | while read -r entry; do
    config=$(jq -r '.Config' <<< "$entry")
    layers=$(jq -r '.Layers[]' <<< "$entry")

    # The image id is the digest of its config blob, which is also the name
    # dockerd stores it under.
    imageid="sha256:$(sha < "$scratch/$config")"
    cp "$scratch/$config" "$imgdb/${imageid#sha256:}"

    parent=""
    while read -r layerpath; do
      diffid="sha256:$(sha < "$scratch/$layerpath")"
      if [ -z "$parent" ]; then
        chainid=$diffid
      else
        chainid="sha256:$(printf '%s %s' "$parent" "$diffid" | sha)"
      fi

      # moby generates a random cache-id at import. Deriving it from the chain
      # id instead makes the build reproducible, which Nix requires because the
      # store ends up in a derivation output.
      cacheid=$(printf 'cache %s' "$chainid" | sha)
      # 26 hex characters, uppercased, is the shape overlay2 generates; the
      # length is maxDepth-dependent and only has to be unique.
      linkid=$(printf 'link %s' "$chainid" | sha | cut -c1-26 | tr 'a-f' 'A-F')

      mkdir -p "$store/overlay2/$cacheid/diff" "$layerdb/${chainid#sha256:}"
      # xattrs first so a layer that carries its own survive, then a plain
      # retry for tars that contain none at all (tar exits 1 on the xattr pass
      # when the destination cannot take them).
      tar -xpf "$scratch/$layerpath" -C "$store/overlay2/$cacheid/diff" \
        --numeric-owner --xattrs --xattrs-include='*' 2> /dev/null ||
        tar -xpf "$scratch/$layerpath" -C "$store/overlay2/$cacheid/diff" --numeric-owner
      convert_whiteouts "$store/overlay2/$cacheid/diff"

      printf '%s' "$diffid" > "$layerdb/${chainid#sha256:}/diff"
      printf '%s' "$cacheid" > "$layerdb/${chainid#sha256:}/cache-id"
      # Sum of file sizes, which is what moby records: it is the size of the
      # layer's content, not the space it occupies. printf, not a redirect from
      # awk: GetSize parses this with strconv.ParseInt and does not trim, so a
      # trailing newline makes it report the layer as missing.
      size=$(find "$store/overlay2/$cacheid/diff" -type f -printf '%s\n' |
        awk '{ s += $1 } END { print s + 0 }')
      printf '%s' "$size" > "$layerdb/${chainid#sha256:}/size"

      printf '%s' "$linkid" > "$store/overlay2/$cacheid/link"
      ln -sfn "../$cacheid/diff" "$links/$linkid"

      if [ -n "$parent" ]; then
        printf '%s' "$parent" > "$layerdb/${chainid#sha256:}/parent"
        prev=$(cat "$layerdb/${parent#sha256:}/cache-id")
        prevlink=$(cat "$store/overlay2/$prev/link")
        # Uppermost first, which is the order overlay2 passes to the mount.
        if [ -f "$store/overlay2/$prev/lower" ]; then
          printf 'l/%s:%s' "$prevlink" "$(cat "$store/overlay2/$prev/lower")" \
            > "$store/overlay2/$cacheid/lower"
        else
          printf 'l/%s' "$prevlink" > "$store/overlay2/$cacheid/lower"
        fi
        mkdir -p "$store/overlay2/$cacheid/work"
        # Marks the parent as no longer writable, so it is mounted read-only as
        # a lower layer. Without it the driver would try to use it as an upper.
        : > "$store/overlay2/$prev/committed"
      fi

      parent=$chainid
    done <<< "$layers"

    addtag "$repo" "$tag" "$imageid"
  done

  rm -rf "$scratch"
done

# A tar rather than a tree: /nix/store strips modes and xattrs from a directory
# output, and both are load-bearing here. --xattrs writes the opaque marks as
# pax headers, which the boot-time extract puts back.
tar -cf "$outtar" --xattrs --numeric-owner -C "$store" .

# "<reference> <image id> <repository>" per line, read back by the module to
# apply tags after dockerd is up. Not a repositories.json inside the tar:
# dockerd creates that file itself, and shipping one would mean that extracting
# over a data root the version chooser has already pulled into replaces the tag
# list with the shipped one.
cp "$images" "$outtar.images"

# The chain ids this store ships, one per line. The unit needs them because
# "every layer here is consistent" is not the same as "every layer shipped is
# here": deleting a whole image takes its layers with it and leaves a store
# that is internally perfect and missing an image. Comparing against this list
# is what turns that into a re-extract instead of a boot that cannot start.
find "$layerdb" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | sort > "$outtar.layers"
