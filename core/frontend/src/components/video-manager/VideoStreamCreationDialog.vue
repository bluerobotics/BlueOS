<template>
  <v-dialog
    width="500"
    :value="show"
    @input="showDialog"
  >
    <v-card>
      <v-card-title>
        Stream creation
      </v-card-title>

      <v-card-text class="d-flex flex-column">
        <v-form
          ref="form"
          lazy-validation
        >
          <v-text-field
            v-model="stream_name"
            :counter="100"
            label="Stream name"
            :rules="[validate_required_field]"
          />

          <v-select
            v-model="selected_encode"
            :items="available_encodes"
            label="Encode"
            required
          />
          <v-select
            v-model="selected_size"
            :items="available_sizes"
            :label="size_selector_label"
            :disabled="!selected_format"
            required
          />
          <v-select
            v-model="selected_interval"
            :items="available_framerates"
            :label="framerate_selector_label"
            :disabled="!selected_size"
            required
          />

          <v-text-field
            v-model="stream_endpoint"
            label="Stream endpoint"
            :rules="[validate_required_field, is_udp_address]"
          />

          <v-btn
            color="success"
            class="mr-4"
            @click="createStream"
          >
            {{ finishButtonText }}
          </v-btn>
        </v-form>
      </v-card-text>
    </v-card>
  </v-dialog>
</template>

<script lang="ts">
import Vue, { PropType } from 'vue'

import {
  CreatedStream, Device, Format, FrameInterval, Size, StreamPrototype, VideoEncodeType,
} from '@/types/video'
import { VForm } from '@/types/vuetify'
import { isNotEmpty, isUdpAddress } from '@/utils/pattern_validators'

export default Vue.extend({
  name: 'VideoStreamCreationDialog',
  model: {
    prop: 'show',
    event: 'visibilityChange',
  },
  props: {
    show: {
      type: Boolean,
      default: false,
    },
    device: {
      type: Object as PropType<Device>,
      required: true,
    },
    finishButtonText: {
      type: String,
      required: false,
      default: 'Create',
    },
    stream: {
      type: Object as PropType<StreamPrototype>,
      required: false,
      default() {
        return {
          name: '',
          encode: null,
          dimensions: null,
          interval: null,
          endpoint: 'udp://0.0.0.0:5600',
        }
      },
    },
  },
  data() {
    const format_match = this.device.formats
      .find((format) => format.encode === this.stream.encode)
    const size_match = format_match?.sizes
      .find((size) => size.width === this.stream.dimensions?.width && size.height === this.stream.dimensions?.height)

    return {
      stream_name: this.stream.name,
      selected_encode: this.stream.encode,
      selected_size: size_match || null,
      selected_interval: this.stream.interval,
      stream_endpoint: this.stream.endpoint,
    }
  },
  computed: {
    form(): VForm {
      return this.$refs.form as VForm
    },
    created_stream(): (CreatedStream | null) {
      if (this.selected_encode === null
        || this.selected_size === null
        || this.selected_interval === null
        || this.stream_name === ''
        || this.stream_endpoint === '') {
        return null
      }
      return {
        name: this.stream_name,
        source: this.device.source,
        stream_information: {
          endpoints: [this.stream_endpoint],
          configuration: {
            encode: this.selected_encode,
            height: this.selected_size.height,
            width: this.selected_size.width,
            frame_interval: this.selected_interval,
          },
        },
      }
    },
    size_selector_label(): string {
      return this.selected_format ? 'Size' : 'Choose an encoding to show available sizes...'
    },
    framerate_selector_label(): string {
      return this.selected_size ? 'Framerate' : 'Choose a size to show available framerates...'
    },
    selected_format(): (Format | null) {
      if (this.selected_encode === null) {
        return null
      }
      const match_format = this.device.formats.find((format) => format.encode === this.selected_encode)
      return match_format === undefined ? null : match_format
    },
    available_encodes(): {text: string, value: VideoEncodeType}[] {
      // Filter out any unknown encode types
      const supported_formats = this.device.formats.filter((format) => typeof format.encode === 'string')
      return supported_formats.map((format) => ({
        text: format.encode, value: format.encode,
      }))
    },
    available_sizes(): {text: string, value: Size}[] {
      if (this.selected_format === null) {
        return []
      }
      return this.selected_format.sizes
        .map((size) => ({ text: `${size.width} x ${size.height}`, value: size }))
        .sort((a, b) => a.value.width - b.value.width)
        .reverse()
    },
    available_framerates(): {text: string, value: FrameInterval}[] {
      if (this.selected_size === null) {
        return []
      }
      return this.selected_size.intervals
        .map((interval) => ({ text: `${Math.round(interval.denominator / interval.numerator)} FPS`, value: interval }))
        .sort((a, b) => a.value.numerator - b.value.numerator)
    },
  },
  methods: {
    validate_required_field(input: string | null): (true | string) {
      return input !== null && isNotEmpty(input) ? true : 'Required field.'
    },
    is_udp_address(input: string): (true | string) {
      return isUdpAddress(input) ? true : 'Invalid UDP stream endpoint.'
    },
    createStream(): boolean {
      // Validate form before proceeding with API request
      if (!this.form.validate()) {
        return false
      }
      if (this.created_stream === null) {
        return false
      }
      this.$emit('streamChange', this.created_stream)
      this.showDialog(false)
      return true
    },
    showDialog(state: boolean) {
      this.$emit('visibilityChange', state)
    },
  },
})
</script>
