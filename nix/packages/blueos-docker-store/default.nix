# Turn `docker save` archives into a Docker data-root that already holds the
# images, so a flashed card starts a container instead of unpacking 1.3GB of
# layers first.
#
# This is the whole point: on a Pi 4 the unpack in guest.nix's installScript is
# most of a three-minute boot, and every boot repeats it. A store built here
# means dockerd finds the images already present.
#
# The format is not documented anywhere, so it was read out of moby v29.9.2 and
# then checked against a real dockerd:
#
#   daemon/internal/layer/filestore.go         layerdb file names
#   daemon/graphdriver/overlay2/overlay.go     overlay2 directory layout
#   vendor/opencontainers/image-spec/identity  chain id recurrence
#
# and the acceptance test is in the header of synth-store.sh.
#
# Nothing here needs privileges. tar carries setuid bits, numeric owners, device
# nodes and xattrs as data, and every step that would need a real syscall runs
# under fakeroot, which fakes them at the libc boundary. That matters because
# the alternative -- running dockerd during the build -- needs a VM, and an
# aarch64 VM under emulation takes hours.
{
  lib,
  stdenv,
  attr,
  coreutils,
  fakeroot,
  findutils,
  gawk,
  gnugrep,
  gnused,
  gnutar,
  jq,
  util-linux,
  zstd,
  # Each entry is `{ image, archive }`, where `archive` is the fixed-output
  # derivation a `docker save` produced and `image` is the `repository:tag` it
  # carries. The tag has to be the one inside the archive: a loaded archive
  # keeps its own name, so the store records exactly what the build saw.
  #
  # Supplied by the caller through callPackage, since it is the one thing that
  # is not derivable from this file.
  images,
}:

let
  inherit (lib) concatMapStringsSep;

  imageArgs = concatMapStringsSep "\n" (i: "${i.archive} ${i.image}") images;

in
stdenv.mkDerivation {
  pname = "blueos-docker-store";
  version = "1";

  nativeBuildInputs = [
    attr
    coreutils
    fakeroot
    findutils
    gawk
    gnugrep
    gnused
    gnutar
    jq
    util-linux
    zstd
  ];

  # The archives have to be referenced from the script for the sandbox to
  # mount them; a bare attribute is only a string to Nix.
  inherit imageArgs;

  # One file out, zstd-compressed. A directory tree cannot be the output:
  # /nix/store canonicalises modes (0700 becomes 0555) and drops xattrs, and
  # both are load-bearing in an overlay2 layer. Compression because the card
  # carries this file as well as the extracted store: the layers are already
  # gzip inside their archives, but the tar framing and the duplicate content
  # across layers still compress to roughly 490MB from 1.4GB.
  #
  # docker.tar.images is the tag list, applied with `docker tag` at boot. It is
  # a separate file rather than the daemon's repositories.json because dockerd
  # owns that file, and re-extracting this store over a data root the version
  # chooser has pulled into would otherwise drop every tag the vehicle added.
  buildCommand = ''
    mkdir -p $out

    # HOME has to exist because tar and fakeroot both consult it, and a
    # sandbox has no passwd entry to derive it from.
    export HOME=$TMPDIR/home
    mkdir -p "$HOME"

    work=$TMPDIR/work
    store=$work/root

    # Every step that touches metadata runs in this one fakeroot session.
    # Splitting it up would not work: the fake modes and owners live in
    # fakeroot's in-memory database, so a second session would see the real,
    # canonicalised values instead.
    #
    # This is also why the store cannot be baked into the SD image here: the
    # module extracts this tar at boot, because make-ext4-fs.nix copies the
    # populated root *outside* fakeroot and would drop every fake mode.
    fakeroot -- bash ${./synth-store.sh} \
      "$store" "$work/docker.tar" "$TMPDIR" <<'IMAGES'
    ${imageArgs}
    IMAGES

    # A store that unpacked to nothing would still tar to a valid archive and
    # would then be invisible to dockerd, so refuse to ship one.
    test -n "$(find "$store/image/overlay2/layerdb" -mindepth 1 -maxdepth 1 -type d)"

    zstd -T$NIX_BUILD_CORES --no-progress "$work/docker.tar" -o $out/docker.tar.zst
    install -m 0444 "$work/docker.tar.images" $out/docker.tar.images
    install -m 0444 "$work/docker.tar.layers" $out/docker.tar.layers
  '';

  meta = {
    description = "Docker data-root with the BlueOS images already unpacked";
    platforms = lib.platforms.linux;
  };
}
