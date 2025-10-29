export interface JournalEntry {
    cursor?: string,
    timestamp?: string,
    priority?: number,
    identifier?: string,
    unit?: string,
    pid?: number,
    hostname?: string,
    message: string,
}
