<script setup lang="ts">
import type { Modifier, TerminalKey } from '../api'

defineProps<{ rows: TerminalKey[][]; active: Set<Modifier> }>()
const emit = defineEmits<{ send: [sequence: string]; toggle: [modifier: Modifier] }>()

function press(key: TerminalKey): void {
  if (key.modifier) emit('toggle', key.modifier)
  else if (key.send) emit('send', key.send)
}
</script>

<template>
  <!-- pointerdown.prevent keeps the focus (and so the on-screen keyboard) where it is.
       Wide screens (landscape, desktop) put all rows side by side to save height. -->
  <div class="flex flex-col gap-1 border-t border-slate-800 bg-slate-900 px-1 py-1 md:flex-row">
    <div v-for="(row, index) in rows" :key="index" class="flex flex-1 gap-1">
      <button
        v-for="key in row"
        :key="key.label"
        class="h-10 min-w-0 flex-1 rounded-md text-sm font-medium select-none"
        :class="
          key.modifier && active.has(key.modifier)
            ? 'bg-red-600 text-white'
            : 'bg-slate-800 text-slate-200 active:bg-slate-600'
        "
        @pointerdown.prevent
        @click="press(key)"
      >
        {{ key.label }}
      </button>
    </div>
  </div>
</template>
