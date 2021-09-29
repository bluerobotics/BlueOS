import { get } from 'lodash'

export default function mavlink_store_get<T>(storage: T, path: string): unknown {
  return get(storage, `available_messages.${path}`)
}
