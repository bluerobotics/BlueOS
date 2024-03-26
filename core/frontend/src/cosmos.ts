export {}

declare global {
    interface Array<T> {
        first(): T | undefined;
        last(): T | undefined;
        isEmpty(): boolean;
    }

    interface String {
      isEmpty(): boolean;
      splitOnce(separator: string): [string, string] | undefined
      toTitle(): string;
  }
}

// eslint-disable-next-line
Array.prototype.first = function<T> (this: T[]): T | undefined {
  return this[0]
}

// eslint-disable-next-line
Array.prototype.last = function<T> (this: T[]): T | undefined {
  return this.at(-1)
}

// eslint-disable-next-line
Array.prototype.isEmpty = function<T> (this: T[]): boolean {
  return this.length === 0
}

// eslint-disable-next-line
String.prototype.isEmpty = function (this: String): boolean {
  return this.length === 0
}

// eslint-disable-next-line
String.prototype.splitOnce = function (this: string, separator: string): [string, string] | undefined {
  const index = this.indexOf(separator)
  if (index === -1) {
    return undefined
  }
  const first = this.substring(0, index)
  const second = this.substring(index + separator.length)
  return [first, second]
}

// eslint-disable-next-line
String.prototype.toTitle = function (this: string): string {
  if (this.length < 1) {
    return this
  }
  if (this.length === 1) {
    return this.toUpperCase()
  }
  return this[0].toUpperCase() + this.substring(1)
}
