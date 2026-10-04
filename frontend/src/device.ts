// A finger rather than a mouse is the main pointer (phones, tablets without a mouse): there,
// giving an input field the focus by itself would open the on-screen keyboard.
export const TOUCH_FIRST = window.matchMedia('(pointer: coarse)')

// Phone-sized screens (below Tailwind's md): the workspace shows one column at a time there.
export const PHONE_WIDTH = window.matchMedia('(max-width: 767px)')
