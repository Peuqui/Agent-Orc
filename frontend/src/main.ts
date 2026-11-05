import { createApp } from 'vue'
import { registerSW } from 'virtual:pwa-register'
import App from './App.vue'
import { currentHost } from './api'
import { hostTranscription } from './dictationHost'
import { hostSpeech } from './speechHost'
import { setMachine } from './composables/useWorkspaceTab'
import { i18n } from './i18n'
import { router } from './router'
import { reloadToNewVersion } from './update'
// Watches presses from the start, so every dialog knows the control that opened it.
import './trigger'
// The terminal font, shipped with the app (see TERMINAL_FONTS).
import '@fontsource-variable/jetbrains-mono'
// Symbol fallback for the terminal fonts (see TERMINAL_FONTS), all of its parts.
import '@fontsource/noto-sans-symbols-2'
import './style.css'

// One service worker, the Zentrale's: its scope holds the pages of the other machines, too (below
// /hosts/<name>/), whose worker it is. A worker such a page registered when every machine had an
// app of its own would take its pages and push messages from the Zentrale's: it is removed.
if (currentHost === null) registerSW({ immediate: true })
else void unregisterOwnWorker()

async function unregisterOwnWorker(): Promise<void> {
  const registration = await navigator.serviceWorker?.getRegistration()
  if (registration?.scope === new URL('./', document.baseURI).href) await registration.unregister()
}

// After an install, a page still running the old version cannot load its parts any more (their
// file names changed, e.g. the workspace's): it switches to the new version by itself.
window.addEventListener('vite:preloadError', (event) => {
  event.preventDefault()
  void reloadToNewVersion()
})

// Before a workspace column can dictate or read aloud.
hostTranscription()
hostSpeech()

// Before any workspace is shown (it keeps what it remembers per machine).
setMachine(currentHost)

createApp(App).use(i18n).use(router).mount('#app')
