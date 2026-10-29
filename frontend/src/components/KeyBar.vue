<script setup lang="ts">
import { computed } from 'vue'
import type { Modifier, TerminalKey } from '../api'
import { TOUCH_FIRST } from '../device'
import { useSettings } from '../composables/useSettings'
import AppIcon from './AppIcon.vue'

const props = defineProps<{ rows: TerminalKey[][]; active: Set<Modifier>; keyboardUp: boolean }>()
const emit = defineEmits<{
  send: [sequence: string]
  submit: [text: string]
  toggle: [modifier: Modifier]
  toggleKeyboard: []
}>()
// The keyboard button (on touch screens) raises or lowers the on-screen keyboard: TerminalView
// knows what it is raised for (the terminal itself or the message field).
// Folded, the first row stays (the keys used most go there in the config); the setting holds
// for every terminal on this device.
const { extraKeysUnfolded } = useSettings()
const shownRows = computed(() => (extraKeysUnfolded.value ? props.rows : props.rows.slice(0, 1)))

function press(key: TerminalKey): void {
  if (key.modifier) emit('toggle', key.modifier)
  else if (key.send && key.submit) emit('submit', key.send)
  else if (key.send) emit('send', key.send)
}
</script>

<template>
  <!-- pointerdown.prevent keeps the focus (and so the on-screen keyboard) where it is.
       Wide screens (landscape, desktop) put all rows side by side to save height. -->
  <div class="controls-zoom flex flex-col gap-1 border-t border-line-subtle bg-page px-1 py-1 md:flex-row">
    <div v-for="(row, index) in shownRows" :key="index" class="flex flex-1 gap-1">
      <button
        v-for="key in row"
        :key="key.label"
        class="h-10 min-w-0 flex-1 rounded-md text-sm font-medium select-none"
        :class="
          key.modifier && active.has(key.modifier)
            ? 'bg-accent-600 text-on-color'
            : 'bg-panel text-main active:bg-raised-strong'
        "
        @pointerdown.prevent
        @click="press(key)"
      >
        {{ key.label }}
      </button>
      <button
        v-if="index === 0 && TOUCH_FIRST.matches"
        class="flex h-10 w-8 shrink-0 items-center justify-center rounded-md select-none hover:bg-panel"
        :class="keyboardUp ? 'text-highlight-300' : 'text-dim'"
        :aria-label="$t(keyboardUp ? 'keys.hideKeyboard' : 'keys.showKeyboard')"
        :title="$t(keyboardUp ? 'keys.hideKeyboard' : 'keys.showKeyboard')"
        :aria-pressed="keyboardUp"
        @pointerdown.prevent
        @click="emit('toggleKeyboard')"
      >
        <AppIcon name="keyboard" />
      </button>
      <button
        v-if="index === 0 && rows.length > 1"
        class="flex h-10 w-8 shrink-0 items-center justify-center rounded-md text-dim select-none hover:bg-panel"
        :aria-label="$t(extraKeysUnfolded ? 'keys.fold' : 'keys.unfold')"
        :title="$t(extraKeysUnfolded ? 'keys.fold' : 'keys.unfold')"
        @pointerdown.prevent
        @click="extraKeysUnfolded = !extraKeysUnfolded"
      >
        <AppIcon name="chevron" :class="extraKeysUnfolded ? '' : 'rotate-180'" />
      </button>
    </div>
  </div>
</template>
