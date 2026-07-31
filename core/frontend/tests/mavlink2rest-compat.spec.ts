import assert from 'node:assert/strict'
import test from 'node:test'

import { MavModeFlag } from '../src/libs/MAVLink2Rest/mavlink2rest-ts/messages/mavlink2rest-enum'
import { mavlinkFlagEnabled, mavlinkString } from '../src/utils/mavlink2rest_compat'

test('reads MAVLink character fields from mavlink2rest 0.11 and 1.0', () => {
  assert.equal(mavlinkString([69, 75, 51, 0, 0]), 'EK3')
  assert.equal(mavlinkString(['E', 'K', '3', '\0']), 'EK3')
  assert.equal(mavlinkString('EK3\0'), 'EK3')
})

test('reads MAVLink flags from mavlink2rest 0.11 and 1.0', () => {
  const armed = MavModeFlag.MAV_MODE_FLAG_SAFETY_ARMED
  assert.equal(mavlinkFlagEnabled({ bits: armed }, 'MAV_MODE_FLAG_SAFETY_ARMED', armed), true)
  assert.equal(mavlinkFlagEnabled({ bits: 0 }, 'MAV_MODE_FLAG_SAFETY_ARMED', armed), false)
  assert.equal(mavlinkFlagEnabled(
    'MAV_MODE_FLAG_MANUAL_INPUT_ENABLED | MAV_MODE_FLAG_SAFETY_ARMED',
    'MAV_MODE_FLAG_SAFETY_ARMED',
    armed,
  ), true)
  assert.equal(mavlinkFlagEnabled(
    'MAV_MODE_FLAG_MANUAL_INPUT_ENABLED',
    'MAV_MODE_FLAG_SAFETY_ARMED',
    armed,
  ), false)
})
