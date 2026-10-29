<script setup lang="ts">
import { useHeightVariable } from '../composables/useHeightVariable'
import { NAV_ITEMS } from '../navigation'
import AppIcon from './AppIcon.vue'

useHeightVariable('--bottom-nav-height', 'bar')
</script>

<!-- In the controls' size, and there whether it shows depends on the room it has then (the
     container), like the tabs in the page header it stands in for. The outer bar is not zoomed:
     its measured height is what is seen. A tab too narrow for its name shows only the icon; a name a little too long is cut
     with an ellipsis instead of running into its neighbour. -->
<template>
  <nav ref="bar" class="fixed inset-x-0 bottom-0 z-30">
    <div class="controls-zoom @container">
      <div
        class="grid auto-cols-fr grid-flow-col border-t border-line-subtle bg-page/95 pb-[calc(env(safe-area-inset-bottom)/var(--controls-zoom))] backdrop-blur @5xl:hidden"
      >
        <RouterLink
          v-for="item in NAV_ITEMS"
          :key="item.to"
          :to="item.to"
          class="@container flex min-h-14 flex-col items-center justify-center gap-0.5 text-xs text-dim"
          active-class="!text-accent-400"
          :aria-label="$t(item.label)"
        >
          <AppIcon :name="item.icon" />
          <span class="max-w-full truncate px-0.5 @max-[3.5rem]:hidden">{{ $t(item.label) }}</span>
        </RouterLink>
      </div>
    </div>
  </nav>
</template>
