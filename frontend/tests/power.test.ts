import assert from 'node:assert/strict'
import { test } from 'node:test'
import { powerButtons } from '../src/power.ts'

const both = { suspend: true, poweroff: true }

test('a reachable other machine offers what it allows itself', () => {
  assert.deepEqual(powerButtons({ state: 'online', host: 'Aragon' }, both), ['suspend', 'poweroff'])
  assert.deepEqual(powerButtons({ state: 'online', host: 'Aragon' }, { suspend: true, poweroff: false }), ['suspend'])
  assert.deepEqual(powerButtons({ state: 'online', host: 'Aragon' }, { suspend: false, poweroff: true }), ['poweroff'])
  assert.deepEqual(powerButtons({ state: 'online', host: 'Aragon' }, { suspend: false, poweroff: false }), [])
})

test('a machine that does not answer has none, whatever it once allowed', () => {
  for (const state of ['service_off', 'ssh_down', 'off'] as const) {
    assert.deepEqual(powerButtons({ state, host: 'Aragon' }, both), [])
  }
})

test('a machine whose permission is not known has none', () => {
  assert.deepEqual(powerButtons({ state: 'online', host: 'Aragon' }, undefined), [])
})

test('this machine own card never has them', () => {
  assert.deepEqual(powerButtons({ state: 'online', host: null }, both), [])
})
