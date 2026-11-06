/**
 * A BlueOS version is a NixOS generation. The update daemon reports the profile
 * as it is, so these types mirror its JSON rather than the container images the
 * version chooser deals in.
 */
export interface Generation {
  generation: number,
  /** Store path of the system closure. Two builds of one version differ here. */
  toplevel: string,
  version: string,
  channel: string,
  revision: string,
  created: string,
  current: boolean,
  /** The last generation that booted and passed its health check. */
  known_good: boolean,
  /** Whether booting it needs a reboot before it takes effect. */
  reboot_required: boolean,
}

export interface PendingActivation {
  toplevel: string,
  mode: ActivationMode,
}

export interface Status {
  current: Generation,
  known_good: (Generation | null),
  /** What the profile points at, when it is not what is running: a reboot is owed. */
  installed: (Generation | null),
  /** An activation that has not confirmed itself yet, with a timer running. */
  pending: (PendingActivation | null),
  reboot_required: boolean,
  /** The generation that failed and was rolled back away from, if the system did. */
  rolled_back_from: (string | null),
  /** Tail of the last activation's output, which runs detached from its request. */
  last_switch_log: (string | null),
}

export interface Release {
  board: string,
  channel: string,
  version: string,
  revision: string,
  toplevel: string,
  published: (string | null),
}

export interface ReleasesResponse {
  releases: Release[],
  /** Why the list is empty, when it is empty because something failed. */
  error: (string | null),
}

export interface ActivationResponse {
  toplevel: string,
  reboot_required: boolean,
  message: string,
  /** Where the detached switch writes its progress. */
  log: string,
}

/** `switch` applies the generation now; `boot` installs it for the next boot. */
export type ActivationMode = 'switch' | 'boot'
