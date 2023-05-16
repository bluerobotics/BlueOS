/** Represents a BlueOS service, with the necessary information to identify it on the system */

type PythonServiceError = {response: {data: {detail: string}}}
export type GenericError = Error | PythonServiceError | unknown

function isPythonError(error: GenericError): error is PythonServiceError {
  // eslint-disable-next-line no-extra-parens
  return (error as PythonServiceError).response !== undefined
}

function isError(error: GenericError): error is Error {
  // eslint-disable-next-line no-extra-parens
  return (error as Error).message !== undefined
}

export function getErrorMessage(error: GenericError): string {
  if (isPythonError(error)) {
    return error.response.data.detail
  }

  if (isError(error)) {
    return error.message
  }

  return 'Unknown error'
}

export type JSONValue =
    | string
    | number
    | boolean
    | { [x: string]: JSONValue }
    | Array<JSONValue>;

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
  b1200 = '1200',
  b1800 = '1800',
  b2400 = '2400',
  b4800 = '4800',
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

export interface Indexed {
  index: number
}

export interface Keyed {
  key: string
}
