<template>
  <v-card-text class="mt-3 pa-0">
    <v-tooltip bottom>
      <template #activator="{ on }">
        <v-icon dense :color="mavlink_lat ? 'green' : 'orange'" v-on="on">
          {{ mavlink_lat ? "mdi-check-circle" : "mdi-alert-circle" }}
        </v-icon>
      </template>
      <span>{{ mavlink_lat ? "Valid GPS position" : "No valid GPS position" }}</span>
    </v-tooltip>
    <b>Vehicle coordinates:</b> {{ mavlink_lat?.toFixed(5) ?? "N/A" }} {{ mavlink_lon?.toFixed(5) ?? "N/A" }}
    <br>
    <template v-if="!mavlink_lat">
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
      <b>GeoIP coordinates:</b> {{ geoip_lat ?? "N/A" }} {{ geoip_lon ?? "N/A" }}
      <br>
    </template>
    <v-card v-if="!mavlink_lat" class="pa-4">
      <v-card-text>
        No valid GPS position!
      </v-card-text>
      <v-card-actions>
        <v-btn v-if="!manual_coordinates" small color="primary" @click="setOrigin(geoip_lat ?? 0, geoip_lon ?? 0)">
          Use GeoIP coordinates
        </v-btn>
        <v-btn v-if="!mavlink_lat && !manual_coordinates" small color="primary" @click="manual_coordinates = true">
          Enter custom coordinate
        </v-btn>
        <br>
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
      </v-card-actions>
    </v-card>
  </v-card-text>
</template>

<script lang="ts">

import { PropType } from 'vue'

import mavlink2rest from '@/libs/MAVLink2Rest'
import autopilot_data from '@/store/autopilot'

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
    }
  },
  computed: {
    coordinates() {
      return this.mavlink_lat && this.mavlink_lon ? { lat: this.mavlink_lat, lon: this.mavlink_lon } : undefined
    },
  },
  watch: {
    coordinates: {
      deep: true,
      handler() {
        this.$emit('input', this.coordinates)
      },
    },
  },
  mounted() {
    mavlink2rest.startListening('GLOBAL_POSITION_INT').setCallback((receivedMessage) => {
      this.mavlink_lat = receivedMessage.message.lat !== 0 ? receivedMessage.message.lat * 1e-7 : undefined
      this.mavlink_lon = receivedMessage.message.lon !== 0 ? receivedMessage.message.lon * 1e-7 : undefined
    }).setFrequency(0)
    mavlink2rest.requestMessageRate('GLOBAL_POSITION_INT', 1, autopilot_data.system_id)
    this.getGeoIp()
  },
  methods: {
    getGeoIp() {
      fetch('http://ip-api.com/json/')
        .then((response) => response.json())
        .then((data) => {
          this.geoip_lat = data.lat
          this.geoip_lon = data.lon
        })
        .catch((err) => console.error(err))
    },
    setOrigin(lat: number, lon:number) {
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
    },
  },
}
</script>

<style scoped>

</style>
