export interface ParamDefinitions {
  name: string,
  replacementTitle?: string,
  replacementDescription?: string,
  optional?: boolean,
  icon?: string
}

export interface FailsafeDependency {
  paramName: string,
  disabledValue: number,
  message: string,
}

export interface FailsafeDefinition {
  name: string,
  generalDescription: string,
  params: ParamDefinitions[],
  image: string,
  dependsOn?: FailsafeDependency,
}
