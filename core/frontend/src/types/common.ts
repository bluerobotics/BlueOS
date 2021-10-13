/** Represents a Companion service, with the necessary information to identify it on the system */

export interface Dictionary<T> {
  [key: string]: T;
}

export interface Service {
  name: string
  description: string
  icon?: URL
  company: string
  version: string
  webpage?: URL
  api?: URL
  webapp?: {
      service_page?: URL
  }
}

export enum Baudrate {
  b9600 = '9600',
  b19200 = '19200',
  b38400 = '38400',
  b57600 = '57600',
  b115200 = '115200',
  b230400 = '230400',
  b460800 = '460800',
  b500000 = '500000',
  b576000 = '576000',
  b921600 = '921600',
  b1000000 = '1000000',
  b1152000 = '1152000',
  b1500000 = '1500000',
  b2000000 = '2000000',
  b2500000 = '2500000',
  b3000000 = '3000000',
  b3500000 = '3500000',
  b4000000 = '4000000',
}

export enum SocketKind {
  UDP = 'UDP',
  TCP = 'TCP',
}
