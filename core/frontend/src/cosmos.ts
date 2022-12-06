export {}

declare global {
    interface Array<T> {
        first(): T | undefined;
        isEmpty(): boolean;
    }

    interface String {
      isEmpty(): boolean;
      toTitle(): string;
  }
}

// eslint-disable-next-line
Array.prototype.first = function<T> (this: T[]): T | undefined {
  return this.isEmpty() ? undefined : this[0]
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
String.prototype.toTitle = function (this: string): string {
  if (this.length < 1) {
    return this
  }
  if (this.length === 1) {
    return this.toUpperCase()
  }
  return this[0].toUpperCase() + this.substring(1)
}
