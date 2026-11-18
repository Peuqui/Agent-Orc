import assert from 'node:assert/strict'
import { test } from 'node:test'
import { offersWake } from '../src/wake.ts'

test('the wake button is for a machine that is not reachable and can be woken', () => {
  for (const state of ['service_off', 'ssh_down', 'off'] as const) {
    assert.equal(offersWake({ state, canWake: true }), true)
    assert.equal(offersWake({ state, canWake: false }), false)
  }
})

test('a reachable machine has none', () => {
  assert.equal(offersWake({ state: 'online', canWake: true }), false)
})
