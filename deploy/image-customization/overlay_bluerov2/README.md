### BlueROV2 BlueOS Overlay

This folder contains only one customization:

  - Custom default parameters with MNT1_TYPE set to Servo (7)
     This is done so manufacturing can test the enclosures upright instead of horizontal

When `customize_images.sh` is given a firmware version, it fetches the vehicle
parameter set from the BlueOS parameter repository and then merges `extra.params`
on top (these two manufacturing overrides). Without a firmware version, the
static `ardupilot_navigatorparams.params` file is copied as before.
