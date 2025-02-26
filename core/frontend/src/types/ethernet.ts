export enum AddressMode {
    client = 'client',
    server = 'server',
    backupServer = 'backup_server',
    unmanaged = 'unmanaged',
}

export interface InterfaceAddress {
    ip: string,
    mode: AddressMode,
}

export interface InterfaceInfo {
    connected: boolean,
    number_of_disconnections: number,
    priority: number,
}

export interface EthernetInterface {
    name: string,
    addresses: InterfaceAddress[],
    info?: InterfaceInfo,
    priority?: number,
}
