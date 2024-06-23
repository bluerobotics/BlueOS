export interface ParamDefinitions {
  name: string,
  replacementTitle?: string,
  replacementDescription?: string,
  optional?: boolean,
  icon?: string
}

export interface FailsafeDefinition {
  name: string,
  generalDescription: string,
  params: ParamDefinitions[],
  image: string,
}
