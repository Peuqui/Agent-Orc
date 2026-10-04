import { createApp } from 'vue'
import { registerSW } from 'virtual:pwa-register'
import App from './App.vue'
import { i18n } from './i18n'
import { router } from './router'
// The terminal font, shipped with the app (see TERMINAL_FONTS).
import '@fontsource-variable/jetbrains-mono'
// Only the symbols part of Noto Sans Symbols 2 (see TERMINAL_FONTS).
import '@fontsource/noto-sans-symbols-2/symbols.css'
import './style.css'

registerSW({ immediate: true })

createApp(App).use(i18n).use(router).mount('#app')
