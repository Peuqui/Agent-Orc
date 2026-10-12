import assert from 'node:assert/strict'
import { test } from 'node:test'
import { ReplayCache } from '../src/replayCache.ts'

test('what was set is found again', () => {
  const cache = new ReplayCache<string>(2)
  cache.set('a', 'x')
  assert.equal(cache.get('a'), 'x')
  assert.equal(cache.get('b'), undefined)
})

test('beyond the limit the entry used longest ago goes', () => {
  const cache = new ReplayCache<string>(2)
  cache.set('a', '1')
  cache.set('b', '2')
  cache.get('a') // a is in use again, so b is the oldest
  cache.set('c', '3')
  assert.deepEqual([cache.get('a'), cache.get('b'), cache.get('c')], ['1', undefined, '3'])
})

test('setting a key again replaces it without growing the cache', () => {
  const cache = new ReplayCache<string>(2)
  cache.set('a', '1')
  cache.set('b', '2')
  cache.set('a', '3')
  assert.deepEqual([cache.get('a'), cache.get('b')], ['3', '2'])
})

test('clear empties it', () => {
  const cache = new ReplayCache<string>(2)
  cache.set('a', '1')
  cache.clear()
  assert.equal(cache.get('a'), undefined)
})
