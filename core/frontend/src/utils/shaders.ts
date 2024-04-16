/**
 * Loading canvas overlay vertex shader
 *   Requires Attributes:
 *     - attribute_vertex_position: vec2 (Vertex position)
 *
 * @type {string}
 * @constant
 */
export const basic2dVertexShaderSource = `
/** Vertex shader precision settings for performance */
precision mediump float;

/** Vertex shader attributes */
attribute vec2 attribute_vertex_position;

/** Shader entry point */
void main()
{
  /** Normalize vertex position */
  vec2 position = attribute_vertex_position * 2.0 - 1.0;

  /** Set vertex position */
  gl_Position = vec4(position, 0.0, 1.0);
}
`

/**
 * Loading canvas overlay fragment shader
 *   Requires Uniforms:
 *     - uniform_resolution: vec2 (Canvas resolution)
 *     - uniform_time: float (Time in seconds)
 * @type {string}
 * @constant
 */
export const bubbles2dFragmentShaderSource = `
/** Precision settings for performance */
precision mediump float;

/** Uniforms */
uniform vec2 uniform_resolution;
uniform float uniform_time;

/** Definitions */
#define PI 3.1415
#define ALIASING 0.002
#define ASPECT uniform_resolution.x / uniform_resolution.y

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
  float speeded_t = 3.5 * uniform_time;

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
      * emphases on the big bubbles
      */
    float radius = 0.1 + cos(index * 543.0 + 2.32) * 0.09;
    /** Square the radius to evidentiate bigger bubbles */
    radius *= radius;

    /**
      * Bigger bubbles move faster than the smaller ones, giving perspective
      */
    float x_pos = sin(index * (1.111 + sin(uniform_time * (0.002 + radius * 0.09)) * 0.2) + 2.1) * ASPECT;

    /**
      * Bigger bubbles raise faster than the smaller ones
      */
    float radius_offset = 2.0 * radius + 1.0;
    float y_pos = -radius_offset + mod(uniform_time * (0.2 + sqrt(radius * 1.5)) + index * 0.1, radius_offset + 1.0);

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
  vec2 st = (gl_FragCoord.xy * 2.0 - uniform_resolution.xy) / uniform_resolution.xy;

  /** Background color */
  vec3 color = background(st);

  /** Add bubbles */
  color += render_bubbles(st);

  /** Add logo */
  color += loading_logo(st) * smoothstep(0.0, 3.0, uniform_time);

  /** Output to screen with clamping to avoid overflow */
  gl_FragColor = vec4(clamp(color, vec3(0.0), vec3(1.0)), 1.0);
}
`
