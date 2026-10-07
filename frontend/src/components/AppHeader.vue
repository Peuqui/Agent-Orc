<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { api, authenticated } from '../api'
import { LOCALES, setLocale, type Locale } from '../i18n'
import { NAV_ITEMS } from '../navigation'
import AppIcon from './AppIcon.vue'
import HelpButton from './HelpButton.vue'
import SettingsMenu from './SettingsMenu.vue'
import AppLogo from './AppLogo.vue'

const { locale } = useI18n()

async function logout(): Promise<void> {
  await api.logout()
  authenticated.value = false
}
</script>

<template>
  <header class="sticky top-0 z-30 border-b border-slate-800 bg-slate-900/95 backdrop-blur">
    <div class="page-width flex items-center justify-between gap-4 py-2">
      <AppLogo />
      <!-- Wide screens: sections as header tabs instead of the bottom bar. -->
      <nav class="hidden flex-1 justify-center gap-1 lg:flex">
        <RouterLink
          v-for="item in NAV_ITEMS"
          :key="item.to"
          :to="item.to"
          class="flex items-center gap-2 rounded-lg px-4 py-2 text-sm text-slate-400 hover:bg-slate-800 hover:text-slate-200"
          active-class="!bg-slate-800 !text-red-400"
        >
          <AppIcon :name="item.icon" />{{ $t(item.label) }}
        </RouterLink>
      </nav>
      <!-- Compact buttons, so the logo keeps its room on narrow screens. -->
      <div class="flex shrink-0 items-center [&_.btn-icon]:size-8">
        <select
          class="mr-1 h-6 rounded-md border border-slate-700 bg-slate-800 px-1 text-xs text-slate-300"
          :aria-label="$t('app.language')"
          :value="locale"
          @change="setLocale(($event.target as HTMLSelectElement).value as Locale)"
        >
          <option v-for="code in LOCALES" :key="code" :value="code">{{ code.toUpperCase() }}</option>
        </select>
        <HelpButton />
        <SettingsMenu />
        <button class="btn-icon" :title="$t('app.logout')" :aria-label="$t('app.logout')" @click="logout">
          <AppIcon name="logout" />
        </button>
      </div>
    </div>
  </header>
</template>
