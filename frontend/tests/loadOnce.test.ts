import assert from 'node:assert/strict'
import { test } from 'node:test'
import { loadOnce } from '../src/loadOnce.ts'

test('a load that went through is not repeated, one in progress is shared', async () => {
  let calls = 0
  const load = loadOnce(async () => {
    calls++
  })
  await Promise.all([load(), load()])
  await load()
  assert.equal(calls, 1)
})

test('a failed load is tried again by the next call', async () => {
  let calls = 0
  const load = loadOnce(async () => {
    calls++
    if (calls === 1) throw new Error('network gap')
  })
  await assert.rejects(load(), /network gap/)
  await load()
  await load()
  assert.equal(calls, 2)
})
