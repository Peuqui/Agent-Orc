/** Enter sends (also the phone keyboard's send key); Shift+Enter starts a new line, and a word
 * still being composed (an input method, the phone's suggestions) is not sent half done. */
export function isSendKey(event: KeyboardEvent): boolean {
  return event.key === 'Enter' && !event.shiftKey && !event.isComposing
}
