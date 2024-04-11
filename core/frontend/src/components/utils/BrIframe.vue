<template>
  <v-sheet
    id="brIframe"
    width="100%"
    height="100%"
  >
    <spinning-logo
      v-if="!gl_compatible && !iframe_loaded"
      size="15%"
      subtitle="Loading external application..."
    />
    <canvas
      v-if="!iframe_loaded"
      v-show="gl_compatible"
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

import SpinningLogo from '../common/SpinningLogo.vue'

/**
 * Loading canvas  overlayvertex shader
 * @type {string}
 * @constant
 */
const vShaderSource = `
/** Vertex shader precision settings for performance */
precision mediump float;

/** Vertex shader attributes */
attribute vec2 aVertexPosition;

/** Uniforms */
uniform vec2 u_resolution;
uniform float u_time;

/** Shader entry point */
void main()
{
  /** Normalize vertex position */
  vec2 position = aVertexPosition * 2.0 - 1.0;

  /** Set vertex position */
  gl_Position = vec4(position, 0.0, 1.0);
}
`

/**
 * Loading canvas overlay fragment shader
 * @type {string}
 * @constant
 */
const fShaderSource = `
/** Precision settings for performance */
precision mediump float;

/** Uniforms */
uniform vec2 u_resolution;
uniform float u_time;

/** Definitions */
#define PI 3.1415
#define ALIASING 0.002
#define ASPECT u_resolution.x / u_resolution.y

/** BG Colors */
#define TOP_COLOR vec3(0.16, 0.6, 0.85)
#define MID_COLOR vec3(0.0, 0.5, 1.0)
#define BOTTOM_COLOR vec3(0.06, 0.32, 0.55)

/** Bubble Colors Overlay */
#define BUBBLE_COLOR vec3(0.0, 0.5, 1.0)
#define BUBBLE_BORDER_DARKEN vec3(0.001)

/** Logo Color */
#define LOGO_COLOR vec3(-0.18)


float rect(in vec2 st, in vec2 p, in vec2 size)
{
  st.x *= ASPECT;

  vec2 dist = min(st - p, p + size - st);
  return smoothstep(0.0, ALIASING, min(dist.x, dist.y)) * 10.0;
}

vec3 loading_logo(in vec2 st)
{
  /** Cross width size */
  float cross_w = 0.7;
  float m_h_cross_w = -(cross_w / 2.0);
  /** Small crosses width */
  float line_w = 0.119;
  /** Lines thickness */
  float line_t = 0.0455;
  /** Line width free of line thickness */
  float line_free = line_w - line_t;
  /** Space between details */
  float line_space = 0.0539;
  /** Loading speed */
  float speeded_t = 3.5 * u_time;

  float h_line_t = line_t / 2.0;

  /** Main cross */
  float logo = rect(st, vec2(-h_line_t, m_h_cross_w), vec2(line_t, cross_w));
  logo += rect(st, vec2(m_h_cross_w, -h_line_t), vec2(cross_w, line_t));

  float p3 = h_line_t + line_space;
  float p2 = p3 + line_t;
  float p1 = p3 + line_w;

  /** Right top small cross */
  float trc = rect(st, vec2(p3, p3), vec2(line_w, line_t));
  trc += rect(st, vec2(p3, p2 - ALIASING), vec2(line_t, line_free));
  /** Loading effect */
  trc *= cos(speeded_t) * 0.5 + 0.52;

  /** Right bottom small cross */
  float rbc = rect(st, vec2(p3, -p2), vec2(line_w, line_t));
  rbc += rect(st, vec2(p3, -p1 + ALIASING), vec2(line_t, line_free));
  /** Loading effect */
  rbc *= sin(speeded_t) * 0.5 + 0.52;

  /** Left bottom small cross */
  float lbc = rect(st, vec2(-p1 , -p2), vec2(line_w, line_t));
  lbc += rect(st, vec2(-p2 , -p1 + ALIASING), vec2(line_t, line_free));
  /** Loading effect */
  lbc *= cos(speeded_t - PI) * 0.5 + 0.52;

  /** Left top small cross */
  float tlc = rect(st, vec2(-p1 , p3), vec2(line_w, line_t));
  tlc += rect(st, vec2(-p2 , p2 - ALIASING), vec2(line_t, line_free));
  /** Loading effect */
  tlc *= sin(speeded_t - PI) * 0.5 + 0.52;

  /** Return clamped logo alpha */
  return clamp(logo + lbc + rbc + tlc + trc, 0.0, 1.0) * LOGO_COLOR;
}

vec3 bubble(in vec2 st, in vec2 pos, in float radius)
{
  st.x *= ASPECT;

  /** Distance from the bubble center */
  float p_distance = distance(st, pos);

  float radius_factor = clamp(radius / p_distance, 0.0, 0.35) * smoothstep(radius, radius * 0.65, p_distance);
  float border = step(radius - 0.005, p_distance) - step(radius, p_distance);

  return BUBBLE_COLOR * radius_factor + (border * BUBBLE_BORDER_DARKEN);
}

vec3 render_bubbles(in vec2 st)
{
  vec3 color = vec3(0.0);

  /** Add random bubbles */
  for (int i = 0; i < 150; ++i)
  {
    /** Creates float index to allow using in math operations */
    float index = float(i);

    /**
     * Bubble radius, use a high freq cos with index offset to create
     * a random radius for each bubble and use square power to make
     * enphasys on the big bubbles
     */
    float radius = 0.1 + cos(index * 543.0 + 2.32) * 0.09;
    /** Square the radius to evidentiate bigger bubbles */
    radius *= radius;

    /**
     * Bigger bubbles move faster than the smaller ones, giving perspective
     */
    float x_pos = sin(index * (1.111 + sin(u_time * (0.002 + radius * 0.09)) * 0.2) + 2.1) * ASPECT;

    /**
     * Bigger bubbles raise faster than the smaller ones
     */
    float radius_offset = 2.0 * radius + 1.0;
    float y_pos = -radius_offset + mod(u_time * (0.2 + sqrt(radius * 1.5)) + index * 0.1, radius_offset + 1.0);

    /**
     * Bubble position, use a high freq sin with index offset to create a
     * random position for each bubble and use mod to make the bubbles
      * move in a loop from bottom to top
     */
    color += bubble(st, vec2(x_pos, y_pos), radius);
  }

  return color;
}

vec3 background(in vec2 st)
{
  /** Gradient color */
  vec3 color = mix(BOTTOM_COLOR, MID_COLOR, smoothstep(-1.0, -0.1, st.y));
  color = mix(color, TOP_COLOR, smoothstep(-0.1, 1.0, st.y));

  return color;
}

/** Shader entry point */
void main()
{
  /**
   * Normalized centered origin, converts system to center of the screen ranging
   * from -1 to 1
   */
  vec2 st = (gl_FragCoord.xy * 2.0 - u_resolution.xy) / u_resolution.xy;

  /** Background color */
  vec3 color = background(st);

  /** Add bubbles */
  color += render_bubbles(st);

  /** Add logo */
  color += loading_logo(st) * smoothstep(0.0, 3.0, u_time);

  /** Output to screen with clamping to avoid overflow */
  gl_FragColor = vec4(clamp(color, vec3(0.0), vec3(1.0)), 1.0);
}
`

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
      gl_compatible: false,
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
  methods: {
    loadFinished(): void {
      this.iframe_loaded = true
    },
    canvasSetup(): void {
      // TODO - Set resize event listener
      this.resizeCanvas()

      const ctx = this.gl as WebGLRenderingContext

      this.canvas_gl_program = this.initShaderProgram(ctx, vShaderSource, fShaderSource)
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
    resizeCanvas(): void {
      const canvas = this.$refs.webglCanvas as HTMLCanvasElement

      // TODO - Handle real size
      canvas.width = 1650
      canvas.height = 890
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
      requestAnimationFrame(() => this.drawScene())
    },
  },
})
</script>
<style scoped>
iframe {
  display: block;
}
</style>
