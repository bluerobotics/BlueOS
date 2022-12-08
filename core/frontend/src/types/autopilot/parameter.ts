export enum ParamType {
    MAV_PARAM_TYPE_UINT8 = 'MAV_PARAM_TYPE_UINT8',
    MAV_PARAM_TYPE_INT8 = 'MAV_PARAM_TYPE_INT8',
    MAV_PARAM_TYPE_UINT16 = 'MAV_PARAM_TYPE_UINT16',
    MAV_PARAM_TYPE_INT16 = 'MAV_PARAM_TYPE_INT16',
    MAV_PARAM_TYPE_UINT32 = 'MAV_PARAM_TYPE_UINT32',
    MAV_PARAM_TYPE_INT32 = 'MAV_PARAM_TYPE_INT32',
    MAV_PARAM_TYPE_UINT64 = 'MAV_PARAM_TYPE_UINT64',
    MAV_PARAM_TYPE_INT64 = 'MAV_PARAM_TYPE_INT64',
    MAV_PARAM_TYPE_REAL32 = 'MAV_PARAM_TYPE_REAL32',
    MAV_PARAM_TYPE_REAL64 = 'MAV_PARAM_TYPE_REAL64',
}

export default interface Parameter {
    name: string

    value: number

    readonly: boolean

    description: string

    shortDescription: string

    options?: {[key:number] : string}

    bitmask?: {[key:number] : string}

    rebootRequired: boolean

    id: number

    range?: {high: number, low: number}

    increment?: number

    paramType: { type: ParamType }

    units?: string
}
