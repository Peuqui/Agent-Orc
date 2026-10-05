<script setup lang="ts">
import { computed } from 'vue'
import type { Modifier, TerminalKey } from '../api'
import { TOUCH_FIRST } from '../device'
import { useSettings } from '../composables/useSettings'
import AppIcon from './AppIcon.vue'

const props = defineProps<{ rows: TerminalKey[][]; active: Set<Modifier> }>()
const emit = defineEmits<{
  send: [sequence: string]
  submit: [text: string]
  toggle: [modifier: Modifier]
}>()
// Folded, the first row stays (the keys used most go there in the config); the setting holds
// for every terminal on this device.
const { extraKeysUnfolded } = useSettings()
const shownRows = computed(() => (extraKeysUnfolded.value ? props.rows : props.rows.slice(0, 1)))

// The focus leaves the terminal's input field, so Android closes the keyboard; a tap into the
// terminal or the text field opens it again.
function hideKeyboard(): void {
  if (document.activeElement instanceof HTMLElement) document.activeElement.blur()
}

function press(key: TerminalKey): void {
  if (key.modifier) emit('toggle', key.modifier)
  else if (key.send && key.submit) emit('submit', key.send)
  else if (key.send) emit('send', key.send)
}
</script>

<template>
  <!-- pointerdown.prevent keeps the focus (and so the on-screen keyboard) where it is.
       Wide screens (landscape, desktop) put all rows side by side to save height. -->
  <div class="flex flex-col gap-1 border-t border-slate-800 bg-slate-900 px-1 py-1 md:flex-row">
    <div v-for="(row, index) in shownRows" :key="index" class="flex flex-1 gap-1">
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
      <button
        v-if="index === 0 && TOUCH_FIRST.matches"
        class="flex h-10 w-8 shrink-0 items-center justify-center rounded-md text-slate-400 select-none hover:bg-slate-800"
        :aria-label="$t('keys.hideKeyboard')"
        :title="$t('keys.hideKeyboard')"
        @pointerdown.prevent
        @click="hideKeyboard"
      >
        <AppIcon name="keyboard" />
      </button>
      <button
        v-if="index === 0 && rows.length > 1"
        class="flex h-10 w-8 shrink-0 items-center justify-center rounded-md text-slate-400 select-none hover:bg-slate-800"
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
