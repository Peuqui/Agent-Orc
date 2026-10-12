import assert from 'node:assert/strict'
import { test } from 'node:test'
import { FOLLOW_WITHIN_PX, isFollowing, moveFor } from '../src/feedScroll.ts'

const following = { following: true, hasUnread: true, hasRemembered: true }
const reading = { ...following, following: false }

test('opening the feed goes to the oldest unread answer, else to where the reader was, else to the end', () => {
  assert.equal(moveFor('opened', following), 'oldestUnread')
  assert.equal(moveFor('opened', { ...following, hasUnread: false }), 'remembered')
  assert.equal(moveFor('opened', { ...following, hasUnread: false, hasRemembered: false }), 'end')
  assert.equal(moveFor('opened', reading), 'oldestUnread') // the state of an earlier visit does not count
})

test('a following reader is brought to what the reader sent and to what the agent wrote', () => {
  assert.equal(moveFor('own', following), 'end')
  assert.equal(moveFor('answer', following), 'oldestUnread')
  assert.equal(moveFor('answer', { ...following, hasUnread: false }), 'end')
})

test('a reader who scrolled up is left where they are', () => {
  assert.equal(moveFor('own', reading), 'stay')
  assert.equal(moveFor('answer', reading), 'stay')
})

test('the reader follows within the distance of the end and no further from it', () => {
  assert.equal(isFollowing(0), true)
  assert.equal(isFollowing(FOLLOW_WITHIN_PX), true)
  assert.equal(isFollowing(FOLLOW_WITHIN_PX + 1), false)
})
