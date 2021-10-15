<template>
  <v-container>
    <v-bottom-sheet
      :value="true"
      inset
    >
      <v-card>
        <v-card-title>Mavlink connection change</v-card-title>
        <v-card-text>
          New Companion doesn't provide a fixed UDP Client endpoint on 192.168.2.1 anymore. For new
          connections Companion now provides an UDP Server locally on port 14550.

          For connecting QGroundControl, for example, please go to Comm Links and create an
          UDP endpoint pointing to companion.local or Companion's IP address (e.g.:192.168.2.2), on port 14550.
          <v-card-text />
        </v-card-text>
      </v-card>
    </v-bottom-sheet>
    <v-card>
      <v-card-title><p>Welcome to companion <strong>B.E.T.A test</strong>!</p></v-card-title>
      <v-card-text>
        <p>
          You are now running Companion <strong>B.E.T.A (Break it Early Test Application)</strong>!.<br>
          We have been working for the last couple of months on a totally new experience on the companion computer,
          and are now confident enough to open our work to a small number of users to test and check
          the changes!
        </p>
        <p>Be aware that the B.E.T.A may not be stable and changes will occur during the development.</p>
        <p>There are 3 types of releases on the new Companion.</p>
        <ul>
          <li>
            "Stable" releases, that are not available in this B.E.T.A
            <ul>
              <li>Stable and long supported versions</li>
            </ul>
          </li>
          <li>
            "B.E.T.A" releases
            <ul>
              <li>Versions that will be released after an internal test</li>
            </ul>
          </li>
          <li>
            "Master" releases, not recommended
            <ul>
              <li>The very latest features, that may not have been tested yet</li>
            </ul>
          </li>
        </ul>
        <br>
        We recommend using only the B.E.T.A releases.
        <v-card-text />
      </v-card-text>
    </v-card>
  </v-container>
</template>

<script lang="ts">
import Vue from 'vue'

export default Vue.extend({
  name: 'Main',
  components: {
  },
})
</script>
