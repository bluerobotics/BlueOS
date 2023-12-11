export function degrees (radians: number): number {
  return radians * 180 / Math.PI
}

export class Vector3 {
  x: number;
  y: number;
  z: number;

  constructor (x: number, y: number, z: number) {
    this.x = x;
    this.y = y;
    this.z = z;
  }

  subtract (v: Vector3): Vector3 {
    this.x = this.x - v.x;
    this.y = this.y - v.y;
    this.z = this.z - v.z;
    return this;
  }

  add (v: Vector3): Vector3 {
    this.x = this.x + v.x;
    this.y = this.y + v.y;
    this.z = this.z + v.z;
    return this;
  }

  multiply (s: number): Vector3 {
    this.x = this.x * s;
    this.y = this.y * s;
    this.z = this.z * s;
    return this;
  }

  length (): number {
    return Math.sqrt(this.x * this.x + this.y * this.y + this.z * this.z);
  }

  equals (v: Vector3): boolean {
    return this.x === v.x && this.y === v.y && this.z === v.z;
  }
}

export class Matrix3 {
    private _elements: number[];

    constructor (
      i11: number | Vector3 = 0, 
      i12: number | Vector3 = 0, 
      i13: number | Vector3 = 0, 
      i21: number = 0, 
      i22: number = 0, 
      i23: number = 0, 
      i31: number = 0, 
      i32: number = 0, 
      i33: number = 0
    ) {
      // check if we're receiving 3 vector3, if so, use its elements:
      if (i11 instanceof Vector3 &&
          i12 instanceof Vector3 &&
          i13 instanceof Vector3) {
          this._elements = [
              i11.x, i11.y, i11.z,
              i12.x, i12.y, i12.z,
              i13.x, i13.y, i13.z
          ]
          return
      }
      this._elements = [i11 as number, i12 as number, i13 as number, i21, i22, i23, i31, i32, i33]
    }

    get a (): Vector3 {
      return new Vector3(
          this._elements[0],
          this._elements[1],
          this._elements[2]
      )
    }

    get b (): Vector3 {
      return new Vector3(
          this._elements[3],
          this._elements[4],
          this._elements[5]
      )
    }


    get c () {
        return new Vector3(
            this._elements[6],
            this._elements[7],
            this._elements[8]
        )
    }

    fromEuler (roll: number, pitch: number, yaw: number) {
        this._elements = []
        const cp = Math.cos(pitch)
        const sp = Math.sin(pitch)
        const sr = Math.sin(roll)
        const cr = Math.cos(roll)
        const sy = Math.sin(yaw)
        const cy = Math.cos(yaw)
        this._elements.push(cp * cy)
        this._elements.push((sr * sp * cy) - (cr * sy))
        this._elements.push((cr * sp * cy) + (sr * sy))
        this._elements.push(cp * sy)
        this._elements.push((sr * sp * sy) + (cr * cy))
        this._elements.push((cr * sp * sy) - (sr * cy))
        this._elements.push(-sp)
        this._elements.push(sr * cp)
        this._elements.push(cr * cp)
        return this
    }

    e (i) {
        // validate?
        return this._elements[i]
    }

    times (vector: Vector3): Vector3 {
        return new Vector3(
            this._elements[0] * vector.x + this._elements[1] * vector.y + this._elements[2] * vector.z,
            this._elements[3] * vector.x + this._elements[4] * vector.y + this._elements[5] * vector.z,
            this._elements[6] * vector.x + this._elements[7] * vector.y + this._elements[8] * vector.z
        )
    }

    multiply (matrix: Matrix3): Matrix3 {
        const m = this._elements
        const n = matrix._elements
        return new Matrix3(
            m[0] * n[0] + m[1] * n[3] + m[2] * n[6],
            m[0] * n[1] + m[1] * n[4] + m[2] * n[7],
            m[0] * n[2] + m[1] * n[5] + m[2] * n[8],
            m[3] * n[0] + m[4] * n[3] + m[5] * n[6],
            m[3] * n[1] + m[4] * n[4] + m[5] * n[7],
            m[3] * n[2] + m[4] * n[5] + m[5] * n[8],
            m[6] * n[0] + m[7] * n[3] + m[8] * n[6],
            m[6] * n[1] + m[7] * n[4] + m[8] * n[7],
            m[6] * n[2] + m[7] * n[5] + m[8] * n[8]
        )
    }

    transposed (): Matrix3 {
        return new Matrix3(
            this._elements[0], this._elements[3], this._elements[6],
            this._elements[1], this._elements[4], this._elements[7],
            this._elements[2], this._elements[5], this._elements[8]
        )
    }

    determinant (): number {
        const m = this._elements
        return m[0] * m[4] * m[8] -
            m[0] * m[5] * m[7] -
            m[1] * m[3] * m[8] +
            m[1] * m[5] * m[6] +
            m[2] * m[3] * m[7] -
            m[2] * m[4] * m[6]
    }

    invert (): Matrix3 | null {
        const d = this.determinant()
        if (d === 0) {
            return null
        }
        const invD = 1 / d
        const m = this._elements
        return new Matrix3(
            invD * (m[8] * m[4] - m[7] * m[5]),
            invD * -(m[8] * m[1] - m[7] * m[2]),
            invD * (m[5] * m[1] - m[4] * m[2]),
            invD * -(m[8] * m[3] - m[6] * m[5]),
            invD * (m[8] * m[0] - m[6] * m[2]),
            invD * -(m[5] * m[0] - m[3] * m[2]),
            invD * (m[7] * m[3] - m[6] * m[4]),
            invD * -(m[7] * m[0] - m[6] * m[1]),
            invD * (m[4] * m[0] - m[3] * m[1])
        )
    }
}

