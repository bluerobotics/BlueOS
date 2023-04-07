<template>
  <div>
    <SpinningLogo v-if="!loading_done" size="5%" />
    <div v-if="loading_done" id="vehicle-banner" class="d-flex justify-space-between mb-6">
      <!-- TODO: create an imagePicker widget -->
      <v-img src="/userdata/images/vehicle.png" contain class="banner pa-1" />
      <p id="vehicle-name" class="pa-4">
        {{ vehicle_name }}
      </p>
      <!-- TODO: create an imagePicker widget -->
      <v-img
        src="../../assets/img/blue-robotics-logo.svg"
        contain
        class="banner pa-1"
      />
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

import SpinningLogo from '../common/SpinningLogo.vue'

const API_URL = '/beacon/v1.0'

export default Vue.extend({
  name: 'VehicleBanner',
  components: {
    SpinningLogo,
  },
  data() {
    return {
      vehicle_name: '',
      loading_done: false,
      vehicle_name_input: '',
      mdns_hostname_input: '',
      dialog: false,
    }
  },
  computed: {
    vehicle_name() {
      return beacon.vehicle_name || 'My Vehicle'
    },
    mdns_hostname() {
      return beacon.hostname || 'blueos'
    },
  },
  mounted() {
    this.load_name()
  },
  methods: {
    load_name() {
      back_axios({
        method: 'get',
        url: `${API_URL}/vehicle_name`,
      }).then((response) => {
        this.vehicle_name = response.data
        this.vehicle_name_input = this.vehicle_name
        this.loading_done = true
      })
    },
    save() {
      this.save_name()
      this.save_mdns()
      this.loading_done = false
      this.dialog = false
    },
    save_name() {
      beacon.setVehicleName(this.vehicle_name_input)
    },
    save_mdns() {
      if (this.mdns_hostname_input === '') {
        return
      }
      back_axios({
        method: 'post',
        url: `${API_URL}/hostname?hostname=${this.mdns_hostname_input}`,
      })
    },
    openDialog() {
      this.dialog = true
    },
  },
})
</script>
<style scoped>
  .banner {
    display: inline-flex;
    height: 50px;
    width: 50px;
    margin: 0px;
    object-fit: contain;
  }
  #vehicle-banner:hover .edit-icon{
    display: inline-flex;
  }

  #vehicle-banner {
    position: relative;
    margin-bottom: 0 !important;
    margin-top: 3px;
  }

  #vehicle-name {
    margin-bottom: 0 !important;
  }
  .edit-icon {
    display: none;
    position: absolute;
    right: 0;
    bottom: 0;
}
</style>
