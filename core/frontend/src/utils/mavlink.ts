import { get } from 'lodash'

export default function mavlink_store_get<T>(storage: T, path: string, system_id? :number, component_id?: number): unknown {
  if (system_id !== undefined && component_id !== undefined) {
    return get(storage, `available_identified_messages.${system_id}_${component_id}.${path}`)
  }
  return get(storage, `available_messages.${path}`)
}
