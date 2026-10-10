import { createRouter, createWebHashHistory } from 'vue-router'
import { currentHost, rootAddress } from './api'
import FilesView from './views/FilesView.vue'
import SessionsView from './views/SessionsView.vue'
import ConsumptionView from './views/ConsumptionView.vue'
import ConversationsView from './views/ConversationsView.vue'
import NotesView from './views/NotesView.vue'

// Editor and terminal bring large libraries (CodeMirror, xterm.js), so they load on demand.
const EditorView = () => import('./views/EditorView.vue')
const TerminalView = () => import('./views/TerminalView.vue')
const WorkspaceView = () => import('./views/WorkspaceView.vue')
const ChangesView = () => import('./views/ChangesView.vue')

// Hash history: no server-side routing needed, also under a reverse-proxy sub-path.
export const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', redirect: '/sessions' },
    { path: '/sessions', component: SessionsView },
    { path: '/notes', component: NotesView },
    { path: '/files', component: FilesView },
    { path: '/peers', component: ConversationsView },
    { path: '/consumption', component: ConsumptionView },
    // Full screen: the terminal needs every pixel, especially with the keyboard open.
    { path: '/workspace', component: WorkspaceView, meta: { fullscreen: true } },
    // One agent's terminal; the workspace shows it embedded (?embedded) in an iframe.
    {
      path: '/terminal/:id',
      component: TerminalView,
      props: (route) => ({ id: route.params.id, embedded: 'embedded' in route.query }),
      meta: { fullscreen: true },
    },
    // What an agent changed in its project (git).
    {
      path: '/changes/:id',
      component: ChangesView,
      props: true,
      meta: { fullscreen: true },
    },
    {
      path: '/edit',
      component: EditorView,
      props: (route) => ({ path: route.query.path, line: Number(route.query.line) || null }),
      meta: { fullscreen: true, perQuery: true },
    },
  ],
})

// A workspace never runs inside a column of another (it would take the tab's workspace for its
// own and store its single column under that name). From a column, the request goes to the
// browser tab's workspace, e.g. a new agent started from the column's file view.
router.beforeEach((to) => {
  if (to.path !== '/workspace' || window.top === null || window.self === window.top) return true
  window.top.location.hash = to.fullPath
  return false
})

// The agents of all machines are listed in one overview, which this machine's own app shows: from
// another machine's page, "Agents" leads there.
router.beforeEach((to) => {
  if (currentHost === null || to.path !== '/sessions') return true
  window.location.assign(`${rootAddress()}#${to.fullPath}`)
  return false
})
