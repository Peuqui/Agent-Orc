import assert from 'node:assert/strict'
import { test } from 'node:test'
import { shownTexts, unreadTexts } from '../src/answers.ts'

const text = (id: string, time: string) => ({ id, time, text: id })
const turn = (id: string, texts: ReturnType<typeof text>[]) => ({
  id,
  time: texts[0]?.time ?? '',
  prompt: id,
  images: 0,
  texts,
  interjections: [],
})

const turns = [
  turn('t1', [text('a', '2026-10-06T10:00:01Z'), text('b', '2026-10-06T10:00:05Z')]),
  turn('t2', [text('c', '2026-10-06T10:01:00Z')]),
  turn('t3', []),
]

test('only the last text of a request is shown, unless all are', () => {
  assert.deepEqual(shownTexts(turns[0], false).map((t) => t.id), ['b'])
  assert.deepEqual(shownTexts(turns[0], true).map((t) => t.id), ['a', 'b'])
  assert.deepEqual(shownTexts(turns[2], false), [])
})

test('what is new is what was written after the time seen, in order', () => {
  assert.deepEqual(unreadTexts(turns, false, '').map((t) => t.id), ['b', 'c'])
  assert.deepEqual(unreadTexts(turns, true, '2026-10-06T10:00:02Z').map((t) => t.id), ['b', 'c'])
  assert.deepEqual(unreadTexts(turns, false, '2026-10-06T10:01:00Z'), [])
})
