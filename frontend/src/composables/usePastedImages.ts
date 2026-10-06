/**
 * The pictures in a paste (e.g. a screenshot from the clipboard). They arrive as items of kind
 * "file" (Windows screenshots do not always show up in clipboardData.files).
 */
export function pastedImages(event: ClipboardEvent): File[] {
  return [...(event.clipboardData?.items ?? [])]
    .filter((item) => item.kind === 'file' && item.type.startsWith('image/'))
    .map((item) => item.getAsFile())
    .filter((file) => file !== null)
}
