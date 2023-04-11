export enum ShutdownType {
  Reboot = 'reboot',
  PowerOff = 'poweroff',
}

export interface ReturnStruct {
  stdout: string
  stderr: string
  return_code: number
}
