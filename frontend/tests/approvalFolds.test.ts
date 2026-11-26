import assert from 'node:assert/strict'
import { test } from 'node:test'
import { agentFolded } from '../src/approvalFolds.ts'

test('an agent shows as a pill only when every waiting request was folded', () => {
  assert.equal(agentFolded(['a'], new Set(['a'])), true)
  assert.equal(agentFolded(['a', 'b'], new Set(['a', 'b', 'old'])), true)
})

test('a new request of a folded agent opens its card again', () => {
  assert.equal(agentFolded(['a', 'b'], new Set(['a'])), false)
})

test('an agent without requests is no pill', () => {
  assert.equal(agentFolded([], new Set(['a'])), false)
})
