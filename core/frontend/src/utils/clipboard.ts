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

