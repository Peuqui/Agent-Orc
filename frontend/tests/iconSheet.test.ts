import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import { iconSheet, SHEET_HTML } from '../scripts/iconSheet.ts'
import { ICONS } from '../src/icons.ts'

test('the icon overview in docs/icons shows the icons as icons.ts holds them (npm run icons)', () => {
  assert.equal(readFileSync(SHEET_HTML, 'utf8'), iconSheet(ICONS))
})
