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

export interface DHCPServerLease {
    mac: string,
    ip: string,
    expires_epoch?: number,
    expires_at?: Date,
    hostname?: string,
    client_id?: string,
    is_active?: boolean,
}

export interface DHCPServerDetails {
  interface: string,
  ipv4_gateway: string,
  lease_range: [number, number],
  lease_time: string,
  is_backup: boolean,
  is_running: boolean,
  leases: DHCPServerLease[],
  subnet_mask: string | null,
}
