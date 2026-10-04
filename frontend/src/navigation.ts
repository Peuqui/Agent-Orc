import type { IconName } from './icons'

/** Main sections, shared by the bottom bar (phones) and the header tabs (wide screens). */
export const NAV_ITEMS: { to: string; icon: IconName; label: string }[] = [
  { to: '/sessions', icon: 'agents', label: 'nav.sessions' },
  { to: '/workspace', icon: 'workspace', label: 'nav.workspace' },
  { to: '/files', icon: 'folder', label: 'nav.files' },
  { to: '/consumption', icon: 'chart', label: 'nav.consumption' },
  { to: '/trash', icon: 'trash', label: 'nav.trash' },
]
