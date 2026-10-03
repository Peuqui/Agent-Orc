import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import { VitePWA } from 'vite-plugin-pwa'

// Relative base: the app works at / locally and under a sub-path (e.g. /ai-orc/) behind a proxy.
export default defineConfig({
  base: './',
  build: {
    // Bundled into the Python package, so installs need no Node.
    outDir: '../src/ai_orc/static',
    emptyOutDir: true,
  },
  plugins: [
    vue(),
    tailwindcss(),
    VitePWA({
      registerType: 'autoUpdate',
      // The manifest request must carry credentials when a reverse proxy uses HTTP basic auth.
      useCredentials: true,
      manifest: {
        name: 'AI-Ørc — Agent Orchestrator',
        short_name: 'AI-Ørc',
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
