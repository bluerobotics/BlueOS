<template>
  <div>
    <v-alert v-if="!mavlink_lat" dense type="error" class="mt-4">
      No valid GPS position!
    </v-alert>

    A valid (usually GPS) position is required for the calibration to estimate the local world magnetic field.
    Estimation of the local magnetic field improves the calibration quality as it
    allows a 3D fusion of the compass data.
    <br>
    <br>
    <div v-if="!warnonly">
      <v-tooltip bottom>
        <template #activator="{ on }">
          <v-icon dense :color="mavlink_lat ? 'green' : 'orange'" v-on="on">
            {{ mavlink_lat ? "mdi-check-circle" : "mdi-alert-circle" }}
          </v-icon>
        </template>
        <span>{{ mavlink_lat ? "Valid GPS position" : "No valid GPS position" }}</span>
      </v-tooltip>
      <b>Current vehicle coordinates:</b>
      <br>
      {{ mavlink_lat?.toFixed(5) ?? "N/A" }} {{ mavlink_lon?.toFixed(5) ?? "N/A" }}
      <br>
    </div>
    <template v-if="!mavlink_lat && supports_setting_position && !warnonly">
      <v-icon dense :color="geoip_lat ? 'green' : 'red'">
        {{ geoip_lat ? "mdi-check-circle" : "mdi-alert-circle" }}
      </v-icon>
      <v-tooltip bottom>
        <template #activator="{ on }">
          <v-icon dense class="ml-1" v-on="on">
            mdi-help-circle
          </v-icon>
        </template>
        <span>GeoIP coordinates are estimated based on your IP address.</span>
      </v-tooltip>
      <b>GeoIP coordinates:</b>
      <br>
      {{ geoip_lat ?? "N/A" }} {{ geoip_lon ?? "N/A" }}
      <br>
    </template>
    <v-card v-if="!mavlink_lat && supports_setting_position && !warnonly" class="pa-4">
      <div class="d-flex flex-column justify-space-between">
        <v-btn
          v-if="!manual_coordinates"
          class="ma-1"
          small
          color="primary"
          @click="setOrigin(geoip_lat ?? 0, geoip_lon ?? 0)"
        >
          Use GeoIP coordinates
        </v-btn>
        <v-btn
          v-if="!mavlink_lat && !manual_coordinates"
          class="ma-1"
          small
          color="primary"
          @click="manual_coordinates = true"
        >
          Enter custom coordinate
        </v-btn>
      </div>

      <div v-if="manual_coordinates">
        <v-text-field
          v-model="manual_lat"
          label="Latitude"
          type="number"
          required
        />
        <v-text-field
          v-model="manual_lon"
          label="Longitude"
          type="number"
          required
        />
        <v-btn small color="primary" @click="setOrigin(manual_lat ?? 0, manual_lon ?? 0)">
          Use these coordinates
        </v-btn>
      </div>
    </v-card>
  </div>
</template>

<script lang="ts">

import { PropType } from 'vue'

import mavlink2rest from '@/libs/MAVLink2Rest'
import autopilot_data from '@/store/autopilot'
import autopilot from '@/store/autopilot_manager'
import { FirmwareVehicleType } from '@/types/autopilot'
import Parameter from '@/types/autopilot/parameter'
import { sleep } from '@/utils/helper_functions'

