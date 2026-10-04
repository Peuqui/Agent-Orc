import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import { VitePWA } from 'vite-plugin-pwa'

// Identifies this build: baked into the app and written next to it, where the server reads it
// and sends it along with every response, so an open app notices a newer installed version.
const BUILD_ID = new Date().toISOString()
// The server reads this file name too (agent_orc.api.BUILD_ID_FILE).
const BUILD_ID_FILE = 'build-id.txt'

// Relative base: the app works at / locally and under a sub-path (e.g. /agent-orc/) behind a proxy.
export default defineConfig({
  base: './',
  define: {
    __BUILD_ID__: JSON.stringify(BUILD_ID),
  },
  build: {
    // Bundled into the Python package, so installs need no Node.
    outDir: '../src/agent_orc/static',
    emptyOutDir: true,
  },
  plugins: [
    {
      name: 'build-id',
      generateBundle() {
        this.emitFile({ type: 'asset', fileName: BUILD_ID_FILE, source: BUILD_ID })
      },
    },
    vue(),
    tailwindcss(),
    VitePWA({
      registerType: 'autoUpdate',
      // Shows Agent-Orc's push messages (public/push-sw.js).
      workbox: { importScripts: ['push-sw.js'] },
      // The manifest request must carry credentials when a reverse proxy uses HTTP basic auth.
      useCredentials: true,
      manifest: {
        name: 'Agent-Ørc — Agent Orchestrator',
        short_name: 'Agent-Ørc',
        start_url: './',
        scope: './',
        display: 'standalone',
        theme_color: '#0a0a0a',
        background_color: '#0a0a0a',
        icons: [
          { src: 'pwa-192x192.png', sizes: '192x192', type: 'image/png' },
          { src: 'pwa-512x512.png', sizes: '512x512', type: 'image/png' },
          { src: 'maskable-512x512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
        ],
      },
    }),
  ],
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8770',
    },
  },
})
