import axios from 'axios'

import notifications from '@/store/notifications'
import { FilebrowserCredentials, FilebrowserFile, FilebrowserFolder } from '@/types/filebrowser'
import { filebrowser_service } from '@/types/frontend_services'

const filebrowser_url = '/file-browser/api'
const filebrowser_credentials: FilebrowserCredentials = { username: '', password: '', recaptcha: '' }

class Filebrowser {
  auth_token: string | null

  constructor() {
    this.auth_token = null
    this.update_filebrowser_token()
  }

  /* Fetch filebrowser API for a authentication token and store it.
     This method should be called on constructor so other methods have a token to use. */
  update_filebrowser_token(): void {
    axios({
      method: 'post',
      url: `${filebrowser_url}/login`,
      timeout: 10000,
      data: filebrowser_credentials,
    })
      .then((response) => {
        this.auth_token = response.data
      })
      .catch((error) => {
        const error_message = `Could not authenticate to filebrowser API: ${error.message}`
        const message = error_message
        notifications.pushError({ service: filebrowser_service, type: 'FILEBROWSER_AUTH_FAIL', message })
        throw new Error(error)
      })
  }

  /* Helper to get the auth token, checking before if it was set. */
  filebrowser_token(): string {
    if (this.auth_token === null) {
      this.update_filebrowser_token()
      if (this.auth_token === null) {
        throw new Error('Authentication token not set.')
      }
    }
    return this.auth_token
  }

  /* Fetch a folder from filebrowser. */
  /**
   * @param folder_path - String absolute path of folder to be fetched
   * @returns FilebrowserFolder object
  * */
  async fetchFolder(folder_path: string): Promise<FilebrowserFolder> {
    return axios({
      method: 'get',
      url: `${filebrowser_url}/resources${folder_path}`,
      timeout: 10000,
      headers: { 'X-Auth': this.filebrowser_token() },
    })
      .then((response) => response.data)
      .catch((error) => {
        const error_message = `Could not fetch folder ${folder_path}: ${error.message}`
        const message = error_message
        notifications.pushError({ service: filebrowser_service, type: 'FOLDER_FETCH_FAIL', message })
        throw new Error(error_message)
      })
  }

  /* Delete a single file. */
  /* Register a notification and throws if delete fails. */
  /**
   * @param file - FilebrowserFile object to be deleted
  * */
  async deleteFile(file: FilebrowserFile): Promise<void> {
    axios({
      method: 'delete',
      url: `/file-browser/api/resources${file.path}`,
      timeout: 10000,
      headers: { 'X-Auth': this.filebrowser_token() },
    })
      .catch((error) => {
        const error_message = `Could not delete file ${file.path}: ${error.message}`
        const message = error_message
        notifications.pushError({ service: filebrowser_service, type: 'FILE_DELETE_FAIL', message })
        throw new Error(error_message)
      })
  }

  /* Performs multiple-file delete requests. */
  /* Will perform all possible delete operations and reject if any of them fails. */
  /**
   * @param files - FilebrowserFile objects to be deleted
  * */
  async deleteFiles(files: FilebrowserFile[]): Promise<void> {
    const delete_promises: Promise<void>[] = []
    files.forEach((file) => {
      delete_promises.push(this.deleteFile(file))
    })
    await Promise.all(delete_promises)
  }

  /* Returns the relative URL (without hostname) of a single file. */
  /**
   * @param file - FilebrowserFile object
  * */
  singleFileRelativeURL(file: FilebrowserFile): string {
    return `${filebrowser_url}/raw${file.path}?auth=${this.filebrowser_token()}`
  }

  /* Returns the relative URL (without hostname) of a zip of multiple files. */
  /**
   * @param files - FilebrowserFile objects
  * */
  multipleFilesRelativeURL(files: FilebrowserFile[]): string {
    const files_arg = files.map((file) => file.path).join(',')
    return `${filebrowser_url}/raw/?files=${files_arg}&algo=zip&auth=${this.filebrowser_token()}`
  }

  /* Download files (single or multiple). */
  /**
   * @param files - FilebrowserFile objects array
  * */
  downloadFiles(files: FilebrowserFile[]): void {
    let url = ''
    if (files.length === 1) {
      url = this.singleFileRelativeURL(files[0])
    } else {
      url = this.multipleFilesRelativeURL(files)
    }
    window.open(url)
  }
}

const filebrowser = new Filebrowser()

export default filebrowser
