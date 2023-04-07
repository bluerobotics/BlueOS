<template>
  <div>
    <div id="vehicle-banner" class="d-flex align-center justify-space-between mb-6">
      <image-picker
        directory="/userdata/images/vehicle"
        readonly-directory="/vehicles/images"
        :default-image="require('@/assets/vehicles/images/unknown.svg')"
        :image="vehicle_image"
        @image-selected="save_vehicle_image"
      />
      <p id="vehicle-name" class="pa-4">
        {{ vehicle_name }}
        <v-btn
          class="mx-2 edit-icon"
          fab
          dark
          x-small
          @click="openDialog"
        >
          <v-icon>
            mdi-pencil
          </v-icon>
        </v-btn>
      </p>
      <image-picker
        directory="/userdata/images/logo"
        :default-image="require('@/assets/img/blue-robotics-logo.svg')"
        :image="logo_image"
        @image-selected="save_logo"
      />
    </div>
    <v-dialog v-if="dialog" v-model="dialog" max-width="500px">
      <v-card>
        <v-card-title>Edit Vehicle Details</v-card-title>
        <v-card-text>
          <v-text-field
            v-model="vehicle_name_input"
            label="Vehicle Name"
          />
          <v-text-field
            v-model="mdns_hostname_input"
            label="mDNS Hostname"
          />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn color="blue darken-1" text @click="dialog = false">
            Cancel
          </v-btn>
          <v-btn color="blue darken-1" text @click="save()">
            Save
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<script lang="ts">
import Vue from 'vue'

import bag from '@/store/bag'
import beacon from '@/store/beacon'

import ImagePicker from './ImagePicker.vue'

export default Vue.extend({
  name: 'VehicleBanner',
  components: {
    ImagePicker,
  },
  data() {
    return {
      vehicle_name_input: '',
      vehicle_image: undefined as string | undefined,
      logo_image: null as string | null,
      mdns_hostname_input: '',
      dialog: false,
    }
  },
  computed: {
    vehicle_name() {
      return beacon.vehicle_name
    },
    mdns_hostname() {
      return beacon.hostname || 'blueos'
    },
  },
  mounted() {
    beacon.registerBeaconListener(this)
    this.load_vehicle_image()
    this.vehicle_name_input = this.vehicle_name || 'My Vehicle'
    this.mdns_hostname_input = this.mdns_hostname
    this.load_company_logo()
  },
  methods: {
    async load_vehicle_image() {
      this.vehicle_image = (await bag.getData('vehicle.image_path'))?.url as string
    },
    async load_company_logo() {
      this.logo_image = (await bag.getData('vehicle.logo_image_path'))?.url as string
    },
    save() {
      this.save_name()
      this.save_mdns()
      this.dialog = false
    },
    save_logo(image: string) {
      this.logo_image = image
      bag.setData('vehicle.logo_image_path', {
        url: image,
      })
    },
    save_vehicle_image(image: string) {
      this.vehicle_image = image
      bag.setData('vehicle.image_path', {
        url: image,
      })
    },
    save_name() {
      beacon.setVehicleName(this.vehicle_name_input)
    },
    save_mdns() {
      beacon.setHostname(this.mdns_hostname_input)
    },
    openDialog() {
      this.dialog = true
    },
  },
})
</script>
<style scoped>
  #vehicle-name:hover .edit-icon{
    display: inline-flex;
  }

  #vehicle-banner {
    margin-bottom: 0 !important;
    margin-top: 3px;
  }

  #vehicle-name {
    margin-bottom: 0 !important;
    position: relative;
  }
  .edit-icon {
    display: none;
    right: 0;
    bottom: 0;
    position: absolute;
  }
</style>
