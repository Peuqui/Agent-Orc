import assert from 'node:assert/strict'
import { test } from 'node:test'
import { moveInList } from '../src/composables/useReorder.ts'
import { baseName, formatSize, joinPath, parentPath } from '../src/format.ts'

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
