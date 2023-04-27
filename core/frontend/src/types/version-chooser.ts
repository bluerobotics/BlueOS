export interface Version {
  repository: string,
  tag: string,
  last_modified: string,
  sha: (string | null),
}

export interface VersionsQuery {
  local: Version[],
  remote: Version[],
  error: (string | null),
}

export interface LocalVersionsQuery {
  local: Version[],
  error: (string | null),
}

export enum VersionType {
  Custom = 'custom',
  Master = 'master',
  Beta = 'beta',
  Stable = 'stable',
}
