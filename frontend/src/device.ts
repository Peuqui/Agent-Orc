// A finger rather than a mouse is the main pointer (phones, tablets without a mouse): there,
// giving an input field the focus by itself would open the on-screen keyboard.
export const TOUCH_FIRST = window.matchMedia('(pointer: coarse)')

// Phone-sized screens (below Tailwind's md): the workspace shows one column at a time there.
// Measured on the browser window, also inside a workspace column (an iframe of the same
// origin): a narrow column on a computer is no phone.
export const PHONE_WIDTH = (window.top ?? window).matchMedia('(max-width: 767px)')
