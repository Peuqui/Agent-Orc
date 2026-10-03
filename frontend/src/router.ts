import { createRouter, createWebHashHistory } from 'vue-router'
import FilesView from './views/FilesView.vue'
import SessionsView from './views/SessionsView.vue'
import TrashView from './views/TrashView.vue'

// Editor and terminal bring large libraries (CodeMirror, xterm.js), so they load on demand.
const EditorView = () => import('./views/EditorView.vue')
const TerminalView = () => import('./views/TerminalView.vue')

// Hash history: no server-side routing needed, also under a reverse-proxy sub-path.
export const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', redirect: '/sessions' },
    { path: '/sessions', component: SessionsView },
    { path: '/files', component: FilesView },
    { path: '/trash', component: TrashView },
    // Full screen: the terminal needs every pixel, especially with the keyboard open.
    { path: '/terminal/:id', component: TerminalView, props: true, meta: { fullscreen: true } },
    {
      path: '/edit',
      component: EditorView,
      props: (route) => ({ path: route.query.path }),
      meta: { fullscreen: true },
    },
  ],
})