export default {
  name: 'AutoCoordinateDetector',
  model: {
    prop: 'inputcoordinates',
    event: 'input',
  },
  props: {
    inputcoordinates: {
      type: Object as PropType<{ lat: number, lon: number } | undefined>,
      required: false,
      default: undefined,
    },
    warnonly: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  data() {
    return {
      mavlink_lat: undefined as number | undefined,
      mavlink_lon: undefined as number | undefined,
      geoip_lat: undefined as number | undefined,
      geoip_lon: undefined as number | undefined,
      manual_coordinates: false,
      manual_lat: this.inputcoordinates?.lat,
      manual_lon: this.inputcoordinates?.lon,
      original_ekf_src: undefined as number | undefined,
    }
  },
  computed: {
    coordinates() {
      return this.mavlink_lat && this.mavlink_lon ? { lat: this.mavlink_lat, lon: this.mavlink_lon } : undefined
    },
    current_ekf_src(): number | undefined {
      return autopilot_data.parameter('EK3_SRC1_POSXY')?.value
    },
    supports_setting_position(): boolean {
      // So far we can only do this for Sub
      return autopilot.firmware_vehicle_type === FirmwareVehicleType.ArduSub
    },
    origin_lat_param(): Parameter | undefined {
      return autopilot_data.parameter('ORIGIN_LAT')
    },
    origin_lon_param(): Parameter | undefined {
      return autopilot_data.parameter('ORIGIN_LON')
    },
    firmware_backup_origin_is_unset(): boolean {
      if (!this.origin_lat_param || !this.origin_lon_param) {
        // A parameter that does not exist cannot be unset
        return true
      }
      return this.origin_lat_param.value === 0.0 && this.origin_lon_param.value === 0.0
    },
  },
  watch: {
    current_ekf_src(new_value) {
      // this is a "rising-edge" detector. only sets the value if it was never set
      if (new_value !== undefined && this.original_ekf_src === undefined) {
        this.original_ekf_src = new_value
      }
    },
    coordinates: {
      deep: true,
      handler() {
        this.$emit('input', this.coordinates)
      },
    },
  },
  mounted() {
    this.original_ekf_src = this.current_ekf_src
    mavlink2rest.startListening('GLOBAL_POSITION_INT').setCallback((receivedMessage) => {
      this.mavlink_lat = receivedMessage.message.lat !== 0 ? receivedMessage.message.lat * 1e-7 : undefined
      this.mavlink_lon = receivedMessage.message.lon !== 0 ? receivedMessage.message.lon * 1e-7 : undefined
    }).setFrequency(0)
    mavlink2rest.requestMessageRate('GLOBAL_POSITION_INT', 1, autopilot_data.system_id)
    this.getGeoIp()
  },
  methods: {
    async waitFor(func: () => boolean, raise = false): Promise<void> {
      const start = new Date()
      while (!func()) {
        await sleep(0.5)
        if (new Date().getTime() - start.getTime() > 5000) {
          const message = 'Timed out waiting'
          if (raise) {
            throw new Error(message)
          }
          console.warn(message)
          break
        }
      }
    },
    getGeoIp() {
      fetch('http://ip-api.com/json/')
        .then((response) => response.json())
        .then((data) => {
          this.geoip_lat = data.lat
          this.geoip_lon = data.lon
        })
        .catch((err) => console.error(err))
    },
    async setOrigin(lat: number, lon:number) {
      if (this.original_ekf_src === undefined) {
        console.error('Unable to detect ekf source, aborting')
        return
      }
      mavlink2rest.setParam('EK3_SRC1_POSXY', 0, autopilot_data.system_id)
      // wait for the param to get set

      await this.waitFor(() => this.current_ekf_src === 0)
      mavlink2rest.sendMessage(
        {
          header: {
            system_id: 255,
            component_id: 0,
            sequence: 0,
          },
          message: {
            type: 'SET_GPS_GLOBAL_ORIGIN',
            latitude: lat * 1e7,
            longitude: lon * 1e7,
            altitude: 0,
            target_system: autopilot_data.system_id,
            time_usec: 0,
          },
        },
      )
      await sleep(0.5)
      mavlink2rest.setParam('EK3_SRC1_POSXY', this.original_ekf_src, autopilot_data.system_id)
      await this.waitFor(() => this.current_ekf_src !== this.original_ekf_src)
      if (this.firmware_backup_origin_is_unset) {
        mavlink2rest.setParam('ORIGIN_LAT', lat, autopilot_data.system_id)
        mavlink2rest.setParam('ORIGIN_LON', lon, autopilot_data.system_id)
      }
    },
  },
}
</script>

<style scoped>
.position {
  max-width: 300px;
}
</style>
