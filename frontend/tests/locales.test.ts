import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import { baseCompile } from '@intlify/message-compiler'

type Messages = { [key: string]: string | Messages | Messages[] }

const LOCALES = ['de', 'en']

function load(locale: string): Messages {
  return JSON.parse(readFileSync(new URL(`../src/locales/${locale}.json`, import.meta.url), 'utf8')) as Messages
}

/** Every text of a language file with its path. */
function* texts(node: unknown, path: string): Generator<[string, string]> {
  if (typeof node === 'string') yield [path, node]
  else if (node && typeof node === 'object') {
    for (const [key, value] of Object.entries(node)) yield* texts(value, `${path}.${key}`)
  }
}

test('every text compiles as a vue-i18n message', () => {
  // A stray @, |, { or } makes the message a syntax error at the moment it is shown (the help
  // dialog vanished over an unescaped @); write them as {'@'}, {'|'}, ...
  const broken: string[] = []
  for (const locale of LOCALES) {
    for (const [path, text] of texts(load(locale), locale)) {
      try {
        baseCompile(text, {
          onError: (error) => {
            throw error
          },
        })
      } catch (error) {
        broken.push(`${path}: ${(error as Error).message}`)
      }
    }
  }
  assert.deepEqual(broken, [])
})

test('the languages have the same texts', () => {
  const [german, english] = LOCALES.map((locale) => [...texts(load(locale), '')].map(([path]) => path))
  assert.deepEqual(german.filter((path) => !english.includes(path)), [])
  assert.deepEqual(english.filter((path) => !german.includes(path)), [])
})
