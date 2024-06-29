/* This has some convenience functions related to Ardupilot's implementations
   While there are MAVLink things here, their usage is tied to Ardupilot's implementation
*/

import mavlink2rest from "@/libs/MAVLink2Rest";
import { MavCmd, MavModeFlag } from "@/libs/MAVLink2Rest/mavlink2rest-ts/messages/mavlink2rest-enum";
import autopilot_data from "@/store/autopilot";
import mavlink_store_get from "./mavlink";
import mavlink from "@/store/mavlink";
import { Message } from "@/libs/MAVLink2Rest/mavlink2rest-ts/messages/mavlink2rest-message";


export function isArmed(): boolean {
  const vehicle_id = autopilot_data.system_id
  const heartbeat = mavlink_store_get(
    mavlink,
    'HEARTBEAT.messageData.message',
    vehicle_id,
    1,
  ) as Message.Heartbeat
  return Boolean(heartbeat?.base_mode.bits & MavModeFlag.MAV_MODE_FLAG_SAFETY_ARMED)
}

function sendArmDisarm(arm: boolean, force: boolean): void {
  const vehicle_id = autopilot_data.system_id
  const magic_number = arm ? 2989 : 21196
  mavlink2rest.sendMessage(
    {
      header: {
        system_id: 255,
        component_id: 0,
        sequence: 0,
      },
      message: {
        type: 'COMMAND_LONG',
        param1: arm ? 1 : 0, // 0: Disarm, 1: ARM,
        param2: force ? magic_number : 0, // force arming/disarming
        param3: 0,
        param4: 0,
        param5: 0,
        param6: 0,
        param7: 0,
        command: {
          type: MavCmd.MAV_CMD_COMPONENT_ARM_DISARM,
        },
        target_system: autopilot_data.system_id,
        target_component: 1,
        confirmation: 0,
      },
    },
  )
}

export async function armDisarm(arm: boolean, force: boolean, tries?: number): Promise<void> {
  return new Promise<void>(async (resolve, reject) => {
    tries = tries || 5
    let current_try = 0

    while (isArmed() !== arm && current_try < tries) {
      current_try += 1
      sendArmDisarm(arm, force)
      await new Promise((resolve) => setTimeout(resolve, 1000))
    }

    if (isArmed() == arm) {
      resolve()
    }
    reject()
  })
}

export function getMode(): number {
  const vehicle_id = autopilot_data.system_id
  const heartbeat = mavlink_store_get(
    mavlink,
    'HEARTBEAT.messageData.message',
    vehicle_id,
    1,
  ) as Message.Heartbeat
  return heartbeat?.custom_mode || 0
}

export async function setMode(mode: number,  tries?: number): Promise<void> {
  tries = tries || 5
  let current_try = 0
  return new Promise<void>(async (resolve, reject) => {
    while (getMode() !== mode && current_try < tries) {
      current_try += 1
      mavlink2rest.sendCommandLong(
        MavCmd.MAV_CMD_DO_SET_MODE,
        MavModeFlag.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
        mode,
      )
      await new Promise((resolve) => setTimeout(resolve, 1000))
    }
    if (getMode() === mode) {
      resolve()
    }
    reject()
  })
}

export async function doMotorTest(motorId: number, output: number): Promise<void> {
  mavlink2rest.sendMessageViaWebsocket(
    {
      header: {
        system_id: 255,
        component_id: 0,
        sequence: 0,
      },
      message: {
        type: 'COMMAND_LONG',
        // Rover and Sub have different starting numbers for motors
        param1: motorId, // MOTOR_TEST_ORDER
        param2: 1, // MOTOR_TEST_THROTTLE_PWM
        param3: output,
        param4: 1, // Seconds running the motor
        param5: 1, // Number of motors to be tested
        param6: 2, // Motor numbers are specified as the output as labeled on the board.
        param7: 0,
        command: {
          type: MavCmd.MAV_CMD_DO_MOTOR_TEST,
        },
        target_system: autopilot_data.system_id,
        target_component: 1,
        confirmation: 0,
      },
    },
  )
}
