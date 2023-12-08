import { JSONValue } from '@/types/common'

export interface UsbPortInfo {
    /// Vendor ID
    vid: number,
    /// Product ID
    pid: number,
    /// Serial number (arbitrary string)
    serial_number: string | null,
    /// Manufacturer (arbitrary string)
    manufacturer: string | null,
    /// Product name (arbitrary string)
    product: string | null,
}

export type SerialPortType = null | string | UsbPortInfo;

export interface SerialPortInfo {
    // The short name of the serial port
    name: string,
    // The long name of the serial port
    by_path: string | null,
    // Time since the device was created,
    by_path_created_ms_ago: number | null
    // Udev information from the device
    udev_properties: JSONValue | null,
    // Is the port in use? by whom?
    current_user: string | null,
}

/** Base structure that provides serial port information */
export interface Serial {
    ports: SerialPortInfo[],
}
