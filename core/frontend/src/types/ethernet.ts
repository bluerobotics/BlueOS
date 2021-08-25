export enum InterfaceMode {
    client = 'client',
    server = 'server',
    unmanaged = 'unmanaged',
}

export interface InterfaceConfiguration {
    ip: string,
    mode: InterfaceMode,
}

export interface InterfaceInfo {
    connected: boolean,
    number_of_disconnections: number,
}

export interface EthernetInterface {
    name: string,
    configuration: InterfaceConfiguration,
    info?: InterfaceInfo,
}
