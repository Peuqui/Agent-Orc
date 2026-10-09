import assert from 'node:assert/strict'
import { test } from 'node:test'
import { arrowOf, firstLine, groupConversations, isMachine, laneLabel, lanesOf, replyRecipients } from '../src/peerConversations.ts'

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

test('the first line is cut, and marked when more follows', () => {
  assert.equal(firstLine('  Kurz  ', 20), 'Kurz')
  assert.equal(firstLine('Erste Zeile\nZweite', 20), 'Erste Zeile…')
  assert.equal(firstLine('Eine sehr lange Zeile', 9), 'Eine sehr…')
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
