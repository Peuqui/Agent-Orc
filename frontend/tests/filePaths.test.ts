import assert from 'node:assert/strict'
import { test } from 'node:test'
import { pathOfCode, pathsIn } from '../src/filePaths.ts'

test('a path in a line is found, with its line number, without the full stop of the sentence', () => {
  const found = pathsIn('Edit docs/TODO.md and see src/app.py:42.')
  assert.deepEqual(
    found.map(({ text, line }) => [text, line]),
    [
      ['docs/TODO.md', null],
      ['src/app.py', 42],
    ],
  )
})

test('plain words and addresses are no paths', () => {
  assert.deepEqual(pathsIn('this is simply a sentence about https://example.com/a/b'), [])
})

test('code that is a path as a whole is one, other code is not', () => {
  assert.deepEqual(pathOfCode(' docs/TODO.md '), { text: 'docs/TODO.md', line: null, start: 0 })
  assert.deepEqual(pathOfCode('~/.config/agent-orc/config.yaml'), {
    text: '~/.config/agent-orc/config.yaml',
    line: null,
    start: 0,
  })
  assert.equal(pathOfCode('.github/workflows/ci.yml')?.text, '.github/workflows/ci.yml')
  assert.equal(pathOfCode('src/app.py:42')?.line, 42)
  assert.equal(pathOfCode('npm run build'), null)
  assert.equal(pathOfCode('word'), null)
  assert.equal(pathOfCode('systemctl restart user@1000'), null)
})
