export interface StreamingResponse {
  fragment: number
  status: number
  data?: string
  error?: string
}

export type ConditionalHandlerFn = (fragment: StreamingResponse, buffer: string) => boolean

/**
 * Parse a string data into an array of streaming response fragments
 * @param {string} data Data to be parsed as string
 * @param {boolean} decode If true, decodes the data from base64 to string
 * @returns {StreamingResponse[]} Array of streaming response fragments
 */
export function parseStreamingResponse(data: string, decode = true): StreamingResponse[] {
  const fragments: StreamingResponse[] = []

  // In the backend we use this as split identifier
  // TODO: If the error includes this split identifier it will break the parsing
  const lines = data.split('|\n\n|')
  for (const line of lines) {
    try {
      const parsed = JSON.parse(line) as StreamingResponse

      // Data can be a null value as well as initial fragment will have value 0
      if ('fragment' in parsed && 'data' in parsed && 'status' in parsed) {
        // As we also want to push the fragment if data is null because errors will have no data, so the decoding
        // should be in this separated inner if
        if (decode && parsed.data) {
          parsed.data = atob(parsed.data)
        }
        fragments.push(parsed)
      }
    } catch (error) {
      // If the error is a SyntaxError, it means that we reached curretn end of the stream
      if (error instanceof SyntaxError) {
        break
      }
      console.error('On decoding streaming response expected to get SyntaxError but got: ', error)
    }
  }

  return fragments
}

function defaultInvalidHandler(fragment: StreamingResponse): boolean {
  console.error('Invalid fragment in streaming response: ', fragment)

  /** Stops aggregation */
  return false
}

function defaultValidator(fragment: StreamingResponse): boolean {
  return !(fragment.status >= 400 || fragment.error)
}

/**
 * Aggregate streaming response fragments into a single string and validate them
 * @param {StreamingResponse[]} fragments Array of streaming response fragments
 * @param {ConditionalHandlerFn} onInvalid Handler for invalid fragments, must return a boolean to continue or stop
 * aggregation, by default it logs the invalid fragment and stops aggregation, when aggregation is stopped it returns
 * undefined
 * @param {ConditionalHandlerFn} validator Validator for fragments, decides if the fragment is valid or not by default
 * it checks if the status is greater than 400 or if there is an error
 * @param {boolean} dropHeartbeats If true, it will drop the heartbeats from the aggregation
 * @returns {string | undefined} Aggregated string or undefined if the aggregation was stopped
 */
export function aggregateStreamingResponse(
  fragments: StreamingResponse[],
  onInvalid: ConditionalHandlerFn = defaultInvalidHandler,
  validator: ConditionalHandlerFn = defaultValidator,
  dropHeartbeats = true,
): string | undefined {
  if (dropHeartbeats) {
    fragments = fragments.filter((fragment) => fragment.fragment !== -1)
  }

  let buffer = ''
  for (const fragment of fragments) {
    if (!validator(fragment, buffer)) {
      if (!onInvalid(fragment, buffer)) {
        return undefined
      }
    }
    buffer += fragment.data ?? ''
  }

  return buffer
}
