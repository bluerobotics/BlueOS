### BlueROV2 BlueOS Overlay

This folder contains only one customization:

  - Custom default parameters with MNT1_TYPE set to Servo (7)
     This is done so manufacturing can test the enclosures upright instead of horizontal

`customize_images.sh` requires an ArduPilot version. It fetches that firmware
and the matching parameter set, then merges `extra.params` on top.
