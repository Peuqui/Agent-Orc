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
import GpuHoldChips from './GpuHoldChips.vue'
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
        <!-- The buttons take the room they need, the logo the rest: one line as high as the icon, so the
             name, where it does not fit beside the icon, wraps into a second line that is cut off. Wide,
             the logo takes its own width and the sections the rest. -->
        <AppLogo class="h-11 min-w-11 flex-1 flex-wrap content-start overflow-hidden sm:h-12 sm:min-w-12 @5xl:flex-none" />
        <!-- Wide: sections as header tabs instead of the bottom bar; their names where there is room. -->
        <div class="hidden flex-1 justify-center @5xl:flex">
          <SectionNav class="flex" label-class="hidden @6xl:inline" />
        </div>
        <!-- The hold pills beside the buttons; short of room the pills shrink to their dot (GpuHoldChips),
             and only where not even the dot fits do they wrap. The buttons never shrink (a fraction of a
             pixel would already wrap one): only wider than the whole room they wrap among themselves,
             so nothing covers the logo or leaves the screen. -->
        <div class="flex min-w-0 flex-wrap items-center justify-end gap-x-2 gap-y-1">
          <GpuHoldChips />
          <!-- Compact buttons, so the logo keeps its room on narrow screens. -->
          <div class="flex max-w-full shrink-0 flex-wrap items-center justify-end [&_.btn-icon]:size-8">
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
    </div>
  </header>
</template>
