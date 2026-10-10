import assert from 'node:assert/strict'
import { test } from 'node:test'

// The module reads the window and the storages once it loads.
const storage = () => {
  const items = new Map<string, string>()
  return {
    getItem: (key: string) => items.get(key) ?? null,
    setItem: (key: string, value: string) => void items.set(key, value),
  }
}
Object.assign(globalThis, {
  window: { matchMedia: () => ({ matches: false }) },
  localStorage: storage(),
  sessionStorage: storage(),
})
const { homeOf, rememberLastWorkspace, setMachine, startWorkspace, unnamedListed } = await import('../src/composables/useWorkspaceTab.ts')

const workspace = (tabs: string[]) => ({ tabs, visible: 1, widths: {}, active: null })
const everything = { unnamed: workspace(['loose-1']), named: { Links: workspace(['left-2']), Rechts: workspace([]) } }

test('an agent is found in the workspace it lives in', () => {
  assert.equal(homeOf(everything, 'loose-1'), null)
  assert.equal(homeOf(everything, 'left-2'), 'Links')
  assert.equal(homeOf(everything, 'nowhere-3'), undefined)
})

test('the unnamed workspace is listed while it holds agents, is shown, or is the only one', () => {
  assert.equal(unnamedListed(2, 1, false), true)
  assert.equal(unnamedListed(2, 0, false), false)
  assert.equal(unnamedListed(2, 0, true), true)
  assert.equal(unnamedListed(0, 0, false), true)
})

test('a tab without a workspace starts with the unnamed one while it holds agents', () => {
  assert.equal(startWorkspace(everything), null)
  const emptied = { ...everything, unnamed: workspace([]) }
  assert.equal(startWorkspace(emptied), 'Links')
})

test('what a tab remembers is kept per machine, as both apps share the browser', () => {
  const everythingNamed = { unnamed: workspace([]), named: { Links: workspace([]), Rechts: workspace([]) } }
  rememberLastWorkspace('Rechts')
  assert.equal(startWorkspace(everythingNamed), 'Rechts')
  setMachine('Aragon')
  // Aragon has remembered nothing yet: the first by name.
  assert.equal(startWorkspace(everythingNamed), 'Links')
  rememberLastWorkspace('Rechts')
  setMachine(null)
  assert.equal(startWorkspace(everythingNamed), 'Rechts')
})
