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


/**
 * Utility functions for clipboard operations
 */

/**
 * Fallback method to copy text to clipboard using a temporary input element
 * @param text - The text to copy to clipboard
 * @returns boolean indicating if the copy operation succeeded
 */
const copyWithFallbackMethod = (text: string): boolean => {
  const temporaryInputElement = document.createElement('input')
  temporaryInputElement.value = text
  document.body.appendChild(temporaryInputElement)

  try {
      temporaryInputElement.select()
      document.execCommand('copy')
      return true
  } catch (error) {
      console.error(`Failed to copy text to clipboard. Reason: ${error}`)
      return false
  } finally {
      document.body.removeChild(temporaryInputElement)
  }
}

/**
* Copy text using the Clipboard API
* @param text - The text to copy to clipboard
* @param fallback - Optional callback to handle fallback behavior
* @returns Promise<boolean> indicating if the copy operation succeeded
*/
const copyWithClipboardAPI = async (text: string, fallback?: () => boolean): Promise<boolean> => {
  try {
      await navigator.clipboard.writeText(text)
      return true
  } catch (error) {
      console.error(`Failed to copy text to clipboard using Clipboard API. Reason: ${error}`)
      if (fallback) {
          return fallback()
      }
      return copyWithFallbackMethod(text)
  }
}

/**
* Main function to copy text to clipboard with permission handling
* @param text - The text to copy to clipboard
* @returns Promise<boolean> indicating if the copy operation succeeded
*/
export const copyToClipboard = async (text: string): Promise<boolean> => {
  try {
      const permissionStatus = await navigator.permissions.query({ name: 'clipboard-write' as PermissionName })

      if (permissionStatus.state === 'granted') {
          return await copyWithClipboardAPI(text)
      } else if (permissionStatus.state === 'prompt') {
          // The user will be prompted to grant the permission
          return new Promise((resolve) => {
              permissionStatus.onchange = async () => {
                  if (permissionStatus.state === 'granted') {
                      resolve(await copyWithClipboardAPI(text))
                  } else {
                      resolve(copyWithFallbackMethod(text))
                  }
              }
          })
      } else {
          return copyWithFallbackMethod(text)
      }
  } catch (error) {
      console.error('Error while requesting clipboard-write permission:', error)
      return copyWithFallbackMethod(text)
  }
}

