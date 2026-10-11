import assert from 'node:assert/strict'
import { test } from 'node:test'

// The module reads the storages once it loads.
Object.assign(globalThis, { localStorage: { getItem: () => null, setItem: () => undefined } })
const { daysUntil, FREE_UNTIL_PREFIX, modelOptions } = await import('../src/composables/useModelChoice.ts')

test('the days left are counted by calendar days, whatever the time of day', () => {
  assert.equal(daysUntil('2026-11-24', new Date(2026, 9, 11, 23, 59)), 44)
  assert.equal(daysUntil('2026-11-24', new Date(2026, 10, 23, 0, 1)), 1)
  assert.equal(daysUntil('2026-11-24', new Date(2026, 10, 24, 12)), 0)
})

test('the choice shows the note as the caller words it, and none where there is none', () => {
  const models = [{ name: 'plain', note: '' }, { name: 'flash', note: `${FREE_UNTIL_PREFIX}2026-11-24` }, { name: 'other', note: 'free until Friday' }]
  const options = modelOptions(models, (note) => (note.startsWith(FREE_UNTIL_PREFIX) ? 'frei bis 24. Nov.' : note))
  assert.deepEqual(
    options.map((option) => option.label),
    ['plain', 'flash – frei bis 24. Nov.', 'other – free until Friday'],
  )
})
