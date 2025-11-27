import filebrowser from "@/libs/filebrowser";

export class FolderManager {
    public downloadedBytes: number = 0;
    public totalBytes: number = 0;
    public startTime: number = 0;
    public downloadSpeed: number = 0;

    public inProgress: boolean = false;

    async downloadFolder(
        logs: string,
    ): Promise<void> {
        const folder = await filebrowser.fetchFolder(logs);
        this.inProgress = true;
        await filebrowser.downloadFolder(folder, (event) => {
            if (this.startTime === 0) this.startTime = Date.now()
            const current_time = Date.now()
            const elapsed = (current_time - this.startTime) / 1000
            this.startTime = current_time
    
            this.downloadedBytes = event.bytes
            this.totalBytes = event.loaded
            this.downloadSpeed = event.bytes / elapsed
          })
          .finally(() => {
            this.resetDownloadVariables()
            this.inProgress = false;
          })
    }

    resetDownloadVariables(): void {
        this.downloadedBytes = 0;
        this.totalBytes = 0;
        this.startTime = 0;
        this.downloadSpeed = 0;
    }
}