/** Base structure that provides information about kernel message */
export interface KernelMessage {
    /**
     * @param facility - Message source, E.g: "kern", "daemon"
     * @param level - Level of message, E.g: "info", "notice"
     * @param message - Content
     * @param sequence_number - Sequence number since first kernel message
     * @param timestamp_from_system_start_ns - When the message was received by the kernel
    * */
    facility: string,
    level: string,
    message: string,
    sequence_number: number,
    timestamp_from_system_start_ns: number,
}
