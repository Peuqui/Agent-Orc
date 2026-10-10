import type { FileEntry } from './api'

export const SORT_KEYS = ['name', 'modified', 'size'] as const
export type SortKey = (typeof SORT_KEYS)[number]

export interface FileSort {
  key: SortKey
  descending: boolean
}

// What a first click on a key means: names from A, but the newest and the largest first.
const FIRST_DIRECTION_DESCENDING: Record<SortKey, boolean> = { name: false, modified: true, size: true }

export const DEFAULT_SORT: FileSort = { key: 'name', descending: false }

/** The sort after a click on `key`: the same key again turns it around. */
export function clicked(sort: FileSort, key: SortKey): FileSort {
  if (sort.key === key) return { key, descending: !sort.descending }
  return { key, descending: FIRST_DIRECTION_DESCENDING[key] }
}

// "name:asc", as it is kept in the browser.
export function formatSort(sort: FileSort): string {
  return `${sort.key}:${sort.descending ? 'desc' : 'asc'}`
}

export function parseSort(text: string | null): FileSort {
  const [key, direction] = (text ?? '').split(':')
  const known = SORT_KEYS.find((candidate) => candidate === key)
  return known === undefined || (direction !== 'asc' && direction !== 'desc')
    ? DEFAULT_SORT
    : { key: known, descending: direction === 'desc' }
}

// "Datei 2" before "Datei 10", "ä" with "a".
const byName = (a: FileEntry, b: FileEntry): number =>
  a.name.localeCompare(b.name, undefined, { numeric: true, sensitivity: 'base' })

/** The entries ordered, folders always first. A folder's size says nothing, so by size they
 * stay by name. */
export function sortEntries(entries: FileEntry[], sort: FileSort): FileEntry[] {
  const sign = sort.descending ? -1 : 1
  return [...entries].sort((a, b) => {
    if (a.is_dir !== b.is_dir) return a.is_dir ? -1 : 1
    if (sort.key === 'modified') return (a.modified - b.modified) * sign || byName(a, b)
    if (sort.key === 'size') return a.is_dir ? byName(a, b) : (a.size - b.size) * sign || byName(a, b)
    return byName(a, b) * sign
  })
}
