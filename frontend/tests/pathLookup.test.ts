import assert from 'node:assert/strict'
import { test } from 'node:test'
import type { ExistingPath } from '../src/api.ts'
import { createPathLookup } from '../src/pathLookup.ts'

function server(existing: Record<string, ExistingPath>) {
  const asked: string[][] = []
  const ask = async (_base: string, candidates: string[]): Promise<Record<string, ExistingPath>> => {
    asked.push(candidates)
    return Object.fromEntries(candidates.filter((candidate) => candidate in existing).map((candidate) => [candidate, existing[candidate]!]))
  }
  return { asked, ask }
}

const README: ExistingPath = { path: '/p/README.md', kind: 'file' }

test('only the paths that exist come back', async () => {
  const { ask } = server({ 'README.md': README })
  const lookUp = createPathLookup(ask)
  assert.deepEqual(await lookUp('/p', ['README.md', 'nothing.md']), { 'README.md': README })
})

test('a path is asked about once, by whichever view asks', async () => {
  const { asked, ask } = server({ 'README.md': README })
  const lookUp = createPathLookup(ask)
  await lookUp('/p', ['README.md', 'nothing.md'])
  assert.deepEqual(await lookUp('/p', ['README.md']), { 'README.md': README })
  assert.deepEqual(await lookUp('/p', ['nothing.md']), {})
  assert.deepEqual(asked, [['README.md', 'nothing.md']])
})

test('only what is new is asked, and the same path in another folder is another path', async () => {
  const { asked, ask } = server({ 'README.md': README })
  const lookUp = createPathLookup(ask)
  await lookUp('/p', ['README.md'])
  await lookUp('/p', ['README.md', 'docs/x.md'])
  await lookUp('/q', ['README.md'])
  assert.deepEqual(asked, [['README.md'], ['docs/x.md'], ['README.md']])
})

test('two views asking at the same moment cause one request', async () => {
  const { asked, ask } = server({ 'README.md': README })
  const lookUp = createPathLookup(ask)
  const [first, second] = await Promise.all([lookUp('/p', ['README.md']), lookUp('/p', ['README.md'])])
  assert.deepEqual(first, second)
  assert.equal(asked.length, 1)
})

test('a path that is missing is asked for again soon, one that exists much later', async () => {
  const { asked, ask } = server({ 'README.md': README })
  let time = 0
  const lookUp = createPathLookup(ask, () => time, { found: 10_000, missing: 1000 })
  await lookUp('/p', ['README.md', 'new.md'])
  time = 999
  await lookUp('/p', ['README.md', 'new.md'])
  assert.equal(asked.length, 1)
  // The missing one expired (a file may exist by now); the one that exists is still kept.
  time = 1001
  await lookUp('/p', ['README.md', 'new.md'])
  assert.deepEqual(asked, [['README.md', 'new.md'], ['new.md']])
  // The one that exists is asked for again once its longer time is over.
  time = 10_001
  await lookUp('/p', ['README.md'])
  assert.deepEqual(asked.at(-1), ['README.md'])
})
