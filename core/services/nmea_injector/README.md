NMEA injection service

Currently supports the following NMEA devices:
- GPS:
    - Following GPS sentence types are currently supported: "GGA", "RMC", "GLL" and "GNS";
    - All sentence types include "lat" and "lon" fields;
    - GGA also includes "hdop", "alt" and "satellites_visible";
    - GNS also includes "hdop", and "satellites_visible";
