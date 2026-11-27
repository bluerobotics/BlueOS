export interface ReadmeView {
  has(key: string): boolean
  store(key: string, readme: string): void
  setLoading(loading: boolean): void
  setError(error: boolean): void
}

/**
 * Loads readmes on demand. Every response is stored, but only the latest request may change the loading and error
 * state, so a slow or failed earlier request cannot override what the user is looking at now.
 */
export default class ReadmeLoader {
  private latest = 0

  constructor(private view: ReadmeView) {}

  async load(key: string, fetcher: () => Promise<string>): Promise<void> {
    this.latest += 1
    const request = this.latest
    this.view.setError(false)
    if (this.view.has(key)) {
      this.view.setLoading(false)
      return
    }
    this.view.setLoading(true)
    try {
      this.view.store(key, await fetcher())
    } catch {
      if (request === this.latest) {
        this.view.setError(true)
      }
    } finally {
      if (request === this.latest) {
        this.view.setLoading(false)
      }
    }
  }
}
