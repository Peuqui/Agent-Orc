import assert from 'node:assert/strict'
import { test } from 'node:test'
import { MAX_CHUNK_CHARS, speakableText, speechChunks } from '../src/speechText.ts'

test('markup is dropped and links keep their text', () => {
  const text = '## Ergebnis\n- **Fett** und `code`\n[Heise](https://heise.de) lesen https://x.org/a'
  assert.equal(speakableText(text, 'Code'), 'Ergebnis.\nFett und code.\nHeise lesen.')
})

test('code blocks and tables are replaced by a short note, once each', () => {
  const text = 'Vorher\n```bash\nls -la\nrm x\n```\nNachher\n| a | b |\n|---|---|\n| 1 | 2 |\nEnde'
  assert.equal(speakableText(text, 'Codeblock'), 'Vorher.\nCodeblock.\nNachher.\nCodeblock.\nEnde.')
})

test('a line keeps its own sentence end', () => {
  assert.equal(speakableText('Fertig!\nWirklich?', 'x'), 'Fertig!\nWirklich?')
})

test('chunks end at sentences and stay within the limit', () => {
  const sentence = 'Das ist ein Satz mit etwas Länge.'
  const text = Array.from({ length: 20 }, () => sentence).join(' ')
  const chunks = speechChunks(text)
  assert.ok(chunks.length > 1)
  assert.ok(chunks.every((chunk) => chunk.length <= MAX_CHUNK_CHARS && chunk.endsWith('.')))
  assert.equal(chunks.join(' '), text)
})

test('a sentence longer than the limit is cut at spaces', () => {
  const long = Array.from({ length: 80 }, (_, index) => `wort${index}`).join(' ')
  const chunks = speechChunks(long, 50)
  assert.ok(chunks.every((chunk) => chunk.length <= 50))
  assert.equal(chunks.join(' '), long)
})

test('every line is read on its own', () => {
  assert.deepEqual(speechChunks('Eins.\nZwei.'), ['Eins.', 'Zwei.'])
})
