### BlueROV2 BlueOS Overlay

This folder contains only one customization:

  - Custom default parameters with MNT1_TYPE set to Servo (7)
     This is done so manufacturing can test the enclosures upright instead of horizontal

`customize_images.sh` requires an ArduPilot version. It fetches that firmware
and the matching parameter set, then merges `extra.params` on top.

```
./deploy/image-customization/customize_images.sh /var/tmp/blueos-1.4.7-beta.2/deploy/pimod/blueos.img bluerov2 4.7.1 --extension-disabled bluerobotics.radcam-manager
```

Production image, sized for the card, trimmed and zipped:

```
./deploy/image-customization/customize_images.sh /path/BlueOS-1.4.7-pi4.img bluerov2 4.7.3 --extension-disabled bluerobotics.radcam-manager --size 113G --output /path/BlueOS-1.4.7-pi4_bluerov2_production.img --compress zip
```

The output is ready to flash as is: it no longer needs a first boot on a Pi to be read back, sanitized, shrunk and re-imaged.

BlueBoat, with no extra extensions:

```
./deploy/image-customization/customize_images.sh /var/tmp/blueos-1.4.7/deploy/pimod/blueos.img blueboat120 4.7.2
```
