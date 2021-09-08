export interface FilebrowserFile {
  path: string
  name: string
  size: number
  extension: string
  modified: string
  mode: number
  isDir: boolean
  type: string
}

export interface FolderSorting {
  by: string
  asc: boolean
}

export interface FilebrowserFolder extends FilebrowserFile {
  items: FilebrowserFile[]
  numDirs: number
  numFiles: number
  sorting: FolderSorting
}

export interface FilebrowserCredentials {
  username: string
  password: string
  recaptcha: string
}
