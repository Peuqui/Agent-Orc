import type { TerminalKey } from './api'

// What a terminal expects for a key (xterm's sequences): the keys offered for the extra-keys
// bar, and the sequence of a key combination pressed while recording one.

const ESC = '\x1b'

function key(label: string, send: string): TerminalKey {
  return { label, send, modifier: null, submit: false }
}

function modifierKey(label: string, modifier: 'ctrl' | 'alt'): TerminalKey {
  return { label, send: null, modifier, submit: false }
}

// F1–F4 have their own short form; the rest are numbered with gaps (xterm).
const FUNCTION_KEYS = [
  `${ESC}OP`,
  `${ESC}OQ`,
  `${ESC}OR`,
  `${ESC}OS`,
  `${ESC}[15~`,
  `${ESC}[17~`,
  `${ESC}[18~`,
  `${ESC}[19~`,
  `${ESC}[20~`,
  `${ESC}[21~`,
  `${ESC}[23~`,
  `${ESC}[24~`,
]

/** Ready-made keys to add, grouped as shown in the editor. */
export const KEY_CATALOG: { group: string; keys: TerminalKey[] }[] = [
  {
    group: 'keyCatalog.basic',
    keys: [
      key('Esc', ESC),
      key('Tab', '\t'),
      key('⇧Tab', `${ESC}[Z`),
      key('⏎', '\r'),
      key('⌫', '\x7f'),
      modifierKey('Ctrl', 'ctrl'),
      modifierKey('Alt', 'alt'),
    ],
  },
  {
    group: 'keyCatalog.moving',
    keys: [
      key('↑', `${ESC}[A`),
      key('↓', `${ESC}[B`),
      key('←', `${ESC}[D`),
      key('→', `${ESC}[C`),
      key('Home', `${ESC}[H`),
      key('End', `${ESC}[F`),
      key('PgUp', `${ESC}[5~`),
      key('PgDn', `${ESC}[6~`),
    ],
  },
  {
    group: 'keyCatalog.control',
    keys: [
      key('^C', '\x03'),
      key('^D', '\x04'),
      key('^L', '\x0c'),
      key('^R', '\x12'),
      key('^Z', '\x1a'),
    ],
  },
  {
    group: 'keyCatalog.characters',
    keys: ['/', '|', '~', '-', '_', '`', '\\', '@', '#', '$'].map((character) => key(character, character)),
  },
  {
    group: 'keyCatalog.function',
    keys: Array.from({ length: 12 }, (_, index) => key(`F${index + 1}`, FUNCTION_KEYS[index])),
  },
]


// Keys whose sequence takes a modifier parameter (ESC [1;<m> X), with their final character.
const CURSOR_KEYS: Record<string, [string, string]> = {
  ArrowUp: ['↑', 'A'],
  ArrowDown: ['↓', 'B'],
  ArrowRight: ['→', 'C'],
  ArrowLeft: ['←', 'D'],
  Home: ['Home', 'H'],
  End: ['End', 'F'],
}
const PLAIN_KEYS: Record<string, [string, string]> = {
  Escape: ['Esc', ESC],
  Enter: ['⏎', '\r'],
  Backspace: ['⌫', '\x7f'],
  Delete: ['Del', `${ESC}[3~`],
  Insert: ['Ins', `${ESC}[2~`],
  PageUp: ['PgUp', `${ESC}[5~`],
  PageDown: ['PgDn', `${ESC}[6~`],
}

/** The key a pressed combination stands for in a terminal; null for a lone modifier. */
export function keyFromEvent(event: KeyboardEvent): TerminalKey | null {
  if (['Control', 'Alt', 'Shift', 'Meta', 'AltGraph'].includes(event.key)) return null
  const names = [event.ctrlKey && 'Ctrl', event.altKey && 'Alt', event.shiftKey && '⇧'].filter(Boolean)
  const prefix = names.length ? `${names.join('+')}+` : ''
  // xterm's modifier parameter: 1 + Shift(1) + Alt(2) + Ctrl(4).
  const parameter = 1 + (event.shiftKey ? 1 : 0) + (event.altKey ? 2 : 0) + (event.ctrlKey ? 4 : 0)

  const cursor = CURSOR_KEYS[event.key]
  if (cursor) {
    const [label, final] = cursor
    return key(`${prefix}${label}`, parameter === 1 ? `${ESC}[${final}` : `${ESC}[1;${parameter}${final}`)
  }
  if (event.key === 'Tab') return event.shiftKey ? key('⇧Tab', `${ESC}[Z`) : key('Tab', '\t')
  const functionKey = /^F([1-9]|1[0-2])$/.exec(event.key)
  if (functionKey) return key(`${prefix}${event.key}`, FUNCTION_KEYS[Number(functionKey[1]) - 1])
  const plain = PLAIN_KEYS[event.key]
  if (plain) return key(`${prefix}${plain[0]}`, (event.altKey ? ESC : '') + plain[1])
  if (event.key.length !== 1) return null

  // Ctrl with a letter (or @ [ \ ] ^ _) is the control character; Alt puts ESC before the key.
  let send = event.key
  if (event.ctrlKey) {
    const code = event.key.toUpperCase().charCodeAt(0)
    if (code < 64 || code > 95) return null
    send = String.fromCharCode(code - 64)
  }
  if (event.altKey) send = ESC + send
  const label = event.ctrlKey && !event.altKey ? `^${event.key.toUpperCase()}` : `${prefix}${event.key}`
  return key(label, send)
}
