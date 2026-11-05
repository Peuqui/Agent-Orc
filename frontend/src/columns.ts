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
 * the keyboard there (see listenForMenuKey). */
export const APPROVAL_FIRST_ATTRIBUTE = 'data-approval-first'
export const APPROVAL_FIRST_SELECTOR = `[${APPROVAL_FIRST_ATTRIBUTE}]`

/** Puts the keyboard on the first button of the page's permission request; false if none waits. */
export function focusApproval(page: Document | null | undefined): boolean {
  const first = page?.querySelector<HTMLElement>(APPROVAL_FIRST_SELECTOR)
  first?.focus()
  return first !== null && first !== undefined
}

/** Calls onMenu when the context menu is asked for from the keyboard (the Menu key, Shift+F10)
 * on this page, instead of opening it. Only a key pressed just before counts: on a touch screen a
 * long press or dragging the handles of a text selection asks for a context menu too, with no
 * mouse button like the key, and it must open the selection's own menu (copy). The menu comes
 * when the key goes down or, on Windows, when it is let go; no other key goes down in between.
 * Returns what stops listening. */
export function listenForMenuKey(page: Window, onMenu: () => void): () => void {
  let menuKeyDown = false
  const noteKey = (event: KeyboardEvent): void => {
    menuKeyDown = event.key === 'ContextMenu' || (event.shiftKey && event.key === 'F10')
  }
  const onContextMenu = (event: MouseEvent): void => {
    if (!menuKeyDown) return
    menuKeyDown = false
    event.preventDefault()
    onMenu()
  }
  page.addEventListener('keydown', noteKey, true)
  page.addEventListener('contextmenu', onContextMenu, true)
  return () => {
    page.removeEventListener('keydown', noteKey, true)
    page.removeEventListener('contextmenu', onContextMenu, true)
  }
}

/** A sideways swipe in the terminal; detail: 1 next column, -1 previous. */
export const COLUMN_SWIPE_EVENT = 'agent-orc-column-swipe'
/** × in the terminal bar on phones, where the column has no tab of its own. */
export const COLUMN_CLOSE_EVENT = 'agent-orc-column-close'
/** From the workspace: show only terminal and input field; detail: on or off. */
export const COLUMN_FULLSCREEN_EVENT = 'agent-orc-column-fullscreen'
