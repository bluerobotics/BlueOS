{
  fetchurl,
  python311,
  runCommand,
}:
let
  python = python311.withPackages (ps: [
    ps.pyserial
    ps.pyelftools
  ]);

  # Pinned to the commits core/tools/ardupilot_tools/setup-python-libs.sh uses.
  script =
    commit: file: hash:
    fetchurl {
      url = "https://raw.githubusercontent.com/ArduPilot/ardupilot/${commit}/Tools/scripts/${file}";
      inherit hash;
    };

  uploader =
    script "f6544ca25ab232407ec102b7a5adf0adca0f2062" "uploader.py"
      "sha256-wTRk8lFHT+ido1QSiQN3242+28R/Twgd/4l6UV2iEGE=";
  decoder =
    script "89c2b4828662ece84f48bdf9aa24db688fea36cb" "firmware_version_decoder.py"
      "sha256-bXUYv31mwFH5ftzRn9ln0vq/TSZofcZZoeip5r8Ax+g=";
  apjTool =
    script "b839ddcc00f4cb89d89aaa8cf0cb03298d2f00b4" "apj_tool.py"
      "sha256-uW6aH6ej09hPLXY83O7Ox25Lm41DkKfNeN9OvXJxSSQ=";
in
runCommand "ardupilot-tools"
  {
    # patchShebangs --host resolves `env python*` against HOST_PATH, which only
    # holds buildInputs.
    buildInputs = [ python ];
  }
  ''
    mkdir -p $out/bin $out/lib/python

    install -m755 ${uploader} $out/bin/ardupilot_fw_uploader.py
    install -m755 ${apjTool} $out/bin/apj_tool.py

    # Imported by FirmwareInstall, so it goes on PYTHONPATH.
    install -m644 ${decoder} $out/lib/python/ardupilot_fw_decoder.py

    patchShebangs --host $out/bin
  ''
