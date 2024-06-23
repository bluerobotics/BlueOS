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

    default?: number
}

export function printParam(param?: Parameter): string {
  if (param === undefined) {
    return 'Unknown'
  }

  // Show device id as an hexadecimal value
  if (param?.name.includes('_DEV_ID') || param?.name.includes('_DEVID')) {
    return `0x${param.value.toString(16).padStart(8, '0')}`
  }

  // Check if there are options but zero does not cover it
  // Or if it's a bitmask, where no flags is 'None'
  const option_zero_does_not_exist = param.options !== undefined && param.options?.[0] === undefined
  if ((param.bitmask || option_zero_does_not_exist) && param.value === 0) {
    return 'None'
  }

  // Bitmask can have options for default values, so this needs to go first
  // E.g: Option: 830 = default, bitmask = ATTITUDE_MED, GPS, PM, CTUN..
  // TODO: fix this so it doesnt show text for values such as 2.5 (rounding down to 2)

  const option_value = param.options?.[param.value]
  if (option_value) {
    return option_value
  }
  // if options is a float...
  const float_option = Object.entries(param.options ?? {}).find(
    ([key, _name]) => parseFloat(key) === param.value,
  )
  if (float_option) {
    return float_option[1]
  }

  if (param.bitmask) {
    const bitmask_result = []
    // We check up to 64 bits to make sure that we are going to cover all possible bits
    // Including the ones not listed in the bitmask
    for (let bit = 0; bit < 64; bit += 1) {
      const bitmask_value = 2 ** bit
      // eslint-disable-next-line no-bitwise
      if (param.value & bitmask_value) {
        bitmask_result.push(param.bitmask[bit] ?? `UNKNOWN (Bit ${bit})`)
      }
    }
    return bitmask_result.join(', ')
  }

  try {
    if (Math.abs(param.value) > 1e4) {
      return param.value.toExponential()
    }
    if (Math.abs(param.value) < 0.01 && param.value !== 0) {
      return param.value.toExponential()
    }
    return param.value.toFixed(param.paramType.type.includes('INT') ? 0 : 2)
  } catch {
    return 'N/A'
  }
}

export function printParamWithUnit(parameter?: Parameter): string {
  const paramValueText = printParam(parameter)
  const paramUnitsText = parameter?.units ? ` [${parameter.units}]` : ''

  return paramValueText + paramUnitsText
}
