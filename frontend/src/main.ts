import { createApp } from 'vue'
import { registerSW } from 'virtual:pwa-register'
import App from './App.vue'
import { i18n } from './i18n'
import { router } from './router'
import { reloadToNewVersion } from './update'
// The terminal font, shipped with the app (see TERMINAL_FONTS).
import '@fontsource-variable/jetbrains-mono'
// Symbol fallback for the terminal fonts (see TERMINAL_FONTS), all of its parts.
import '@fontsource/noto-sans-symbols-2'
import './style.css'

registerSW({ immediate: true })

// After an install, a page still running the old version cannot load its parts any more (their
// file names changed, e.g. the workspace's): it switches to the new version by itself.
window.addEventListener('vite:preloadError', (event) => {
  event.preventDefault()
  void reloadToNewVersion()
})

createApp(App).use(i18n).use(router).mount('#app')
