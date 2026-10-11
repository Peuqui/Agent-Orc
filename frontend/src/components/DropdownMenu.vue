<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'
import { useDismiss } from '../composables/useDismiss'

// A button that opens a panel below (or above) it. The panel closes when the user turns
// elsewhere: a press outside, Escape, the window losing the focus. Every pop-up menu is made with
// this, so none can forget to close. `alsoOpen`: something else belonging to the menu is open
// (a pop-up of its own), which a press outside closes as well (`close` tells the owner).
// `above`: the panel prefers to open above, `right`: aligned with the button's right edge. Either way
// it opens on the side that has the room for it (the bottom bar and the header of the app take
// theirs; at the sides, the screen's edge), and scrolls when neither has enough.
const open = defineModel<boolean>('open', { default: false })
const props = defineProps<{ panelClass?: string; right?: boolean; above?: boolean; alsoOpen?: boolean }>()
const emit = defineEmits<{ close: [] }>()
const root = ref<HTMLElement>()
const panel = ref<HTMLElement>()
const opensAbove = ref(false)
const alignsRight = ref(false)
const maxHeight = ref<string>()

// What the panel keeps clear of at the screen's edge.
const SCREEN_MARGIN_PX = 8
const GAP_PX = 4

/** What the app's header or bottom bar covers (their heights are variables where they exist). */
function covered(variable: string): number {
  return parseFloat(getComputedStyle(document.documentElement).getPropertyValue(variable)) || 0
}

function place(): void {
  if (!root.value || !panel.value) return
  const trigger = root.value.getBoundingClientRect()
  const roomBelow = window.innerHeight - trigger.bottom - covered('--bottom-nav-height') - GAP_PX - SCREEN_MARGIN_PX
  const roomAbove = trigger.top - covered('--app-header-height') - GAP_PX - SCREEN_MARGIN_PX
  const needed = panel.value.scrollHeight
  const [preferred, other] = props.above ? [roomAbove, roomBelow] : [roomBelow, roomAbove]
  const onPreferred = preferred >= needed || preferred >= other
  opensAbove.value = onPreferred === Boolean(props.above)
  // Sideways the same: at the side asked for (`right`) unless the panel would stick out there and
  // does not at the other.
  const width = panel.value.offsetWidth
  const fitsLeftAligned = trigger.left + width <= window.innerWidth - SCREEN_MARGIN_PX
  const fitsRightAligned = trigger.right - width >= SCREEN_MARGIN_PX
  alignsRight.value = props.right ? fitsRightAligned || !fitsLeftAligned : !fitsLeftAligned && fitsRightAligned
  maxHeight.value = `${Math.max(0, onPreferred ? preferred : other)}px`
}

// Measured once the panel is drawn, before the browser paints it.
watch(open, async (isOpen) => {
  if (!isOpen) return
  maxHeight.value = undefined
  await nextTick()
  place()
})

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
      ref="panel"
      class="card absolute z-40 overflow-y-auto shadow-xl"
      :class="[opensAbove ? 'bottom-full mb-1' : 'top-full mt-1', alignsRight ? 'right-0' : 'left-0', panelClass]"
      :style="{ maxHeight }"
    >
      <slot :close="close" />
    </div>
    <!-- Things that belong to the menu but are not its panel (pop-ups of their own, hidden inputs). -->
    <slot name="extra" />
  </div>
</template>
