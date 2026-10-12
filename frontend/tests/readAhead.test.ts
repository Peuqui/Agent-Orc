import assert from 'node:assert/strict'
import { test } from 'node:test'
import { readAhead } from '../src/readAhead.ts'

/** A piece of text the test finishes by hand: `receive()` is "all its audio is here", `end()` "it was spoken". */
function fakeEngine() {
  const events: string[] = []
  const pieces = new Map<string, { receive: () => void; end: () => void; fail: (error: Error) => void }>()
  const begin = (text: string) => {
    events.push(`begin ${text}`)
    let receive!: () => void
    let fail!: (error: Error) => void
    const received = new Promise<void>((resolve, reject) => ((receive = resolve), (fail = reject)))
    let end!: () => void
    const ended = received.then(() => new Promise<void>((resolve) => (end = resolve)))
    pieces.set(text, { receive, fail, end: () => end() })
    return { received, ended }
  }
  return { events, pieces, begin }
}

const answers = ['a', 'b', 'c'].map((text) => ({ item: text, text }))
/** Lets the promise chains of the code under test run. */
const settle = () => new Promise((resolve) => setImmediate(resolve))

test('the next answer is sent when the one before is here, not when it was spoken', async () => {
  const engine = fakeEngine()
  const log: string[] = []
  const reading = readAhead(answers, {
    begin: engine.begin, active: () => true,
    started: (item) => log.push(`started ${item}`), finished: (item) => log.push(`finished ${item}`),
  })
  await settle()
  assert.deepEqual(engine.events, ['begin a'])                    // nothing else before a is here
  engine.pieces.get('a')!.receive()
  await settle()
  assert.deepEqual(engine.events, ['begin a', 'begin b'])         // b goes out while a is being spoken
  assert.deepEqual(log, ['started a'])
  engine.pieces.get('b')!.receive()
  engine.pieces.get('a')!.end()
  await settle()
  assert.deepEqual(engine.events, ['begin a', 'begin b', 'begin c'])
  engine.pieces.get('c')!.receive()
  engine.pieces.get('b')!.end()
  await settle()
  engine.pieces.get('c')!.end()
  await reading
  assert.deepEqual(log, ['started a', 'finished a', 'started b', 'finished b', 'started c', 'finished c'])
})

test('after a stop nothing more is sent and nothing is reported', async () => {
  const engine = fakeEngine()
  let on = true
  const log: string[] = []
  const reading = readAhead(answers, {
    begin: engine.begin, active: () => on,
    started: (item) => log.push(`started ${item}`), finished: (item) => log.push(`finished ${item}`),
  })
  await settle()
  on = false                                  // stopped while a is still being made
  engine.pieces.get('a')!.receive()
  await settle()
  engine.pieces.get('a')!.end()               // a cancelled engine ends what was queued
  await reading
  assert.deepEqual(engine.events, ['begin a'])
  assert.deepEqual(log, ['started a'])        // not reported as spoken
})

test('a failure ends the reading with that error and sends no further answer', async () => {
  const engine = fakeEngine()
  const reading = readAhead(answers, {
    begin: engine.begin, active: () => true, started: () => undefined, finished: () => undefined,
  })
  await settle()
  engine.pieces.get('a')!.fail(new Error('refused'))
  await assert.rejects(reading, /refused/)
  assert.deepEqual(engine.events, ['begin a'])
})
