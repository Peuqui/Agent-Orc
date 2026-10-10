import assert from 'node:assert/strict'
import { test } from 'node:test'
import { collect, freeName, renameTakenFolders } from '../src/uploadTree.ts'

// Stands in for what the browser gives of a dropped folder.
const file = (name: string) => ({ isFile: true, name, file: (done: (file: File) => void) => done(new File(['x'], name)) })
const folder = (name: string, children: unknown[], batch = 100) => ({
  isFile: false,
  name,
  createReader: () => {
    const rest = [...children]
    return { readEntries: (done: (entries: unknown[]) => void) => done(rest.splice(0, batch)) }
  },
})

test('a dropped folder gives its files with the folder each lies in', async () => {
  const dropped = folder('proj', [file('README.md'), folder('src', [file('a.py'), folder('app', [file('b.py')])])])
  const items = await collect(dropped as unknown as FileSystemEntry, '')
  assert.deepEqual(
    items.map((item) => `${item.directory}/${item.file.name}`).sort(),
    ['proj/README.md', 'proj/src/a.py', 'proj/src/app/b.py'],
  )
})

test('a file dropped by itself lies in the open folder', async () => {
  const items = await collect(file('probe.mp3') as unknown as FileSystemEntry, '')
  assert.deepEqual(items.map((item) => item.directory), [''])
})

test('a folder with more entries than one batch is read through', async () => {
  const many = Array.from({ length: 250 }, (_, number) => file(`f${number}.txt`))
  const items = await collect(folder('big', many, 100) as unknown as FileSystemEntry, '')
  assert.equal(items.length, 250)
})

test('a taken name gets a number', () => {
  assert.equal(freeName('proj', new Set()), 'proj')
  assert.equal(freeName('proj', new Set(['proj'])), 'proj-2')
  assert.equal(freeName('proj', new Set(['proj', 'proj-2'])), 'proj-3')
})

test('a dropped folder whose name is taken is renamed as a whole, files stay as they are', () => {
  const item = (directory: string, name: string) => ({ file: new File(['x'], name), directory })
  const renamed = renameTakenFolders(
    [item('proj', 'a.py'), item('proj/src', 'b.py'), item('other', 'c.py'), item('', 'loose.txt')],
    ['proj', 'readme.md'],
  )
  assert.deepEqual(
    renamed.map((entry) => entry.directory),
    ['proj-2', 'proj-2/src', 'other', ''],
  )
})
