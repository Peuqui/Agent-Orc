import assert from 'node:assert/strict'
import { test } from 'node:test'
import {
  arrowOf,
  byDay,
  chatOf,
  clip,
  collapseRepeats,
  groupConversations,
  isMachine,
  laneLabel,
  lanesOf,
  replyRecipients,
} from '../src/peerConversations.ts'

const message = (id: number, from: string, to: string, timestamp: string) => ({
  id,
  from,
  to,
  content: `Nachricht ${id}`,
  context: null,
  timestamp,
})

test('both directions of a pair are one conversation, a broadcast is its own', () => {
  const conversations = groupConversations([
    message(1, 'Mini:B', 'Mini:A', '2026-10-09T20:00:00.000Z'),
    message(3, 'Mini:A', '*', '2026-10-09T20:02:00.000Z'),
    message(2, 'Mini:A', 'Mini:B', '2026-10-09T20:01:00.000Z'),
  ])
  // The latest activity first, the messages within oldest first.
  assert.deepEqual(
    conversations.map((c) => [c.members, c.messages.map((m) => m.id)]),
    [
      [['Mini:A', '*'], [3]],
      [['Mini:A', 'Mini:B'], [1, 2]],
    ],
  )
})

test('an answer goes to everyone in the conversation but the user', () => {
  const [withUser] = groupConversations([message(1, 'User:Ada', 'Mini:A', '2026-10-09T20:00:00.000Z')])
  assert.deepEqual(replyRecipients(withUser!), ['Mini:A'])
  const [broadcast] = groupConversations([message(2, 'Mini:A', '*', '2026-10-09T20:00:00.000Z')])
  assert.deepEqual(replyRecipients(broadcast!), ['*'])
  const [notice] = groupConversations([message(3, 'Bridge', 'Mini:A', '2026-10-09T20:00:00.000Z')])
  assert.deepEqual(replyRecipients(notice!), [])
})

test('a text is cut to its lines and characters, and marked when more follows', () => {
  assert.equal(clip('  Kurz  ', 20, 1), 'Kurz')
  assert.equal(clip('Erste Zeile\nZweite', 20, 1), 'Erste Zeile…')
  assert.equal(clip('Eine sehr lange Zeile', 9, 1), 'Eine sehr…')
  assert.equal(clip('Eins\nZwei\nDrei', 100, 2), 'Eins\nZwei…')
  assert.equal(clip('Eins\nZwei', 100, 2), 'Eins\nZwei')
})

test('a message repeated right after itself is one run with its count and time span', () => {
  const notice = (id: number, timestamp: string) => ({ ...message(id, 'Bridge', 'Mini:A', timestamp), content: 'Standby' })
  const runs = collapseRepeats([
    notice(1, '2026-10-09T20:00:00.000Z'),
    notice(2, '2026-10-09T20:05:00.000Z'),
    message(3, 'Mini:B', 'Mini:A', '2026-10-09T20:06:00.000Z'),
    notice(4, '2026-10-09T20:07:00.000Z'),
  ])
  assert.deepEqual(
    runs.map((run) => [run.message.id, run.count, run.first, run.last]),
    [
      [1, 2, '2026-10-09T20:00:00.000Z', '2026-10-09T20:05:00.000Z'],
      [3, 1, '2026-10-09T20:06:00.000Z', '2026-10-09T20:06:00.000Z'],
      [4, 1, '2026-10-09T20:07:00.000Z', '2026-10-09T20:07:00.000Z'],
    ],
  )
})

test('runs are split by the local day they were sent', () => {
  const days = byDay(
    collapseRepeats([
      message(1, 'Mini:A', 'Mini:B', new Date(2026, 9, 9, 23, 50).toISOString()),
      message(2, 'Mini:B', 'Mini:A', new Date(2026, 9, 10, 0, 10).toISOString()),
      message(3, 'Mini:A', 'Mini:B', new Date(2026, 9, 10, 8, 0).toISOString()),
    ]),
  )
  assert.deepEqual(
    days.map((day) => day.runs.map((run) => run.message.id)),
    [[1], [2, 3]],
  )
})

test('in a chat the user is on the right, of two agents the one who began on the left, a machine in the middle', () => {
  const [agents] = groupConversations([
    message(1, 'Mini:B', 'Mini:A', '2026-10-09T20:00:00.000Z'),
    message(2, 'Mini:A', 'Mini:B', '2026-10-09T20:01:00.000Z'),
    message(3, 'Mini:A', 'Mini:B', '2026-10-09T20:02:00.000Z'),
  ])
  const entries = chatOf(agents!).flatMap((day) => day.entries)
  assert.deepEqual(
    entries.map((entry) => [entry.side, entry.showName]),
    [
      ['left', true],
      ['right', true],
      ['right', false],
    ],
  )
  const [withUser] = groupConversations([
    message(4, 'Mini:A', 'User:Ada', '2026-10-09T20:00:00.000Z'),
    message(5, 'User:Ada', 'Mini:A', '2026-10-09T20:01:00.000Z'),
  ])
  assert.deepEqual(
    chatOf(withUser!).flatMap((day) => day.entries.map((entry) => entry.side)),
    ['left', 'right'],
  )
  const [notice] = groupConversations([message(6, 'Bridge', 'Mini:A', '2026-10-09T20:00:00.000Z')])
  assert.deepEqual(
    chatOf(notice!).flatMap((day) => day.entries.map((entry) => entry.side)),
    ['center'],
  )
})

test('every participant is a lane, in the order they first appear; a broadcast spans them all', () => {
  const messages = [
    message(2, 'Mini:A', '*', '2026-10-09T20:01:00.000Z'),
    message(1, 'User:Ada', 'Mini:A', '2026-10-09T20:00:00.000Z'),
    message(3, 'Mini:B', 'User:Ada', '2026-10-09T20:02:00.000Z'),
  ]
  const lanes = lanesOf(messages)
  assert.deepEqual(lanes, ['User:Ada', 'Mini:A', 'Mini:B'])
  assert.deepEqual(lanes.map(laneLabel), ['Ada', 'A', 'B'])
  assert.deepEqual(arrowOf(messages[2]!, lanes), { from: 2, to: 0 })
  assert.deepEqual(arrowOf(messages[0]!, lanes), { from: 1, to: null })
})

test('a name without a project is a machine, not an agent', () => {
  assert.equal(isMachine('Mini'), true)
  assert.equal(isMachine('Mini:AIfred'), false)
  assert.equal(isMachine('User:Ada'), false)
})
