<script setup lang="ts">
import { ref } from 'vue'
import { useDismiss } from '../composables/useDismiss'

// A button that opens a panel below (or above) it. The panel closes when the user turns
// elsewhere: a press outside, Escape, the window losing the focus. Every pop-up menu is made with
// this, so none can forget to close. `alsoOpen`: something else belonging to the menu is open
// (a pop-up of its own), which a press outside closes as well (`close` tells the owner).
const open = defineModel<boolean>('open', { default: false })
const props = defineProps<{ panelClass?: string; right?: boolean; above?: boolean; alsoOpen?: boolean }>()
const emit = defineEmits<{ close: [] }>()
const root = ref<HTMLElement>()

function close(): void {
  open.value = false
  emit('close')
}

useDismiss(root, () => open.value || Boolean(props.alsoOpen), close)
</script>

<template>
  <div ref="root" class="relative">
    <slot name="trigger" :open="open" :toggle="() => (open = !open)" />
    <div
      v-if="open"
      class="card absolute z-40 shadow-xl"
      :class="[above ? 'bottom-full mb-1' : 'top-full mt-1', right ? 'right-0' : 'left-0', panelClass]"
    >
      <slot :close="close" />
    </div>
    <!-- Things that belong to the menu but are not its panel (pop-ups of their own, hidden inputs). -->
    <slot name="extra" />
  </div>
</template>
