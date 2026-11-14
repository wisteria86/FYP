import test from 'node:test'
import assert from 'node:assert/strict'
import { parseRoute, routePath, PAGES } from './ui/router.mjs'

test('every sidebar page has an address that reads back as the same page', () => {
  for (const view of Object.keys(PAGES)) {
    assert.deepEqual(parseRoute(routePath({ kind: 'page', view })), { kind: 'page', view })
  }
})

test('sessions, results and briefings round-trip through their addresses', () => {
  for (const route of [
    { kind: 'session', id: 'abc-123' },
    { kind: 'results', id: 'f00d' },
    { kind: 'briefing', skill: 'negotiation', level: 'advanced', activity: 'activity-negotiation' },
    { kind: 'briefing', skill: 'english-speaking', level: 'beginner', activity: null },
  ]) {
    const path = routePath(route)
    const [pathname, search = ''] = path.split('?')
    assert.deepEqual(parseRoute(pathname, search ? `?${search}` : ''), route)
  }
})

test('unknown addresses and trailing slashes are handled safely', () => {
  assert.deepEqual(parseRoute('/no-such-page'), { kind: 'page', view: 'home' })
  assert.deepEqual(parseRoute('/progress/'), { kind: 'page', view: 'progress' })
  assert.deepEqual(parseRoute('/briefing'), { kind: 'page', view: 'home' })
  assert.deepEqual(parseRoute('/session/<script>'), { kind: 'page', view: 'home' })
})
