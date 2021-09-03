export interface Firmware {
    name: string
    url: URL
}

export enum Vehicle {
    Sub = 'Sub',
    Rover = 'Rover',
    Plane = 'Plane',
    Copter = 'Copter',
}
