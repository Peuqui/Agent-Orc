import assert from 'node:assert/strict'
import { test } from 'node:test'
import { hostOf, hostPath, rootOf } from '../src/hostPaths.ts'

test('a page below /hosts/<name>/ belongs to that machine, any other to this one', () => {
  assert.equal(hostOf('/hosts/Aragon/'), 'Aragon')
  assert.equal(hostOf('/agent-orc/hosts/Aragon/'), 'Aragon')
  assert.equal(hostOf('/hosts/Der%20Rechner/'), 'Der Rechner')
  assert.equal(hostOf('/'), null)
  assert.equal(hostOf('/agent-orc/'), null)
})

test('the own app lies above the other machine, and below any proxy prefix', () => {
  assert.equal(rootOf('/hosts/Aragon/'), '/')
  assert.equal(rootOf('/agent-orc/hosts/Aragon/'), '/agent-orc/')
  assert.equal(rootOf('/agent-orc/'), '/agent-orc/')
})

test('another machine is reached from this one and from another machine alike', () => {
  assert.equal(hostPath('/', 'Aragon'), '/hosts/Aragon/')
  assert.equal(hostPath('/agent-orc/hosts/Aragon/', 'Mini'), '/agent-orc/hosts/Mini/')
  assert.equal(hostPath('/', 'Der Rechner'), '/hosts/Der%20Rechner/')
})
