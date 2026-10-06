import assert from 'node:assert/strict'
import { test } from 'node:test'
import { shownTexts, unreadTexts, uploadMentions } from '../src/answers.ts'

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

test('what the user typed during an answer gets a summary of its own', () => {
  const interjection = (time: string, pending = false) => ({ id: time, time, text: 'x', images: 0, pending })
  const request = {
    ...turn('t', [
      text('a1', '2026-10-06T10:00:01Z'),
      text('a2', '2026-10-06T10:00:02Z'),
      text('b1', '2026-10-06T10:00:11Z'),
      text('b2', '2026-10-06T10:00:12Z'),
      text('c1', '2026-10-06T10:00:21Z'),
    ]),
    interjections: [interjection('2026-10-06T10:00:10Z'), interjection('2026-10-06T10:00:20Z')],
  }
  assert.deepEqual(shownTexts(request, false).map((t) => t.id), ['a2', 'b2', 'c1'])
  assert.deepEqual(shownTexts(request, true).map((t) => t.id), ['a1', 'a2', 'b1', 'b2', 'c1'])
  // A message not delivered yet does not end a stretch.
  const waiting = { ...request, interjections: [interjection('2026-10-06T10:00:10Z', true)] }
  assert.deepEqual(shownTexts(waiting, false).map((t) => t.id), ['c1'])
})

test('pictures attached in Agent-Orc are told apart from the message text', () => {
  const shown = uploadMentions('Schau @.agent-orc/uploads/20261006-200131-image.png und\n@.agent-orc/uploads/b.JPG an')
  assert.deepEqual(shown.files, ['20261006-200131-image.png', 'b.JPG'])
  assert.equal(shown.text, 'Schau und\nan')
  assert.deepEqual(uploadMentions('@.agent-orc/uploads/x.png'), { text: '', files: ['x.png'] })
  // Other files and other folders stay what they are: text.
  assert.deepEqual(uploadMentions('@.agent-orc/uploads/plan.pdf und @docs/x.png'), {
    text: '@.agent-orc/uploads/plan.pdf und @docs/x.png',
    files: [],
  })
})
