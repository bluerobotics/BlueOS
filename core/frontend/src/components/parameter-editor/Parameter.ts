export default class Parameter {
name = ''

value: string | number = ''

readonly = false

description = ''

options: string[] = []

constructor(name: string, value: string | number) {
  this.name = name
  this.value = value
}

setDescription(description: string): void {
  this.description = description
}

setReadOnly(readonly: boolean): void {
  this.readonly = readonly
}
}
