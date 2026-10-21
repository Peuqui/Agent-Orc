import assert from 'node:assert/strict'
import { test } from 'node:test'

const store = new Map<string, string>()
Object.assign(globalThis, {
  sessionStorage: {
    getItem: (key: string) => store.get(key) ?? null,
    setItem: (key: string, value: string) => void store.set(key, value),
    removeItem: (key: string) => void store.delete(key),
  },
})
const { addToDraft, draftOf } = await import('../src/composables/useDrafts.ts')

test('text added from elsewhere shows in the field and is kept for a reload', () => {
  const field = draftOf('a')
  assert.equal(field.value, '')
  addToDraft('a', 'first')
  assert.equal(field.value, 'first')
  addToDraft('a', 'second')
  assert.equal(field.value, 'first\nsecond')
  assert.equal(store.get('agent-orc-draft:a'), 'first\nsecond')
})

test('an emptied field leaves nothing stored, and agents keep their own text', () => {
  const field = draftOf('b')
  field.value = 'kept'
  assert.equal(draftOf('a').value, 'first\nsecond')
  field.value = ''
  assert.equal(store.has('agent-orc-draft:b'), false)
})

test('a field opened later starts from what is stored', () => {
  store.set('agent-orc-draft:c', 'from before')
  assert.equal(draftOf('c').value, 'from before')
})
