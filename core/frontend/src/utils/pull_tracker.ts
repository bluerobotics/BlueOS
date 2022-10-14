import { Dictionary } from '@/types/common'

class PullTracker {
    private layer_status: Dictionary<string> = {}

    private layers: string[] = []

    private layer_progress: Dictionary<string> = {}

    private left_over_data = ''

    pull_output = ''

    private onready: () => void

    overall_status = ''

    constructor(ready_callback: () => void) {
      this.onready = ready_callback
    }

    digestNewData(progressEvent: any): void {
      // dataChunk contains the data that have been obtained so far (the whole data so far)..
      // The received data is descbribed at
      // https://docker-py.readthedocs.io/en/stable/api.html#docker.api.image.ImageApiMixin.pull
      const dataChunk = progressEvent?.currentTarget?.response
      // As the data consists of multiple jsons, the following like is a hack to split them
      const dataList = (this.left_over_data + dataChunk.replaceAll('}{', '}\n\n{')).split('\n\n')
      this.left_over_data = ''

      for (const line of dataList) {
        try {
          const data = JSON.parse(line)
          if ('id' in data) {
            const { id } = data
            if (!this.layers.includes(id)) {
              this.layers.push(id)
            }
            if ('progress' in data) {
              this.layer_progress[id] = data.progress
            }
            if ('status' in data) {
              this.layer_status[id] = data.status
            }
          } else {
            this.overall_status = data.status
            // Axios returns the promise too early (before the pull is done)
            // so we check the overall docker status instead
            if (this.overall_status.includes('Downloaded newer image for')) {
              this.onready()
            }
            if (this.overall_status.includes('Image is up to date')) {
              this.onready()
            }
          }
        } catch (error) {
          this.left_over_data = line
        }
      }
      this.pull_output = ''
      this.layers.forEach((image) => {
        this.pull_output = `${this.pull_output}[${image}] ${this.layer_status[image]}`
        + `  ${this.layer_progress[image] || ''}\n`
      })
      this.pull_output = `${this.pull_output}${this.overall_status}\n`
    }
}
export default PullTracker
