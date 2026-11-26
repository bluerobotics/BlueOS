# GStreamer for MCM (D-084, option A): nixpkgs' packages rebuilt with only
# the plugins of blueos-docker-base's checked list
# (scripts/inspect_gst_plugins.sh at 35371aa1) plus those MCM creates
# (src/lib/stream/gst/utils.rs and its pipelines), and gst-libav for MCM's
# H.264/H.265 thumbnails. No GUI, documentation or introspection; the core
# without its doc-build script. `check` runs gst-inspect on `elements` and
# two pipelines (an x86_64 flake check). Measured in spikes/gstreamer-trim/.
{ lib, pkgs }:
let
  gst = pkgs.gst_all_1;
  # nixpkgs builds GStreamer with meson auto_features=enabled (every plugin
  # whose dependency is present); here everything is off unless named.
  only = features: old: {
    mesonAutoFeatures = "disabled";
    mesonFlags = (old.mesonFlags or [ ]) ++ map (f: "-D${f}=enabled") features;
  };

  gstreamer =
    (gst.gstreamer.override {
      enableDocumentation = false;
      withIntrospection = false;
    }).overrideAttrs
      (old: {
        # A doc-build script whose python3 shebang puts Python 3.13 (131 MiB)
        # in every closure that has GStreamer.
        postInstall = (old.postInstall or "") + ''
          rm $out/libexec/gstreamer-1.0/gst-plugins-doc-cache-generator
        '';
      });

  base =
    (gst.gst-plugins-base.override {
      inherit gstreamer;
      enableX11 = false;
      enableWayland = false;
      enableAlsa = false;
      enableGl = false;
      enableCdparanoia = false;
      enableDocumentation = false;
      withIntrospection = false;
    }).overrideAttrs
      (only [
        "app" # appsink
        "playback" # decodebin3
        "typefind" # decodebin3 needs it
        "tcp" # tcpserversink
        "pango" # timeoverlay
        "videoconvertscale" # videoconvert, videoscale
        "videotestsrc"
        "orc"
        # gst-discoverer-1.0 and gst-play-1.0, which recorder_extractor runs
        # for thumbnails. Gated by `tools`, which auto_features=disabled
        # otherwise turns off.
        "tools"
      ]);

  libnice = pkgs.libnice.override {
    gst_all_1 = {
      inherit gstreamer;
      gst-plugins-base = base;
    };
  };

  good =
    (gst.gst-plugins-good.override {
      gst-plugins-base = base;
      enableJack = false;
      enableX11 = false;
      enableWayland = false;
      enableDocumentation = false;
    }).overrideAttrs
      (only [
        "rtp" # rtph26[45]pay/depay, rtpjpeg*, rtpvraw*, rtpulpfecenc, rtpredenc
        "rtpmanager" # rtpbin (rtspsrc, webrtcbin)
        "rtsp" # rtspsrc
        "udp" # udpsrc, multiudpsink
        "jpeg" # jpegenc, jpegdec
        "isomp4" # mp4mux (mcap-foxglove-video-extract), qtdemux (gst-discoverer on its output)
        "v4l2"
        "v4l2-gudev"
        "v4l2-libv4l2" # v4l2src
        "vpx" # vp9enc
        "orc"
      ]);

  bad =
    (gst.gst-plugins-bad.override {
      inherit gstreamer libnice;
      gst-plugins-base = base;
      guiSupport = false;
      ajaSupport = false;
      bluezSupport = false;
      openh264Support = false;
      ldacbtSupport = false;
      webrtcAudioProcessingSupport = false;
      lcevcdecSupport = false;
      enableDocumentation = false;
    }).overrideAttrs
      (
        old:
        let
          o = only [
            "videoparsers" # h264parse, h265parse
            "jpegformat" # jpegparse
            "libde265" # libde265dec
            "proxy" # proxysrc, proxysink
            "shm" # shmsrc, shmsink
            "srtp" # srtpenc
            "webrtc"
            "dtls"
            "sctp" # webrtcbin
            "x265" # x265enc
            "orc"
          ] old;
          # nixpkgs passes -Dopenaptx=enabled unconditionally; the last -D wins.
        in
        o // { mesonFlags = o.mesonFlags ++ [ "-Dopenaptx=disabled" ]; }
      );

  ugly =
    (gst.gst-plugins-ugly.override {
      gst-plugins-base = base;
      enableDocumentation = false;
    }).overrideAttrs
      (only [
        "x264"
        "orc"
      ]);

  # avdec_h264 and avdec_h265 only (MCM's thumbnails).
  ffmpeg =
    (pkgs.ffmpeg-headless.override {
      ffmpegVariant = "headless";
      withHeadlessDeps = false;
      withSmallDeps = false;
      # gst-libav links libavcodec, libavformat, libavfilter and libavutil.
      buildAvcodec = true;
      buildAvformat = true;
      buildAvfilter = true;
      buildAvutil = true;
      buildSwresample = true;
      buildSwscale = true;
    }).overrideAttrs
      (old: {
        configureFlags = old.configureFlags ++ [
          "--disable-everything"
          "--enable-decoder=h264,hevc"
          "--enable-parser=h264,hevc"
        ];
        doCheck = false; # its self-tests assume the full build
      });

  libav =
    (gst.gst-libav.override {
      inherit gstreamer;
      gst-plugins-base = base;
      ffmpeg-headless = ffmpeg;
      enableDocumentation = false;
    }).overrideAttrs
      (only [ ]);

  rtsp-server =
    (gst.gst-rtsp-server.override {
      gst-plugins-base = base;
      gst-plugins-bad = bad;
      enableDocumentation = false;
    }).overrideAttrs
      (only [ ]);

  # What MCM and blueos-docker-base need (not rpicamsrc: the legacy MMAL
  # camera stack, which the Pi 5 does not have; libcamerasrc is not in the
  # image either way).
  elements = [
    "appsink"
    "capsfilter"
    "decodebin3"
    "h264parse"
    "h265parse"
    "identity"
    "jpegdec"
    "jpegenc"
    "jpegparse"
    "avdec_h264"
    "avdec_h265"
    "libde265dec"
    "multiudpsink"
    "proxysink"
    "proxysrc"
    "queue"
    "rtph264depay"
    "rtph264pay"
    "rtph265depay"
    "rtph265pay"
    "rtpjpegdepay"
    "rtpjpegpay"
    "rtpvrawdepay"
    "rtpvrawpay"
    "shmsink"
    "shmsrc"
    "srtpenc"
    "tcpserversink"
    "tee"
    "timeoverlay"
    "udpsrc"
    "v4l2src"
    "videoconvert"
    "videoscale"
    "videotestsrc"
    "vp9enc"
    "webrtcbin"
    "x264enc"
    "x265enc"
    "valve"
    "rtspsrc"
    "rtpbin"
    "nicesrc"
    "rtpulpfecenc"
    "rtpredenc"
  ];
  # The extractor's mp4mux/h264parse, and the recorder_extractor's thumbnail
  # pipeline (gst-play with a jpegenc snapshot).
  extraElements = [
    "mp4mux"
    "qtdemux"
    "filesink"
    "filesrc"
    "fakesink"
    "playbin"
    "typefind"
  ];
  # webrtcbin instantiates these itself rather than through the pipeline
  # description, so gst-inspect on webrtcbin would not catch their loss.
  webrtcElements = [
    "rtpbin"
    "rtpfunnel"
    "rtprtxsend"
    "rtprtxreceive"
    "rtpredenc"
    "rtpreddec"
    "rtpulpfecenc"
    "rtpulpfecdec"
    "clocksync"
    "nicesrc"
  ];
  pluginPath = lib.concatMapStringsSep ":" (p: "${p}/lib/gstreamer-1.0") [
    gstreamer.out
    base
    good
    bad
    ugly
    libav
    rtsp-server
    libnice.out
  ];
  check = pkgs.runCommand "gstreamer-for-mcm-check" { } ''
    export HOME=$TMPDIR GST_PLUGIN_SYSTEM_PATH_1_0=${pluginPath} GST_REGISTRY_1_0=$TMPDIR/registry.bin
    missing=""
    for e in ${lib.concatStringsSep " " (elements ++ extraElements ++ webrtcElements)}; do
      ${gstreamer.bin}/bin/gst-inspect-1.0 $e > /dev/null 2>&1 || missing="$missing $e"
    done
    [ -z "$missing" ] || { echo "missing elements:$missing"; exit 1; }
    ${gstreamer.bin}/bin/gst-launch-1.0 -q videotestsrc num-buffers=30 ! video/x-raw,width=320,height=240 \
      ! timeoverlay ! videoconvert ! x264enc tune=zerolatency ! h264parse ! rtph264pay \
      ! rtph264depay ! h264parse ! avdec_h264 ! videoconvert ! jpegenc ! fakesink
    ${gstreamer.bin}/bin/gst-launch-1.0 -q videotestsrc num-buffers=10 ! x265enc ! h265parse \
      ! avdec_h265 ! fakesink
    # mcap-foxglove-video-extract's pipeline
    ${gstreamer.bin}/bin/gst-launch-1.0 -q videotestsrc num-buffers=10 ! x264enc ! h264parse \
      ! mp4mux faststart=true ! filesink location=$TMPDIR/out.mp4
    # recorder_extractor: discover the file it just wrote, and pull a frame
    ${base}/bin/gst-discoverer-1.0 file://$TMPDIR/out.mp4 > /dev/null
    ${base}/bin/gst-play-1.0 -q --no-interactive --start-position=0 \
      --videosink='videoconvert ! videoscale ! video/x-raw,width=320,height=180 ! jpegenc snapshot=true quality=85 ! fdsink fd=1 sync=false' \
      --audiosink=fakesink file://$TMPDIR/out.mp4 > $TMPDIR/frame.jpg
    [ -s $TMPDIR/frame.jpg ]
    echo "${
      toString (builtins.length (elements ++ extraElements ++ webrtcElements))
    } elements found, MCM, extractor and thumbnail pipelines ran" > $out
  '';
in
{
  inherit
    gstreamer
    libnice
    ffmpeg
    elements
    extraElements
    webrtcElements
    pluginPath
    check
    ;
  gst-plugins-base = base;
  gst-plugins-good = good;
  gst-plugins-bad = bad;
  gst-plugins-ugly = ugly;
  gst-libav = libav;
  gst-rtsp-server = rtsp-server;
}
