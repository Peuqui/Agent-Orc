<script setup lang="ts">
import { ref } from 'vue'
import { NAV_ITEMS } from '../navigation'
import AppIcon from './AppIcon.vue'
import DropdownMenu from './DropdownMenu.vue'

// The app's pages for views without the bottom bar (the workspace): one tap more, no room taken.
const open = ref(false)
</script>

<template>
  <DropdownMenu v-model:open="open" panel-class="flex w-52 flex-col p-1">
    <template #trigger="{ toggle }">
      <button class="btn-icon" :aria-label="$t('nav.menu')" :title="$t('nav.menu')" @click="toggle">
        <AppIcon name="apps" />
      </button>
    </template>
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
  </DropdownMenu>
</template>
