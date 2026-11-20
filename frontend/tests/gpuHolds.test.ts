import assert from 'node:assert/strict'
import { test } from 'node:test'
import { type GpuHold, holdView, isFolded, setFolded } from '../src/gpuHolds.ts'

const requested: GpuHold = {
  owner: 'vllm-research',
  reason: 'Messung',
  model: null,
  state: 'requested',
  granted_by: null,
  since: '2026-11-14T20:55:00+01:00',
}

class MemoryStorage {
  items = new Map<string, string>()
  getItem(key: string): string | null {
    return this.items.get(key) ?? null
  }
  setItem(key: string, value: string): void {
    this.items.set(key, value)
  }
  removeItem(key: string): void {
    this.items.delete(key)
  }
}

test('a requested hold nobody handed over can be handed the cards, with no reason against it', () => {
  assert.deepEqual(holdView(requested), {
    stateKey: 'gpuHold.state.requested',
    canGrant: true,
    blockedKey: null,
    shortKey: 'gpuHold.short.requested',
    pulses: true,
  })
})

test('a requested hold already handed over says so and the button is blocked with that reason', () => {
  assert.deepEqual(holdView({ ...requested, granted_by: 'Peuqui' }), {
    stateKey: 'gpuHold.state.granted',
    canGrant: false,
    blockedKey: 'gpuHold.blocked.granted',
    shortKey: 'gpuHold.short.granted',
    pulses: false,
  })
})

test('an active hold cannot be handed anything, the reason is told', () => {
  assert.deepEqual(holdView({ ...requested, state: 'active' }), {
    stateKey: 'gpuHold.state.active',
    canGrant: false,
    blockedKey: 'gpuHold.blocked.active',
    shortKey: 'gpuHold.short.active',
    pulses: false,
  })
  assert.equal(holdView({ ...requested, state: 'active', granted_by: 'Peuqui' }).canGrant, false)
})

test('a folded hold stays folded, and a new hold of the same owner shows in full again', () => {
  const storage = new MemoryStorage()
  assert.equal(isFolded('http://mini:5070', requested, storage), false)
  setFolded('http://mini:5070', requested, true, storage)
  assert.equal(isFolded('http://mini:5070', requested, storage), true)
  assert.equal(isFolded('http://aragon:5070', requested, storage), false)
  assert.equal(isFolded('http://mini:5070', { ...requested, since: '2026-11-15T08:00:00+01:00' }, storage), false)
  setFolded('http://mini:5070', requested, false, storage)
  assert.equal(isFolded('http://mini:5070', requested, storage), false)
})

test('a storage that throws is nothing folded and does not break folding', () => {
  const broken = {
    getItem: (): never => {
      throw new Error('blocked')
    },
    setItem: (): never => {
      throw new Error('blocked')
    },
    removeItem: (): never => {
      throw new Error('blocked')
    },
  }
  assert.equal(isFolded('x', requested, broken), false)
  setFolded('x', requested, true, broken)
  setFolded('x', requested, false, broken)
})

test('the folded chip pulses only while a decision is open, not when effective and not when handed over', () => {
  assert.equal(holdView(requested).pulses, true)
  assert.equal(holdView({ ...requested, state: 'active' }).pulses, false)
  assert.equal(holdView({ ...requested, state: 'active', granted_by: 'Peuqui' }).pulses, false)
  assert.equal(holdView({ ...requested, granted_by: 'Peuqui' }).pulses, false)
})
