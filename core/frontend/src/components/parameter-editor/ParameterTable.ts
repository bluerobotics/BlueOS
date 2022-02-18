import Parameter from './Parameter'

export default class ParametersTable {
    parameters: Parameter[] = []

    count = 0

    addParam(param: Parameter): void {
      this.parameters.push(param)
    }

    setCount(count: number): void {
      this.count = count
    }
}
