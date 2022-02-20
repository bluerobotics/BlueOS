<template>
  <v-container>
    <v-card>
      <v-card-title><p>Welcome to BlueOS <strong>B.E.T.A test</strong>!</p></v-card-title>
      <v-card-text>
        <p>
          You are now running BlueOS <strong>B.E.T.A (Break it Early Test Application)</strong>!.<br>
          We have been working for the last couple of months on a totally new experience,
          and are now confident enough to open our work to a small number of users to test and check
          the changes!
        </p>
        <p>Be aware that the B.E.T.A may not be stable and changes will occur during the development.</p>
        <p>There are 3 types of releases on BlueOS.</p>
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
    <user-component />
  </v-container>
</template>

<script lang="ts">
import Vue from 'vue'

import externalComponent from '@/utils/external_component'

function UserComponent(): any {
  return externalComponent(
    'http://192.168.15.172:8000/UserComponent/UserComponent.umd.min.js',
  )
}

export default Vue.extend({
  name: 'Main',
  components: {
    UserComponent,
  },
})
</script>
