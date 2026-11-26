<script setup lang="ts">
import { api, authenticated } from '../api'
import { useHeightVariable } from '../composables/useHeightVariable'
import SectionNav from './SectionNav.vue'
import AppIcon from './AppIcon.vue'
import SettingsMenu from './SettingsMenu.vue'
import AppLogo from './AppLogo.vue'
import HostSwitcher from './HostSwitcher.vue'
import WithBannerChips from './WithBannerChips.vue'

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
      <!-- Where not even the logo's icon (and a pill's smallest size) fits beside the buttons (large
           controls on a narrow phone), the buttons wrap to a line of their own. -->
      <div class="page-width flex flex-wrap items-center justify-between gap-x-4 gap-y-2 py-2">
        <!-- The buttons take the room they need, the logo the rest, and the banner's pills what the logo leaves
             (WithBannerChips). The logo is one line as high as the icon, so the name, where it does not fit
             beside the icon, wraps into a second line that is cut off. Wide, logo and pills take their own
             width and the sections the rest. -->
        <WithBannerChips
          class="@5xl:flex-none"
          min-class="min-w-11 sm:min-w-12 has-[[data-banner-chip]]:min-w-18 sm:has-[[data-banner-chip]]:min-w-19"
        >
          <AppLogo class="h-11 min-w-11 flex-wrap content-start overflow-hidden sm:h-12 sm:min-w-12" />
        </WithBannerChips>
        <!-- Wide: sections as header tabs instead of the bottom bar; their names where there is room. -->
        <div class="hidden flex-1 justify-center @5xl:flex">
          <SectionNav class="flex" label-class="hidden @6xl:inline" />
        </div>
        <!-- Compact buttons, so the logo keeps its room on narrow screens. They never shrink (a fraction of
             a pixel would already wrap one): only wider than the whole row they wrap among themselves, so
             nothing leaves the screen. -->
        <div class="ml-auto flex max-w-full shrink-0 flex-wrap items-center justify-end [&_.btn-icon]:size-8">
          <HostSwitcher />
          <SettingsMenu />
          <button class="btn-icon" :title="$t('app.logout')" :aria-label="$t('app.logout')" @click="logout">
            <AppIcon name="logout" />
          </button>
        </div>
      </div>
    </div>
  </header>
</template>
