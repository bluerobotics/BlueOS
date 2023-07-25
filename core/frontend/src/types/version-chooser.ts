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

// Used to get internal error or status from connexion
export interface ServerResponse {
  title: string,
  status: number,
  detail: string,
  type: string,
}

export function isServerResponse(response: unknown): response is ServerResponse {
  // eslint-disable-next-line no-extra-parens
  return (response as ServerResponse).status !== undefined
}
