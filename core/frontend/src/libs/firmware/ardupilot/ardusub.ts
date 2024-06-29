export enum ArduSubMode {
  // Mode not set by vehicle yet
  PRE_FLIGHT = -1,
  // Manual angle with manual depth/throttle
  STABILIZE = 0,
  // Manual body-frame angular rate with manual depth/throttle
  ACRO = 1,
  // Manual angle with automatic depth/throttle
  ALT_HOLD = 2,
  // Fully automatic waypoint control using mission commands
  AUTO = 3,
  // Fully automatic fly to coordinate or fly at velocity/direction using GCS immediate commands
  GUIDED = 4,
  // Automatic circular flight with automatic throttle
  CIRCLE = 7,
  // Automatically return to surface, pilot maintains horizontal control
  SURFACE = 9,
  // Automatic position hold with manual override, with automatic throttle
  POSHOLD = 16,
  // Pass-through input with no stabilization
  MANUAL = 19,
  // Automatically detect motors orientation
  MOTOR_DETECT = 20,
  // Manual angle with automatic depth/throttle (from rangefinder altitude)
  SURFTRAK = 21,
}
