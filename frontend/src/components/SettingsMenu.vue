<script setup lang="ts">
import { ref } from 'vue'
import { MAX_SCROLL_LINES, MIN_SCROLL_LINES, useSettings } from '../composables/useSettings'
import AppIcon from './AppIcon.vue'

// Settings of this device; more entries join here as they become adjustable.
const { scrollLines } = useSettings()
const open = ref(false)

function changeScrollLines(delta: number): void {
  scrollLines.value = Math.min(MAX_SCROLL_LINES, Math.max(MIN_SCROLL_LINES, scrollLines.value + delta))
}
</script>

<template>
  <div class="relative">
    <button class="btn-icon" :title="$t('settings.title')" :aria-label="$t('settings.title')" @click="open = !open">
      <AppIcon name="settings" />
    </button>
    <div v-if="open" class="card absolute top-full right-0 z-30 mt-1 w-64 p-3 shadow-xl">
      <h2 class="mb-2 text-sm font-semibold text-slate-200">{{ $t('settings.title') }}</h2>
      <div class="flex items-center justify-between gap-2 text-sm text-slate-300">
        <span>{{ $t('settings.scrollLines') }}</span>
        <div class="flex items-center gap-1">
          <button class="btn-icon size-7" :aria-label="$t('settings.less')" @click="changeScrollLines(-1)">−</button>
          <span class="w-6 text-center tabular-nums">{{ scrollLines }}</span>
          <button class="btn-icon size-7" :aria-label="$t('settings.more')" @click="changeScrollLines(1)">+</button>
        </div>
      </div>
      <p class="mt-1 text-xs text-slate-500">{{ $t('settings.scrollLinesHint') }}</p>
    </div>
  </div>
</template>
