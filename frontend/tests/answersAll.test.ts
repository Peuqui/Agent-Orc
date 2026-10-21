import assert from 'node:assert/strict'
import { test } from 'node:test'
import { keepAnswersAllOf, readAnswersAll, useAnswersAll } from '../src/composables/useAnswersAll.ts'

test('an agent shows every text until the choice is made, and only this page remembers it', () => {
  const choice = useAnswersAll('a')
  assert.equal(choice.value, true)
  assert.equal(readAnswersAll('a'), true)
  choice.value = false
  assert.equal(readAnswersAll('a'), false)
  assert.equal(readAnswersAll('b'), true)
})

test('an agent that is gone takes its choice with it, a new one in its folder starts anew', () => {
  useAnswersAll('c').value = false
  useAnswersAll('d').value = false
  keepAnswersAllOf(new Set(['d']))
  assert.equal(readAnswersAll('c'), true)
  assert.equal(readAnswersAll('d'), false)
})
