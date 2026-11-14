// A small History API router: page addresses, Back and Forward, refresh and shareable links.
import { useCallback, useEffect, useState } from 'react'

// Sidebar view ids and their addresses. 'home' is the root.
export const PAGES = {
  home: '/',
  path: '/learning-path',
  training: '/training',
  progress: '/progress',
  plan: '/plan',
  resources: '/resources',
  settings: '/settings',
  monitor: '/monitor',
}
const PAGE_BY_PATH = Object.fromEntries(Object.entries(PAGES).map(([view, path]) => [path, view]))

// Turn an address into what the app should show.
export function parseRoute(pathname = '/', search = '') {
  const clean = ('/' + pathname.split('/').filter(Boolean).join('/')) || '/'
  const query = Object.fromEntries(new URLSearchParams(search))
  const session = clean.match(/^\/session\/([\w-]+)$/)
  if (session) return { kind: 'session', id: session[1] }
  const results = clean.match(/^\/results\/([\w-]+)$/)
  if (results) return { kind: 'results', id: results[1] }
  if (clean === '/briefing' && query.skill) {
    return { kind: 'briefing', skill: query.skill, level: query.level || 'intermediate', activity: query.activity || null }
  }
  return { kind: 'page', view: PAGE_BY_PATH[clean] || 'home' }
}

// The address for something the app shows.
export function routePath(route) {
  if (route.kind === 'session') return `/session/${route.id}`
  if (route.kind === 'results') return `/results/${route.id}`
  if (route.kind === 'briefing') {
    const query = new URLSearchParams({ skill: route.skill, level: route.level || 'intermediate' })
    if (route.activity) query.set('activity', route.activity)
    return `/briefing?${query}`
  }
  return PAGES[route.view] || '/'
}

export function useRoute() {
  const read = () => parseRoute(window.location.pathname, window.location.search)
  const [route, setRoute] = useState(read)
  useEffect(() => {
    const onPop = () => setRoute(read())
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [])
  // replace: true changes the current history entry instead of adding one.
  const navigate = useCallback((next, { replace = false } = {}) => {
    const path = routePath(next)
    if (path !== window.location.pathname + window.location.search) {
      window.history[replace ? 'replaceState' : 'pushState'](null, '', path)
    }
    setRoute(parseRoute(window.location.pathname, window.location.search))
    if (!replace) window.scrollTo?.(0, 0)
  }, [])
  return [route, navigate]
}
