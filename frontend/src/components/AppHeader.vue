<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { api, authenticated } from '../api'
import { LOCALES, setLocale, type Locale } from '../i18n'
import { useHeightVariable } from '../composables/useHeightVariable'
import SectionNav from './SectionNav.vue'
import AppIcon from './AppIcon.vue'
import HelpButton from './HelpButton.vue'
import SettingsMenu from './SettingsMenu.vue'
import AppLogo from './AppLogo.vue'
import HostSwitcher from './HostSwitcher.vue'
import SelectMenu from './SelectMenu.vue'

const { locale } = useI18n()
const LANGUAGE_OPTIONS = LOCALES.map((code) => ({ value: code, label: code.toUpperCase() }))

useHeightVariable('--app-header-height', 'header')

async function logout(): Promise<void> {
  await api.logout()
  authenticated.value = false
}
</script>

<template>
  <header ref="header" class="sticky top-0 z-30 border-b border-line-subtle bg-page/95 backdrop-blur">
    <!-- What shows depends on the room in the controls' size (the container: the whole width, the
         same as the bottom bar's, so that exactly one of them has the sections), not on the screen. -->
    <div class="controls-zoom @container">
      <div class="page-width flex items-center justify-between gap-4 py-2">
        <AppLogo name-class="hidden @[17rem]:flex" />
        <!-- Wide: sections as header tabs instead of the bottom bar; their names where there is room. -->
        <div class="hidden flex-1 justify-center @5xl:flex">
          <SectionNav class="flex" label-class="hidden @6xl:inline" />
        </div>
        <!-- Compact buttons, so the logo keeps its room on narrow screens. -->
        <div class="flex shrink-0 items-center [&_.btn-icon]:size-8">
          <HostSwitcher />
          <SelectMenu
            class="mr-1"
            button-class="h-6 rounded-md border border-line bg-panel pr-0.5 pl-1.5 text-xs text-soft"
            :model-value="locale"
            :options="LANGUAGE_OPTIONS"
            :aria-label="$t('app.language')"
            @update:model-value="(code) => setLocale(code as Locale)"
          />
          <HelpButton />
          <SettingsMenu />
          <button class="btn-icon" :title="$t('app.logout')" :aria-label="$t('app.logout')" @click="logout">
            <AppIcon name="logout" />
          </button>
        </div>
      </div>
    </div>
  </header>
</template>
