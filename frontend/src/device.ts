// A finger rather than a mouse is the main pointer (phones, tablets without a mouse): there,
// giving an input field the focus by itself would open the on-screen keyboard.
export const TOUCH_FIRST = window.matchMedia('(pointer: coarse)')

// Phone-sized screens (below Tailwind's md): the workspace shows one column at a time there.
// Measured on the browser window, also inside a workspace column (an iframe of the same
// origin): a narrow column on a computer is no phone.
export const PHONE_WIDTH = (window.top ?? window).matchMedia('(max-width: 767px)')

// Room for the workspace tabs in one row even with a single column: tablets held upright (about
// 600 CSS pixels wide), not phones (about 440, measured on a Realme GT Neo2 at 1080 px).
export const TABS_WIDTH = (window.top ?? window).matchMedia('(min-width: 520px)')

// Track width in pixels of the jog (scroll strip) at the right edge of a terminal or an answers
// list. A finger needs about 40 px, a mouse less; kept a little under that, as the grip is
// touched on the whole track. Things laid over the list keep clear of it.
export const JOG_TRACK_WIDTH_PX = 20
