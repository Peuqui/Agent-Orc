import assert from 'node:assert/strict'
import { test } from 'node:test'
import { nearestLevel } from '../src/effort.ts'

const ORDER = ['low', 'medium', 'high', 'xhigh', 'max']

test('a level the agent takes stays', () => {
  assert.equal(nearestLevel('high', ['low', 'high', 'max'], ORDER), 'high')
})

test('a level it does not take becomes the next higher one it takes', () => {
  assert.equal(nearestLevel('high', ['low', 'medium', 'xhigh'], ORDER), 'xhigh')
  assert.equal(nearestLevel('medium', ['low', 'high'], ORDER), 'high')
})

test('above all of them it becomes the highest it takes', () => {
  assert.equal(nearestLevel('max', ['low', 'medium', 'xhigh'], ORDER), 'xhigh')
})

test('an agent without levels has none, and no wish gets the first it takes', () => {
  assert.equal(nearestLevel('max', [], ORDER), null)
  assert.equal(nearestLevel(null, ['low', 'high'], ORDER), 'low')
})
