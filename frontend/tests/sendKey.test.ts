import assert from 'node:assert/strict'
import { test } from 'node:test'
import { isSendKey } from '../src/sendKey.ts'

const key = (key: string, shiftKey = false, isComposing = false) => ({ key, shiftKey, isComposing }) as KeyboardEvent

test('Enter sends; Shift+Enter, a word being composed and other keys do not', () => {
  assert.equal(isSendKey(key('Enter')), true)
  assert.equal(isSendKey(key('Enter', true)), false)
  assert.equal(isSendKey(key('Enter', false, true)), false)
  assert.equal(isSendKey(key('a')), false)
})
