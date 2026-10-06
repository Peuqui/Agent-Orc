import assert from 'node:assert/strict'
import { test } from 'node:test'

const items = new Map<string, string>()
Object.assign(globalThis, {
  localStorage: {
    getItem: (key: string) => items.get(key) ?? null,
    setItem: (key: string, value: string) => void items.set(key, value),
  },
})
const { preferredModel, rememberModel } = await import('../src/composables/useModelChoice.ts')

test('the first model is offered until another one was chosen', () => {
  assert.equal(preferredModel('claude', ['Opus', 'Sonnet']), 'Opus')
  rememberModel('claude', 'Sonnet')
  assert.equal(preferredModel('claude', ['Opus', 'Sonnet']), 'Sonnet')
})

test('a remembered model that is no longer offered is ignored', () => {
  rememberModel('lclaude', 'gone')
  assert.equal(preferredModel('lclaude', ['qwen']), 'qwen')
  assert.equal(preferredModel('lclaude', []), null)
})
