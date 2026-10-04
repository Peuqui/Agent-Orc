// Simple stroke icons on a 24×24 grid, drawn for Agent-Orc.
export const ICONS = {
  agents: 'M4 5h16v14H4z M7 9l3 3-3 3 M12 15h5',
  folder: 'M3 6h6l2 2h10v11H3z',
  file: 'M6 3h8l4 4v14H6z M14 3v4h4',
  trash: 'M4 7h16 M9 7V4h6v3 M6 7l1 13h10l1-13',
  play: 'M8 5l11 7-11 7z',
  stop: 'M7 7h10v10H7z',
  resume: 'M4 12a8 8 0 1 0 2.4-5.7 M4 4v4h4',
  more: 'M12 5h.01 M12 12h.01 M12 19h.01',
  lock: 'M6 11h12v9H6z M9 11V8a3 3 0 0 1 6 0v3',
  unlock: 'M6 11h12v9H6z M9 11V8a3 3 0 0 1 5.8-1',
  up: 'M12 19V5 M5 12l7-7 7 7',
  plus: 'M12 5v14 M5 12h14',
  logout: 'M14 4h5v16h-5 M10 8l-4 4 4 4 M6 12h10',
  pencil: 'M4 20h4L19 9l-4-4L4 16z M13 7l4 4',
  search: 'M10.5 17a6.5 6.5 0 1 0 0-13 6.5 6.5 0 0 0 0 13z M15.5 15.5L20 20',
  copy: 'M8 8h11v12H8z M5 16V4h11',
  workspace: 'M3 5h18v14H3z M9 5v14 M15 5v14',
  send: 'M4 12l16-8-6 16-3-7z M11 13l9-9',
  mic: 'M12 3a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V6a3 3 0 0 0-3-3z M5 11a7 7 0 0 0 14 0 M12 18v3',
} as const

export type IconName = keyof typeof ICONS
