<template>
  <v-sheet
    width="100%"
    height="100%"
    style="overflow: hidden;"
  >
    <spinning-logo
      v-if="!gl_compatible && !iframe_loaded"
      size="15%"
      subtitle="Loading external application..."
    />
    <canvas
      v-if="gl_compatible && !iframe_loaded"
      ref="webglCanvas"
    />
    <iframe
      v-show="iframe_loaded"
      :title="`iframe-${source}`"
      :src="source"
      height="100%"
      width="100%"
      frameBorder="0"
      allowfullscreen
      @load="loadFinished"
    />
  </v-sheet>
</template>

<script lang="ts">
import Vue from 'vue'

import { basic2dVertexShaderSource, bubbles2dFragmentShaderSource } from '@/utils/shaders'

import SpinningLogo from '../common/SpinningLogo.vue'

/**
 * Plane vertices for the canvas overlay
 * @type {number[]}
 * @constant
 */
const planeVertices: number[] = [
  -1.0, -1.0,
  -1.0, 1.0,
  1.0, -1.0,
  1.0, 1.0,
]

export default Vue.extend({
  name: 'BrIframe',
  components: {
    SpinningLogo,
  },
  props: {
    source: {
      type: String,
      required: true,
    },
  },
  data() {
    return {
      iframe_loaded: false,
      gl_compatible: true,
      gl: null as WebGLRenderingContext | null,
      canvas_gl_program: null as WebGLProgram | null,
      plane_buffer: null as WebGLBuffer | null,
      plane_a_vertex_loc: 0,
      u_resolution_loc: null as WebGLUniformLocation | null,
      u_time_loc: null as WebGLUniformLocation | null,
      start_time: Date.now(),
    }
  },
  mounted() {
    // Load GL Context at first
    this.loadGlContext()

    // If compatible, setup canvas overlay using GL
    if (this.gl_compatible) {
      this.canvasSetup()
    }
  },
  beforeDestroy() {
    // If compatible clear GL resources
    if (this.gl_compatible) {
      window.removeEventListener('resize', this.resizeCanvas)
      this.clearGLResources()
    }
  },
  methods: {
    loadFinished(): void {
      this.iframe_loaded = true
    },
    clearGLResources(): void {
      const ctx = this.gl as WebGLRenderingContext

      ctx.disableVertexAttribArray(this.plane_a_vertex_loc)

      if (this.plane_buffer) {
        ctx.deleteBuffer(this.plane_buffer)
        this.plane_buffer = null
      }

      if (this.canvas_gl_program) {
        const vertexShader = ctx.getAttachedShaders(this.canvas_gl_program)?.[0]
        const fragmentShader = ctx.getAttachedShaders(this.canvas_gl_program)?.[1]

        if (vertexShader) {
          ctx.detachShader(this.canvas_gl_program, vertexShader)
          ctx.deleteShader(vertexShader)
        }

        if (fragmentShader) {
          ctx.detachShader(this.canvas_gl_program, fragmentShader)
          ctx.deleteShader(fragmentShader)
        }

        ctx.deleteProgram(this.canvas_gl_program)
        this.canvas_gl_program = null
      }

      ctx.clear(ctx.COLOR_BUFFER_BIT | ctx.DEPTH_BUFFER_BIT)
      ctx.finish()
    },
    canvasSetup(): void {
      this.setInitialCanvasSize()
      window.addEventListener('resize', this.resizeCanvas)

      const ctx = this.gl as WebGLRenderingContext

      this.canvas_gl_program = this.initShaderProgram(ctx, basic2dVertexShaderSource, bubbles2dFragmentShaderSource)
      if (!this.canvas_gl_program) {
        console.log('Unable to initialize the shader program')
        this.gl_compatible = false
        return
      }

      this.u_resolution_loc = ctx.getUniformLocation(this.canvas_gl_program, 'u_resolution')
      this.u_time_loc = ctx.getUniformLocation(this.canvas_gl_program, 'u_time')

      if (!this.u_resolution_loc || !this.u_time_loc) {
        console.log('Unable to get resolution and time uniform locations')
        this.gl_compatible = false
        return
      }

      this.plane_a_vertex_loc = ctx.getAttribLocation(this.canvas_gl_program, 'aVertexPosition')
      this.plane_buffer = ctx.createBuffer()
      ctx.bindBuffer(ctx.ARRAY_BUFFER, this.plane_buffer)
      ctx.bufferData(ctx.ARRAY_BUFFER, new Float32Array(planeVertices), ctx.STATIC_DRAW)

      this.drawScene()
    },
    setInitialCanvasSize(): void {
      const canvas = this.$refs.webglCanvas as HTMLCanvasElement

      canvas.width = this.$el.clientWidth
      canvas.height = this.$el.clientHeight
    },
    resizeCanvas(): void {
      const canvas = this.$refs.webglCanvas as HTMLCanvasElement

      canvas.width = this.$el.clientWidth
    },
    loadGlContext(): void {
      const canvas = this.$refs.webglCanvas as HTMLCanvasElement
      this.gl = canvas.getContext('webgl')
      this.gl_compatible = Boolean(this.gl)
    },
    loadShader(ctx: WebGLRenderingContext, type: GLenum, source: string): WebGLShader | null {
      const shader = ctx.createShader(type)

      if (!shader) {
        console.log(`Unable to create shader of type ${type}`)
        return null
      }

      ctx.shaderSource(shader, source)
      ctx.compileShader(shader)

      if (!ctx.getShaderParameter(shader, ctx.COMPILE_STATUS)) {
        console.log(`An error occurred compiling the shaders: ${ctx.getShaderInfoLog(shader)}`)
        ctx.deleteShader(shader)
        return null
      }

      return shader
    },
    initShaderProgram(ctx: WebGLRenderingContext, vShader: string, fSahder: string): WebGLProgram | null {
      const vertexShader = this.loadShader(ctx, ctx.VERTEX_SHADER, vShader)
      const fragmentShader = this.loadShader(ctx, ctx.FRAGMENT_SHADER, fSahder)

      const shaderProgram = ctx.createProgram()

      if (!shaderProgram || !vertexShader || !fragmentShader) {
        return null
      }

      ctx.attachShader(shaderProgram, vertexShader)
      ctx.attachShader(shaderProgram, fragmentShader)
      ctx.linkProgram(shaderProgram)

      if (!ctx.getProgramParameter(shaderProgram, ctx.LINK_STATUS)) {
        console.log(`Unable to initialize the shader program: ${ctx.getProgramInfoLog(shaderProgram)}`)
        return null
      }

      return shaderProgram
    },
    drawScene(): void {
      const ctx = this.gl as WebGLRenderingContext
      const currentTime = (Date.now() - this.start_time) / 1000.0

      ctx.clearColor(0.0, 0.0, 0.0, 1.0)
      ctx.clear(ctx.COLOR_BUFFER_BIT | ctx.DEPTH_BUFFER_BIT)

      ctx.viewport(0, 0, ctx.canvas.width, ctx.canvas.height)

      ctx.useProgram(this.canvas_gl_program)

      ctx.uniform2f(this.u_resolution_loc, ctx.canvas.width, ctx.canvas.height)
      ctx.uniform1f(this.u_time_loc, currentTime)

      ctx.bindBuffer(ctx.ARRAY_BUFFER, this.plane_buffer)
      ctx.vertexAttribPointer(this.plane_a_vertex_loc, 2, ctx.FLOAT, false, 0, 0)
      ctx.enableVertexAttribArray(this.plane_a_vertex_loc)

      ctx.drawArrays(ctx.TRIANGLE_STRIP, 0, 4)

      // Request animation frame for continuous rendering
      if (!this.iframe_loaded) {
        requestAnimationFrame(() => this.drawScene())
      }
    },
  },
})
</script>
<style scoped>
iframe {
  display: block;
}
</style>
