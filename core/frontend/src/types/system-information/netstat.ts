/** Base structure that provides connection information */
export interface Connection {
    /**
     * @param address - Address where the connection is happening
     * @param port - Port that the connection is using
    * */
    address: string,
    port: number,
}

/** Base structure that provides TCP information */
export interface TCP {
    /**
     * @param remote - TCP remote connection
     * @param local - TCP local connection
     * @param pids - Processes PIDs that is using such connection
     * @param state - E.g: Listen, time_wait, close_wait
    * */
    remote: Connection,
    local: Connection,
    pids: number[],
    status: string,
}

/** Base structure that provides UDP information */
export interface UDP {
    /**
     * @param local - UDP local bind
     * @param pids - Processes PIDs that is using such connection
    * */
    local: Connection,
    pids: number[],
}

/** Base structure that provides netstat information */
export interface Netstat {
    /**
     * @param tcp - List of TCP connections
     * @param udp - List od UDP connections
    * */
    tcp: TCP[],
    udp: UDP[],
}
