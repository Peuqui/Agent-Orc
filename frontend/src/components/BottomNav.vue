<script setup lang="ts">
import { useHeightVariable } from '../composables/useHeightVariable'
import { NAV_ITEMS } from '../navigation'
import AppIcon from './AppIcon.vue'

useHeightVariable('--bottom-nav-height', 'bar')
</script>

<!-- In the controls' size, and there whether it shows depends on the room it has then (the
     container), like the tabs in the page header it stands in for. The outer bar is not zoomed:
     its measured height is what is seen. A tab too narrow for its name shows only the icon. -->
<template>
  <nav ref="bar" class="fixed inset-x-0 bottom-0 z-30">
    <div class="controls-zoom @container">
      <div
        class="grid auto-cols-fr grid-flow-col border-t border-slate-800 bg-slate-900/95 pb-[calc(env(safe-area-inset-bottom)/var(--controls-zoom))] backdrop-blur @5xl:hidden"
      >
        <RouterLink
          v-for="item in NAV_ITEMS"
          :key="item.to"
          :to="item.to"
          class="@container flex min-h-14 flex-col items-center justify-center gap-0.5 text-xs text-slate-400"
          active-class="!text-red-400"
          :aria-label="$t(item.label)"
        >
          <AppIcon :name="item.icon" />
          <span class="@max-[3.5rem]:hidden">{{ $t(item.label) }}</span>
        </RouterLink>
      </div>
    </div>
  </nav>
</template>
