import assert from 'node:assert/strict'
import { test } from 'node:test'
import { type GpuHold, holdView, isFolded, setFolded } from '../src/gpuHolds.ts'

const requested: GpuHold = {
  owner: 'vllm-research',
  reason: 'Messung',
  model: null,
  state: 'requested',
  granted_by: null,
  end_requested_by: null,
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
}

test('a requested hold nobody handed over can be handed the cards, with no reason against it', () => {
  assert.deepEqual(holdView(requested), {
    stateKey: 'gpuHold.state.requested',
    by: null,
    canGrant: true,
    blockedKey: null,
    shortKey: 'gpuHold.short.requested',
    decisionOpen: true,
    endAsked: false,
  })
})

test('a requested hold already handed over says so and the button is blocked with that reason', () => {
  assert.deepEqual(holdView({ ...requested, granted_by: 'Peuqui' }), {
    stateKey: 'gpuHold.state.granted',
    by: 'Peuqui',
    canGrant: false,
    blockedKey: 'gpuHold.blocked.granted',
    shortKey: 'gpuHold.short.granted',
    decisionOpen: false,
    endAsked: false,
  })
})

test('an active hold cannot be handed anything, the reason is told', () => {
  assert.deepEqual(holdView({ ...requested, state: 'active' }), {
    stateKey: 'gpuHold.state.active',
    by: null,
    canGrant: false,
    blockedKey: 'gpuHold.blocked.active',
    shortKey: 'gpuHold.short.active',
    decisionOpen: false,
    endAsked: false,
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
  }
  assert.equal(isFolded('x', requested, broken), false)
  assert.equal(isFolded('x', { ...requested, state: 'active' }, broken), true)
  setFolded('x', requested, true, broken)
  setFolded('x', requested, false, broken)
})

test('a hold with nothing to decide shows as the chip at once, and a tap opens it until "Later"', () => {
  const storage = new MemoryStorage()
  const active: GpuHold = { ...requested, state: 'active' }
  const granted: GpuHold = { ...requested, granted_by: 'Peuqui' }
  assert.equal(isFolded('http://mini:5070', active, storage), true)
  assert.equal(isFolded('http://mini:5070', granted, storage), true)
  setFolded('http://mini:5070', active, false, storage)
  assert.equal(isFolded('http://mini:5070', active, storage), false)
  setFolded('http://mini:5070', active, true, storage)
  assert.equal(isFolded('http://mini:5070', active, storage), true)
})

test('a requested hold folds by itself once it is effective, a folded one stays folded', () => {
  const storage = new MemoryStorage()
  assert.equal(isFolded('http://mini:5070', requested, storage), false)
  assert.equal(isFolded('http://mini:5070', { ...requested, state: 'active' }, storage), true)
  setFolded('http://mini:5070', requested, true, storage)
  assert.equal(isFolded('http://mini:5070', { ...requested, state: 'active' }, storage), true)
})

test('a decision is open only while requested and not handed over, not when effective and not when handed over', () => {
  assert.equal(holdView(requested).decisionOpen, true)
  assert.equal(holdView({ ...requested, state: 'active' }).decisionOpen, false)
  assert.equal(holdView({ ...requested, state: 'active', granted_by: 'Peuqui' }).decisionOpen, false)
  assert.equal(holdView({ ...requested, granted_by: 'Peuqui' }).decisionOpen, false)
})

test('an active hold whose end was asked for says who asked, shows as the chip, and only then can be released at once', () => {
  const ending = holdView({ ...requested, state: 'active', end_requested_by: 'AIfred: Telegram' })
  assert.deepEqual(ending, {
    stateKey: 'gpuHold.state.ending',
    by: 'AIfred: Telegram',
    canGrant: false,
    blockedKey: 'gpuHold.blocked.active',
    shortKey: 'gpuHold.short.ending',
    decisionOpen: false,
    endAsked: true,
  })
  assert.equal(holdView({ ...requested, state: 'active' }).endAsked, false)
  assert.equal(holdView(requested).endAsked, false)
  assert.equal(isFolded('http://mini:5070', { ...requested, state: 'active', end_requested_by: 'x' }, new MemoryStorage()), true)
})
