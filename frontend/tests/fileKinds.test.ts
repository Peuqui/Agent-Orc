import assert from 'node:assert/strict'
import { test } from 'node:test'
import { isTextKind, kindOfFile } from '../src/fileKinds.ts'

test('a file is shown by its extension, in any case', () => {
  assert.equal(kindOfFile('README.md'), 'markdown')
  assert.equal(kindOfFile('bericht.HTML'), 'html')
  assert.equal(kindOfFile('seite.htm'), 'html')
  assert.equal(kindOfFile('rechnung.pdf'), 'pdf')
  assert.equal(kindOfFile('brief.docx'), 'docx')
  assert.equal(kindOfFile('foto.JPG'), 'image')
  assert.equal(kindOfFile('ansage.opus'), 'audio')
  assert.equal(kindOfFile('clip.webm'), 'video')
})

test('anything else is tried as text, also without an extension or with a leading dot', () => {
  assert.equal(kindOfFile('main.py'), 'text')
  assert.equal(kindOfFile('Makefile'), 'text')
  assert.equal(kindOfFile('.bashrc'), 'text')
  assert.equal(kindOfFile('archiv.tar.gz'), 'text')
})

test('Markdown and HTML are text to edit as well as pages', () => {
  assert.ok(isTextKind('text') && isTextKind('markdown') && isTextKind('html'))
  assert.ok(!isTextKind('pdf') && !isTextKind('docx') && !isTextKind('image') && !isTextKind('binary'))
})
