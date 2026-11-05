import type { IconName } from './icons'

/** Main sections, shared by the bottom bar (phones) and the header tabs (wide screens). */
export const NAV_ITEMS: { to: string; icon: IconName; label: string }[] = [
  { to: '/sessions', icon: 'agents', label: 'nav.sessions' },
  { to: '/workspace', icon: 'workspace', label: 'nav.workspace' },
  { to: '/notes', icon: 'notes', label: 'nav.notes' },
  { to: '/files', icon: 'folder', label: 'nav.files' },
  { to: '/peers', icon: 'peers', label: 'nav.peers' },
  { to: '/consumption', icon: 'chart', label: 'nav.consumption' },
]

/** The sections that belong to the user, not to a machine: this machine's own app shows them, also
 * from another machine's page (the agents of all machines, notes, conversations, consumption). */
export const USER_SECTIONS = ['/sessions', '/notes', '/peers', '/consumption']
