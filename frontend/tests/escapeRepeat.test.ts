import assert from 'node:assert/strict'
import { test } from 'node:test'
import { ESCAPE_REPEAT_GUARD_MILLISECONDS, isRepeatedEscape } from '../src/escapeRepeat.ts'

test('the first Esc always goes to the agent', () => {
  assert.equal(isRepeatedEscape(null, 0), false)
})

test('an Esc right after the last one is left out', () => {
  assert.equal(isRepeatedEscape(1000, 1150), true)
  assert.equal(isRepeatedEscape(1000, 1000 + ESCAPE_REPEAT_GUARD_MILLISECONDS - 1), true)
})

test('an Esc a second or more after the last one goes through', () => {
  assert.equal(isRepeatedEscape(1000, 1000 + ESCAPE_REPEAT_GUARD_MILLISECONDS), false)
  assert.equal(isRepeatedEscape(1000, 5000), false)
})
