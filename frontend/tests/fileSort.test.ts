import assert from 'node:assert/strict'
import { test } from 'node:test'
import { DEFAULT_SORT, clicked, formatSort, parseSort, sortEntries } from '../src/fileSort.ts'

const entry = (name: string, extra: Partial<{ is_dir: boolean; size: number; modified: number }> = {}) => ({
  name,
  path: `/x/${name}`,
  is_dir: false,
  size: 0,
  modified: 0,
  ...extra,
})

const names = (entries: { name: string }[]) => entries.map((item) => item.name)

test('by name: folders first, numbers as numbers, umlauts with their letters', () => {
  const sorted = sortEntries(
    [entry('Datei 10'), entry('Zeta'), entry('Datei 2'), entry('Ärger'), entry('sub', { is_dir: true })],
    DEFAULT_SORT,
  )
  assert.deepEqual(names(sorted), ['sub', 'Ärger', 'Datei 2', 'Datei 10', 'Zeta'])
})

test('descending turns the files around but folders stay first', () => {
  const sorted = sortEntries(
    [entry('a'), entry('b'), entry('d1', { is_dir: true }), entry('d2', { is_dir: true })],
    { key: 'name', descending: true },
  )
  assert.deepEqual(names(sorted), ['d2', 'd1', 'b', 'a'])
})

test('by date and by size, a tie goes by name', () => {
  const files = [
    entry('old', { modified: 1, size: 500 }),
    entry('new', { modified: 9, size: 5 }),
    entry('same-a', { modified: 5, size: 70 }),
    entry('same-b', { modified: 5, size: 70 }),
  ]
  assert.deepEqual(names(sortEntries(files, { key: 'modified', descending: true })), ['new', 'same-a', 'same-b', 'old'])
  assert.deepEqual(names(sortEntries(files, { key: 'size', descending: false })), ['new', 'same-a', 'same-b', 'old'])
  assert.deepEqual(names(sortEntries(files, { key: 'size', descending: true })), ['old', 'same-a', 'same-b', 'new'])
})

test('folders stay by name when sorted by size', () => {
  const sorted = sortEntries(
    [entry('b', { is_dir: true, size: 4096 }), entry('a', { is_dir: true, size: 9999 }), entry('f', { size: 1 })],
    { key: 'size', descending: true },
  )
  assert.deepEqual(names(sorted), ['a', 'b', 'f'])
})

test('a click on a key: its first direction, again turns it around', () => {
  assert.deepEqual(clicked(DEFAULT_SORT, 'modified'), { key: 'modified', descending: true })
  assert.deepEqual(clicked({ key: 'modified', descending: true }, 'modified'), { key: 'modified', descending: false })
  assert.deepEqual(clicked({ key: 'size', descending: true }, 'name'), { key: 'name', descending: false })
})

test('the sort is kept as text and read back; anything else is the default', () => {
  assert.equal(formatSort({ key: 'size', descending: true }), 'size:desc')
  assert.deepEqual(parseSort('size:desc'), { key: 'size', descending: true })
  for (const unknown of [null, '', 'size', 'colour:asc', 'size:up']) assert.deepEqual(parseSort(unknown), DEFAULT_SORT)
})
