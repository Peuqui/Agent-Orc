import assert from 'node:assert/strict'
import { test } from 'node:test'
import { suggestionText } from '../src/permissionSuggestions.ts'

test('rules read as Claude Code writes them', () => {
  const suggestion = {
    type: 'addRules',
    rules: [{ toolName: 'Bash', ruleContent: 'git push:*' }, { toolName: 'WebSearch' }],
    behavior: 'allow',
    destination: 'localSettings' as const,
  }
  assert.deepEqual(suggestionText(suggestion), { kind: 'rules', text: 'Bash(git push:*), WebSearch' })
})

test('a mode and folders are offered too', () => {
  assert.deepEqual(suggestionText({ type: 'setMode', mode: 'acceptEdits', destination: 'session' }), {
    kind: 'mode',
    mode: 'acceptEdits',
  })
  assert.deepEqual(suggestionText({ type: 'addDirectories', directories: ['/srv/a', '/srv/b'], destination: 'session' }), {
    kind: 'directories',
    text: '/srv/a, /srv/b',
  })
})

test('what would not allow more is not offered', () => {
  const deny = { type: 'addRules', rules: [{ toolName: 'Bash' }], behavior: 'deny', destination: 'session' as const }
  assert.equal(suggestionText(deny), null)
  assert.equal(suggestionText({ type: 'removeRules', rules: [{ toolName: 'Bash' }], behavior: 'allow', destination: 'session' }), null)
})
