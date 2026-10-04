<script setup lang="ts">
import { ref } from 'vue'
import { useDismiss } from '../composables/useDismiss'
import { NAV_ITEMS } from '../navigation'
import AppIcon from './AppIcon.vue'

// The app's pages for views without the bottom bar (the workspace): one tap more, no room taken.
const open = ref(false)
const root = ref<HTMLElement>()
useDismiss(root, () => open.value, () => (open.value = false))
</script>

<template>
  <div ref="root" class="relative">
    <button class="btn-icon" :aria-label="$t('nav.menu')" :title="$t('nav.menu')" @click="open = !open">
      <AppIcon name="apps" />
    </button>
    <nav v-if="open" class="card absolute top-full left-0 z-40 mt-1 flex w-52 flex-col p-1 shadow-xl">
      <RouterLink
        v-for="item in NAV_ITEMS"
        :key="item.to"
        :to="item.to"
        class="flex items-center gap-2 rounded-md px-3 py-2 text-sm text-slate-300 hover:bg-slate-700"
        active-class="!text-red-400"
        @click="open = false"
      >
        <AppIcon :name="item.icon" />{{ $t(item.label) }}
      </RouterLink>
    </nav>
  </div>
</template>
