<script setup lang="ts">
import { NAV_ITEMS } from '../navigation'
import AppIcon from './AppIcon.vue'

// The main sections as links, the one list for the page header and the workspace's header. With
// their names as tabs; `compact` where room is short: icons, and the names only on a very wide
// screen. Whoever places it sets how it is laid out (display), as a class.
defineProps<{ compact?: boolean }>()
</script>

<template>
  <nav class="items-center gap-1">
    <RouterLink
      v-for="item in NAV_ITEMS"
      :key="item.to"
      :to="item.to"
      class="flex items-center gap-2 rounded-lg text-sm text-slate-400 hover:bg-slate-800 hover:text-slate-200"
      :class="compact ? 'p-2 2xl:px-4' : 'px-4 py-2'"
      active-class="!bg-slate-800 !text-red-400"
      :aria-label="$t(item.label)"
      :title="compact ? $t(item.label) : undefined"
    >
      <AppIcon :name="item.icon" /><span :class="compact ? 'hidden 2xl:inline' : ''">{{ $t(item.label) }}</span>
    </RouterLink>
  </nav>
</template>
