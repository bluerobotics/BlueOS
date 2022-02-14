/** Enum for possible Raspberry events */
export enum RaspberryEventType {
    FrequencyCapping = 'FrequencyCapping',
    TemperatureLimit = 'TemperatureLimit',
    Throttling = 'Throttling',
    UnderVoltage = 'UnderVoltage',
}

/** Base structure that provides event information for Raspberry */
export interface RaspberryEvent {
    /**
     * @param time - Time when the event occurred
     * @param type - E.g: "BCM2711"
    * */
    time: string,
    type: RaspberryEventType,
}

/** Base structure that provides system events for Raspberry */
export interface RaspberryEvents {
    /**
     * @param model - E.g: "Raspberry Pi 4 B"
     * @param soc - E.g: "BCM2711"
    * */
    occurring: RaspberryEvent[],
    list: RaspberryEvent[],
}

/** Base structure that provides platform information for Raspberry */
export interface Raspberry {
    /**
     * @param model - E.g: "Raspberry Pi 4 B"
     * @param soc - E.g: "BCM2711"
    * */
    model: string,
    soc: string,
    events: RaspberryEvents,
}

/** Base structure that provides platform information */
export interface Platform {
    /**
     * @param raspberry - Platform specific information for Raspberry Pi
     * @param udp - List od UDP connections
    * */
    raspberry?: Raspberry,
}
