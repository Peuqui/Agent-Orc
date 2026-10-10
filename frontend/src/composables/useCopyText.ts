import { useToast } from './useToast'

/** Copies a text to the clipboard and tells so (`message`), or tells why not. */
export function useCopyText(): (text: string, message: string) => Promise<void> {
  const toast = useToast()
  return async (text, message) => {
    try {
      await navigator.clipboard.writeText(text)
      toast.info(message)
    } catch (error) {
      toast.error(error)
    }
  }
}
