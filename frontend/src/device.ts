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
