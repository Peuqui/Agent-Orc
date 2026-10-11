<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { MODAL_ATTRIBUTE, useDismiss } from '../composables/useDismiss'
import AppIcon from './AppIcon.vue'

// The one way to choose from a list, wherever a form or a bar asks for it: a button that opens
// the list right at itself, the same on a phone and on a computer (the browser's own <select>
// opens the system's picker on a phone, which looks different from every other menu here). The
// list opens below, above where there is more room, and scrolls when it is longer than the room.
export interface SelectOption {
  value: string
  label: string
  disabled?: boolean
}

const props = defineProps<{
  /** Null: nothing chosen yet (an agent that has not reported its mode). */
  modelValue: string | null
  options: SelectOption[]
  /** The look of the button: the same classes a <select> had there. */
  buttonClass?: string
  disabled?: boolean
  ariaLabel?: string
  title?: string
}>()
const emit = defineEmits<{ 'update:modelValue': [value: string] }>()

// The gap between button and list, and the margin the list keeps to the screen's edge.
const GAP_PX = 4
const SCREEN_MARGIN_PX = 8
// With less room than this below, the list opens above if that has more room.
const MIN_ROOM_PX = 160

const open = ref(false)
const root = ref<HTMLElement>()
const button = ref<HTMLButtonElement>()
const panel = ref<HTMLElement>()
const placement = ref<Record<string, string>>({})

const chosen = computed(() => props.options.find((option) => option.value === props.modelValue))

function place(): void {
  const box = button.value!.getBoundingClientRect()
  const roomBelow = window.innerHeight - box.bottom - GAP_PX - SCREEN_MARGIN_PX
  const roomAbove = box.top - GAP_PX - SCREEN_MARGIN_PX
  const below = roomBelow >= MIN_ROOM_PX || roomBelow >= roomAbove
  // A button in the right half grows its list to the left, so it stays on the screen.
  const toTheRight = box.left + box.width / 2 > window.innerWidth / 2
  placement.value = {
    position: 'fixed',
    minWidth: `${box.width}px`,
    maxWidth: `${window.innerWidth - 2 * SCREEN_MARGIN_PX}px`,
    maxHeight: `${below ? roomBelow : roomAbove}px`,
    ...(below ? { top: `${box.bottom + GAP_PX}px` } : { bottom: `${window.innerHeight - box.top + GAP_PX}px` }),
    ...(toTheRight ? { right: `${window.innerWidth - box.right}px` } : { left: `${box.left}px` }),
  }
}

function close(): void {
  open.value = false
}

async function toggle(): Promise<void> {
  if (open.value) return close()
  place()
  open.value = true
  await nextTick()
  const selected = panel.value?.querySelector<HTMLElement>('[aria-selected="true"]')
  const first = panel.value?.querySelector<HTMLElement>('button:not(:disabled)')
  ;(selected ?? first)?.focus()
}

function choose(option: SelectOption): void {
  close()
  button.value?.focus()
  if (option.value !== props.modelValue) emit('update:modelValue', option.value)
}

function onPanelKey(event: KeyboardEvent): void {
  if (event.key === 'Escape') {
    event.stopPropagation()
    close()
    button.value?.focus()
    return
  }
  const entries = [...(panel.value?.querySelectorAll<HTMLElement>('button:not(:disabled)') ?? [])]
  const at = entries.indexOf(document.activeElement as HTMLElement)
  const target = { ArrowDown: at + 1, ArrowUp: at - 1, Home: 0, End: entries.length - 1 }[event.key]
  if (target === undefined) return
  event.preventDefault()
  entries[Math.min(entries.length - 1, Math.max(0, target))]?.focus()
}

// The list is drawn into <body> (a dialog or a scrolling menu around the button would cut it), so
// a press in it is marked as inside a modal: it must not count as a press outside (useDismiss).
useDismiss(root, () => open.value, close)

// A list that sits at a place which moved (the page scrolled, the window changed) would hang in
// the air: it closes then.
function onMoved(event: Event): void {
  if (!(event.target instanceof Node) || !panel.value?.contains(event.target)) close()
}
watch(open, (isOpen) => {
  const method = isOpen ? 'addEventListener' : 'removeEventListener'
  window[method]('resize', close)
  window[method]('scroll', onMoved, true)
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', close)
  window.removeEventListener('scroll', onMoved, true)
})
</script>

<template>
  <div ref="root" class="min-w-0">
    <button
      ref="button"
      type="button"
      class="flex w-full min-w-0 items-center justify-between gap-1 text-left disabled:opacity-50"
      :class="buttonClass"
      :disabled="disabled"
      :aria-label="ariaLabel"
      :title="title"
      aria-haspopup="listbox"
      :aria-expanded="open"
      @click="toggle"
    >
      <span class="min-w-0 truncate">{{ chosen?.label ?? '' }}</span>
      <AppIcon name="chevron" class="size-4 text-slate-400" />
    </button>
    <Teleport to="body">
      <div
        v-if="open"
        ref="panel"
        :[MODAL_ATTRIBUTE]="''"
        role="listbox"
        class="card z-[70] flex flex-col overflow-y-auto p-1 shadow-xl"
        :style="placement"
        @keydown="onPanelKey"
      >
        <button
          v-for="option in options"
          :key="option.value"
          type="button"
          role="option"
          :aria-selected="option.value === modelValue"
          :disabled="option.disabled"
          class="rounded-md px-3 py-2 text-left text-sm hover:bg-slate-700 focus:bg-slate-700 focus:outline-none disabled:text-slate-500 disabled:hover:bg-transparent"
          :class="option.value === modelValue ? 'text-amber-300' : 'text-slate-200'"
          @click="choose(option)"
        >
          {{ option.label }}
        </button>
      </div>
    </Teleport>
  </div>
</template>
