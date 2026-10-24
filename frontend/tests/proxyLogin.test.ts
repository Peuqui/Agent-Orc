import assert from 'node:assert/strict'
import { test } from 'node:test'
import { answeredByProxyLogin } from '../src/proxyLogin.ts'

test('a redirect to an HTML page is the proxy login', () => {
  assert.equal(answeredByProxyLogin(true, 'text/html; charset=utf-8'), true)
})

test('the app\'s own answers are not', () => {
  assert.equal(answeredByProxyLogin(false, 'application/json'), false)
  // A page of the app itself (e.g. a file opened in a tab of its own) arrives without a redirect.
  assert.equal(answeredByProxyLogin(false, 'text/html'), false)
  // A redirect the app follows on purpose to data is no login page either.
  assert.equal(answeredByProxyLogin(true, 'application/json'), false)
  assert.equal(answeredByProxyLogin(true, null), false)
})
