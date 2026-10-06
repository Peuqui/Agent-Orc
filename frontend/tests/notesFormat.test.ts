import assert from 'node:assert/strict'
import { test } from 'node:test'
import { applyFormat, fileLink, insertBlock, LINK_ADDRESS, pdfLinks, type Placeholders } from '../src/notesFormat.ts'

const placeholders: Placeholders = { bold: 'fett', italic: 'kursiv', code: 'code', link: 'Link' }
const selected = (text: string, edit: { from: number; to: number }) => text.slice(edit.from, edit.to)

test('bold wraps the selection and keeps it selected', () => {
  const edit = applyFormat('bold', 'ein Wort hier', 4, 8, placeholders)
  assert.equal(edit.text, 'ein **Wort** hier')
  assert.equal(selected(edit.text, edit), 'Wort')
})

test('without a selection a placeholder is put in and selected', () => {
  const edit = applyFormat('italic', 'ab', 1, 1, placeholders)
  assert.equal(edit.text, 'a*kursiv*b')
  assert.equal(selected(edit.text, edit), 'kursiv')
})

test('heading and list prefix every line the selection touches', () => {
  const text = 'eins\nzwei\ndrei'
  const heading = applyFormat('heading', text, 2, 6, placeholders)
  assert.equal(heading.text, '## eins\n## zwei\ndrei')
  const list = applyFormat('list', text, 11, 11, placeholders)
  assert.equal(list.text, 'eins\nzwei\n- drei')
})

test('a prefix goes at the start of the first line even when the selection starts inside it', () => {
  const edit = applyFormat('list', 'erste\nzweite', 8, 8, placeholders)
  assert.equal(edit.text, 'erste\n- zweite')
})

test('code is inline for one line and a fenced block for several', () => {
  assert.equal(applyFormat('code', 'ls -la', 0, 6, placeholders).text, '`ls -la`')
  const block = applyFormat('code', 'ls\npwd', 0, 6, placeholders)
  assert.equal(block.text, '```\nls\npwd\n```')
  assert.equal(selected(block.text, block), 'ls\npwd')
})

test('a link takes the selection as its text and selects the address to type over', () => {
  const edit = applyFormat('link', 'siehe Heise', 6, 11, placeholders)
  assert.equal(edit.text, `siehe [Heise](${LINK_ADDRESS})`)
  assert.equal(selected(edit.text, edit), LINK_ADDRESS)
})

test('a link without a selection uses the placeholder as its text', () => {
  assert.equal(applyFormat('link', '', 0, 0, placeholders).text, `[Link](${LINK_ADDRESS})`)
})

test('a picture is linked as an image, any other file as a link, without brackets in the label', () => {
  assert.equal(fileLink('foto.png', 'api/notes/files/1-foto.png', true), '![foto.png](api/notes/files/1-foto.png)')
  assert.equal(fileLink('Plan [neu].pdf', 'api/notes/files/2-plan.pdf', false), '[Plan neu.pdf](api/notes/files/2-plan.pdf)')
})

test('a block goes on a line of its own, apart from the text around it', () => {
  assert.equal(insertBlock('', 0, 'X').text, 'X')
  const middle = insertBlock('vorher nachher', 7, 'X')
  assert.equal(middle.text, 'vorher \n\nX\n\nnachher')
  assert.equal(middle.from, 'vorher \n\nX\n\n'.length)
  assert.equal(insertBlock('Zeile\n', 6, 'X').text, 'Zeile\n\nX')
  assert.equal(insertBlock('a\n\n', 3, 'X').text, 'a\n\nX')
})

test('the PDFs of a note are found, pictures and other links are not', () => {
  const text = [
    'Vorher [Plan](api/notes/files/1-plan.pdf)',
    '![Foto](api/notes/files/2-foto.png)',
    '[Heise](https://heise.de/x.pdf)',
    '[Zweiter](api/notes/files/3-b.PDF)',
  ].join('\n')
  assert.deepEqual(pdfLinks(text), [
    { name: 'Plan', url: 'api/notes/files/1-plan.pdf' },
    { name: 'Zweiter', url: 'api/notes/files/3-b.PDF' },
  ])
})
