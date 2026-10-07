import assert from 'node:assert/strict'
import { test } from 'node:test'
import { moveInList } from '../src/composables/useReorder.ts'
import { baseName, formatSize, formatTokens, joinPath, parentPath } from '../src/format.ts'

test('paths are split and joined like the file view expects', () => {
  assert.equal(baseName('/home/mp/Projekte/'), 'Projekte')
  assert.equal(baseName('/'), '/')
  assert.equal(parentPath('/home/mp/notes.md'), '/home/mp')
  assert.equal(joinPath('/home/mp', '../other/./pic.png'), '/home/other/pic.png')
  assert.equal(joinPath('/home/mp', '/abs/file'), '/abs/file')
})

test('sizes use the largest fitting unit', () => {
  assert.equal(formatSize(512), '512 B')
  assert.equal(formatSize(1536), '1.5 KB')
})

test('a dragged item takes the place of its target and the others move up', () => {
  const list = ['a', 'b', 'c', 'd']
  moveInList(list, 'd', 'b')
  assert.deepEqual(list, ['a', 'd', 'b', 'c'])
  moveInList(list, 'a', 'c')
  assert.deepEqual(list, ['d', 'b', 'c', 'a'])
})

const EN_UNITS = ['k', 'M', 'B', 'T', 'Q']
// German: its billion is a million millions, its milliarde a thousand millions.
const DE_UNITS = [' Tsd.', ' Mio.', ' Mrd.', ' Bio.', ' Brd.']

test('token counts are short, with the units of the language', () => {
  assert.equal(formatTokens(950, EN_UNITS, 'en'), '950')
  assert.equal(formatTokens(675_000, EN_UNITS, 'en'), '675k')
  assert.equal(formatTokens(1_200_000, EN_UNITS, 'en'), '1.2M')
  assert.equal(formatTokens(2_500_000_000, EN_UNITS, 'en'), '2.5B')
  assert.equal(formatTokens(3_000_000_000_000, EN_UNITS, 'en'), '3T')
  assert.equal(formatTokens(4_500_000_000_000_000, EN_UNITS, 'en'), '4.5Q')

  assert.equal(formatTokens(950, DE_UNITS, 'de'), '950')
  assert.equal(formatTokens(675_000, DE_UNITS, 'de'), '675 Tsd.')
  assert.equal(formatTokens(1_200_000, DE_UNITS, 'de'), '1,2 Mio.')
  assert.equal(formatTokens(2_500_000_000, DE_UNITS, 'de'), '2,5 Mrd.')
  assert.equal(formatTokens(3_000_000_000_000, DE_UNITS, 'de'), '3 Bio.')
  assert.equal(formatTokens(4_500_000_000_000_000, DE_UNITS, 'de'), '4,5 Brd.')
})

test('a count that rounds up to the next unit is written in it', () => {
  assert.equal(formatTokens(999_999, EN_UNITS, 'en'), '1M')
  assert.equal(formatTokens(999_999, DE_UNITS, 'de'), '1 Mio.')
})
