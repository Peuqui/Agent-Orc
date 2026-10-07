<script setup lang="ts">
import { NAV_ITEMS } from '../navigation'
import AppIcon from './AppIcon.vue'
</script>

<template>
  <nav
    class="fixed inset-x-0 bottom-0 z-30 grid auto-cols-fr grid-flow-col lg:hidden border-t border-slate-800 bg-slate-900/95 pb-[env(safe-area-inset-bottom)] backdrop-blur"
  >
    <RouterLink
      v-for="item in NAV_ITEMS"
      :key="item.to"
      :to="item.to"
      class="flex min-h-14 flex-col items-center justify-center gap-0.5 text-xs text-slate-400"
      active-class="!text-red-400"
    >
      <AppIcon :name="item.icon" />
      {{ $t(item.label) }}
    </RouterLink>
  </nav>
</template>
