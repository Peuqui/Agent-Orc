// What a terminal in a workspace column (an iframe of the same origin) tells its workspace, and
// what the workspace tells its columns: events on the column's window.

/**
 * Marks the message field of a terminal page (our own input, which takes dictation and phone
 * keyboards in one piece; the terminal's own hidden input doubles words); the workspace focuses
 * it by this selector.
 */
export const MESSAGE_FIELD_ATTRIBUTE = 'data-message-field'
export const MESSAGE_FIELD_SELECTOR = `[${MESSAGE_FIELD_ATTRIBUTE}]`

/** A sideways swipe in the terminal; detail: 1 next column, -1 previous. */
export const COLUMN_SWIPE_EVENT = 'agent-orc-column-swipe'
/** × in the terminal bar on phones, where the column has no tab of its own. */
export const COLUMN_CLOSE_EVENT = 'agent-orc-column-close'
/** From the workspace: show only terminal and input field; detail: on or off. */
export const COLUMN_FULLSCREEN_EVENT = 'agent-orc-column-fullscreen'
