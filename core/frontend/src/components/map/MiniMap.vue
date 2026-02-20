<template>
  <div class="mini-map-container">
    <div
      v-if="!has_position"
      class="no-gps-overlay d-flex align-center justify-center"
    >
      <div class="text-center">
        <v-icon
          size="48"
          color="grey"
        >
          mdi-map-marker-off
        </v-icon>
        <div class="grey--text mt-2">
          Waiting for GPS...
        </div>
      </div>
    </div>
    <div
      ref="mapContainer"
      class="map"
    />
  </div>
</template>

<script lang="ts">
import 'leaflet/dist/leaflet.css'

import L from 'leaflet'
import Vue from 'vue'

import blueboatMarker from '@/assets/img/map-markers/blueboat-marker.png'
import brov2Marker from '@/assets/img/map-markers/brov2-marker.png'
import genericMarker from '@/assets/img/map-markers/generic-vehicle-marker.png'
import mavlink2rest from '@/libs/MAVLink2Rest'
import { GpsFixType } from '@/libs/MAVLink2Rest/mavlink2rest-ts/messages/mavlink2rest-enum'
import { GlobalPositionInt, GpsRawInt } from '@/libs/MAVLink2Rest/mavlink2rest-ts/messages/mavlink2rest-message'
import autopilot_data from '@/store/autopilot'
import autopilot_manager from '@/store/autopilot_manager'

const marker_size = 48

function vehicleMarkerUrl(): string {
  const vehicle_type = autopilot_manager.vehicle_type?.toLowerCase() ?? ''
  if (vehicle_type.includes('submarine')) return brov2Marker
  if (vehicle_type.includes('boat')) return blueboatMarker
  return genericMarker
}

function createVehicleIcon(): L.DivIcon {
  const url = vehicleMarkerUrl()
  const size = `width: ${marker_size}px; height: ${marker_size}px;`
  return L.divIcon({
    html: `<img src="${url}" style="${size}">`,
    iconSize: [marker_size, marker_size],
    iconAnchor: [marker_size / 2, marker_size / 2],
    className: 'vehicle-marker-icon',
  })
}

export default Vue.extend({
  name: 'MiniMap',
  data: () => ({
    map: null as L.Map | null,
    vehicle_marker: null as L.Marker | null,
    trail: null as L.Polyline | null,
    trail_points: [] as L.LatLng[],
    latitude: 0,
    longitude: 0,
    heading: 0,
    has_position: false,
    has_gps_fix: false,
    max_trail_points: 500,
    position_listener: null as ReturnType<typeof mavlink2rest.startListening> | null,
    gps_fix_listener: null as ReturnType<typeof mavlink2rest.startListening> | null,
  }),
  watch: {
    has_position(val: boolean) {
      if (val) {
        this.$nextTick(() => {
          this.map?.invalidateSize()
        })
      }
    },
  },
  mounted() {
    this.initMap()
    this.startListening()
  },
  beforeDestroy() {
    this.position_listener?.discard()
    this.gps_fix_listener?.discard()
    this.map?.remove()
  },
  methods: {
    initMap() {
      const container = this.$refs.mapContainer as HTMLElement
      if (!container) return

      this.map = L.map(container, {
        center: [0, 0],
        zoom: 16,
        zoomControl: false,
        attributionControl: false,
        dragging: true,
        scrollWheelZoom: true,
      })

      L.tileLayer('/cache/tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 16,
      }).addTo(this.map)

      L.control.attribution({
        position: 'bottomright',
        prefix: false,
      }).addAttribution('OSM').addTo(this.map)

      this.trail = L.polyline([], {
        color: '#2699D0',
        weight: 2,
        opacity: 0.7,
      }).addTo(this.map)

      this.vehicle_marker = L.marker([0, 0], {
        icon: createVehicleIcon(),
      }).addTo(this.map)
    },
    startListening() {
      this.gps_fix_listener = mavlink2rest.startListening('GPS_RAW_INT')
      this.gps_fix_listener.setCallback((message) => {
        if (message?.header.system_id !== autopilot_data.system_id || message?.header.component_id !== 1) return
        const gps = message?.message as GpsRawInt
        const fix = gps.fix_type?.type
        this.has_gps_fix = fix !== undefined
          && fix !== GpsFixType.GPS_FIX_TYPE_NO_GPS
          && fix !== GpsFixType.GPS_FIX_TYPE_NO_FIX
      }).setFrequency(1)

      this.position_listener = mavlink2rest.startListening('GLOBAL_POSITION_INT')
      this.position_listener.setCallback((message) => {
        if (message?.header.system_id !== autopilot_data.system_id || message?.header.component_id !== 1) return
        if (!this.has_gps_fix) return

        const pos = message?.message as GlobalPositionInt
        this.latitude = pos.lat / 1e7
        this.longitude = pos.lon / 1e7
        if (this.latitude === 0 && this.longitude === 0) return
        if (pos.hdg !== 65535) {
          this.heading = pos.hdg / 100
        }

        const was_positioned = this.has_position
        this.has_position = true

        this.updateVehicle()

        if (!was_positioned) {
          this.$nextTick(() => {
            this.map?.invalidateSize()
            this.map?.setView([this.latitude, this.longitude], 18)
          })
        }
      }).setFrequency(1)
    },
    updateVehicle() {
      if (!this.map || !this.vehicle_marker || !this.trail) return

      const pos: L.LatLngExpression = [this.latitude, this.longitude]

      this.vehicle_marker.setLatLng(pos)

      // Only recenter when the vehicle approaches the viewport edge (inner 60% threshold)
      const bounds = this.map.getBounds().pad(-0.2)
      if (!bounds.contains(pos)) {
        this.map.panTo(pos)
      }

      const icon_el = this.vehicle_marker.getElement()
      const img = icon_el?.querySelector('img')
      if (img) {
        img.style.transform = `rotate(${this.heading}deg)`
      }

      this.trail_points.push(L.latLng(this.latitude, this.longitude))
      if (this.trail_points.length > this.max_trail_points) {
        this.trail_points.shift()
      }
      this.trail.setLatLngs(this.trail_points)
    },
  },
})
</script>

<style scoped>
.mini-map-container {
  width: 100%;
  height: 100%;
  position: relative;
  min-height: 100px;
  padding: 8px;
}

.map {
  width: 100%;
  height: 100%;
  border-radius: 8px;
  z-index: 0;
}

.no-gps-overlay {
  position: absolute;
  top: 8px;
  left: 8px;
  right: 8px;
  bottom: 8px;
  background: rgba(0, 0, 0, 0.3);
  z-index: 1;
  border-radius: 8px;
  pointer-events: none;
}
</style>

<style>
.vehicle-marker-icon {
  background: none !important;
  border: none !important;
}
</style>
