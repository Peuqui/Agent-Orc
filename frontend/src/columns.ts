// What a terminal in a workspace column (an iframe of the same origin) tells its workspace, and
// what the workspace tells its columns: events on the column's window.

/**
 * Marks the message field of a terminal page (our own input, which takes dictation and phone
 * keyboards in one piece; the terminal's own hidden input doubles words); the workspace focuses
 * it by this selector.
 */
export const MESSAGE_FIELD_ATTRIBUTE = 'data-message-field'
export const MESSAGE_FIELD_SELECTOR = `[${MESSAGE_FIELD_ATTRIBUTE}]`

/** Marks a permission request, to know whether the keyboard is on one already. */
export const APPROVAL_ATTRIBUTE = 'data-approval'
export const APPROVAL_SELECTOR = `[${APPROVAL_ATTRIBUTE}]`

/** Marks the first button of a permission request (Allow, or approving a plan): the Menu key brings
 * the keyboard there (see menuFromKeyboard). */
export const APPROVAL_FIRST_ATTRIBUTE = 'data-approval-first'
export const APPROVAL_FIRST_SELECTOR = `[${APPROVAL_FIRST_ATTRIBUTE}]`

/** Puts the keyboard on the first button of the page's permission request; false if none waits. */
export function focusApproval(page: Document | null | undefined): boolean {
  const first = page?.querySelector<HTMLElement>(APPROVAL_FIRST_SELECTOR)
  first?.focus()
  return first !== null && first !== undefined
}

/** A context menu asked for from the keyboard (the Menu key, Shift+F10), not by a click: no mouse
 * button pressed it (-1; a right click is 2). Its event comes on Windows when the key is let go,
 * so the key itself is not watched. */
export function menuFromKeyboard(event: MouseEvent): boolean {
  return event.button === -1
}

/** A sideways swipe in the terminal; detail: 1 next column, -1 previous. */
export const COLUMN_SWIPE_EVENT = 'agent-orc-column-swipe'
/** × in the terminal bar on phones, where the column has no tab of its own. */
export const COLUMN_CLOSE_EVENT = 'agent-orc-column-close'
/** From the workspace: show only terminal and input field; detail: on or off. */
export const COLUMN_FULLSCREEN_EVENT = 'agent-orc-column-fullscreen'
