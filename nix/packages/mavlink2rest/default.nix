{
  fetchFromGitHub,
  fetchurl,
  lib,
  rustPlatform,
}:
let
  version = "0.11.28";

  # build.rs downloads these at build time, which the sandbox forbids; the patch
  # drops the download and the files are supplied from fixed-output fetches.
  vue = fetchurl {
    url = "https://unpkg.com/vue@3.0.5/dist/vue.global.js";
    hash = "sha256-Wr5PnkpmZ3oQFRZLfDrI6fsePSMak5h8rW2rqq+mdWg=";
  };
  highlight-css = fetchurl {
    url = "https://unpkg.com/highlight.js@10.6.0/styles/github.css";
    hash = "sha256-ja0z+lPRcUPYhi+sdtJJEKlXmCMywxJtCLxCQzKd2K0=";
  };
  highlight-js = fetchurl {
    url = "https://cdnjs.cloudflare.com/ajax/libs/highlight.js/10.6.0/highlight.min.js";
    hash = "sha256-0vVFuyJuW8wdUK83s0XSRdzmO8B6rroiQ+Dx6oey3Lk=";
  };
in
rustPlatform.buildRustPackage {
  pname = "mavlink2rest";
  inherit version;

  src = fetchFromGitHub {
    owner = "mavlink";
    repo = "mavlink2rest";
    tag = version;
    hash = "sha256-XhaQ21qn2K8KR2LiNorxOBIe7SA9pNadP2m9zCTsxT0=";
  };

  cargoLock.lockFile = ./Cargo.lock;

  patches = [ ./no-download.patch ];

  postPatch = ''
    cp ${./Cargo.lock} Cargo.lock
    cp ${vue} src/html/vue.global.js
    cp ${highlight-css} src/html/github.css
    cp ${highlight-js} src/html/highlight.min.js
  '';

  meta = {
    description = "REST API for MAVLink";
    homepage = "https://github.com/mavlink/mavlink2rest";
    license = lib.licenses.mit;
    mainProgram = "mavlink2rest";
    platforms = lib.platforms.linux;
  };
}
