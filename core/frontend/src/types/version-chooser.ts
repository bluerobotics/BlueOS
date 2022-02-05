export interface Version {
    repository: string,
    tag: string,
    last_modified: string,
    sha: (string | null)
  }

export interface VersionsQuery {
    local: Version[],
    remote: Version[],
    error: (string | null)
  }
