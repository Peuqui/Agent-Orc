import assert from 'node:assert/strict'
import { test } from 'node:test'
import { boundaryShift, MAX_VISIBLE, MIN_WIDTH_SHARE } from '../src/composables/boundaryShift.ts'

test('a divider moves the boundary by the dragged distance', () => {
  assert.equal(boundaryShift(0.5, 0.5, 0.1), 0.1)
  assert.equal(boundaryShift(0.5, 0.5, -0.2), -0.2)
})

test('the left column stops at the smallest width, dragging left', () => {
  assert.ok(Math.abs(boundaryShift(0.5, 0.5, -5) - (MIN_WIDTH_SHARE - 0.5)) < 1e-12)
})

test('the right column stops at the smallest width, dragging right', () => {
  assert.ok(Math.abs(boundaryShift(0.5, 0.3, 5) - (0.3 - MIN_WIDTH_SHARE)) < 1e-12)
})

test('the sum of the two stays the same whatever the drag', () => {
  for (const moved of [-3, -0.2, 0, 0.05, 0.4, 3]) {
    const shift = boundaryShift(0.4, 0.35, moved)
    assert.ok(Math.abs(0.4 + shift + (0.35 - shift) - 0.75) < 1e-12)
  }
})

test('more columns than the smallest width allows are not offered', () => {
  assert.equal(MAX_VISIBLE, 10)
})
