<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { Reasoning } from '../api'
import ToggleSwitch from './ToggleSwitch.vue'

// Reasoning of an agent: the effort as a slider (the profile's levels from fast to smart;
// chosen on release) and, where the agent offers it, the ultracode switch next to it.
const props = defineProps<{
  levels: string[]
  ultracodeOffered: boolean
  modelValue: Reasoning
  disabled?: boolean
  /** On the card: a dropdown instead of the slider. */
  compact?: boolean
}>()
const emit = defineEmits<{ 'update:modelValue': [reasoning: Reasoning] }>()

const stops = computed(() => props.levels)
const position = ref(0)

watch(
  () => [props.modelValue.effort, props.levels] as const,
  () => {
    // Unknown (null) until a running agent reports its level: the first stop then.
    const { effort } = props.modelValue
    position.value = effort === null ? 0 : Math.max(0, stops.value.indexOf(effort))
  },
  { immediate: true },
)

const effort = computed(() => stops.value[position.value])

function onInput(event: Event): void {
  position.value = Number((event.target as HTMLInputElement).value)
}

function onChange(): void {
  if (effort.value !== props.modelValue.effort) {
    emit('update:modelValue', { ...props.modelValue, effort: effort.value })
  }
}

function onSelect(event: Event): void {
  const chosen = (event.target as HTMLSelectElement).value
  if (chosen !== props.modelValue.effort) emit('update:modelValue', { ...props.modelValue, effort: chosen })
}

function toggleUltracode(): void {
  emit('update:modelValue', { ...props.modelValue, ultracode: !props.modelValue.ultracode })
}
</script>

<template>
  <div class="flex" :class="compact ? 'items-center gap-x-3' : 'items-end gap-x-4'">
    <!-- On the card: a dropdown, which a swipe over the card cannot change by accident (a slider
         is easily caught) and which takes less room. -->
    <select
      v-if="compact"
      class="h-7 rounded-lg border border-slate-600 bg-slate-800 pr-1 pl-1.5 text-xs text-slate-200 disabled:opacity-50"
      :value="effort"
      :disabled="disabled"
      :aria-label="$t('agent.effort')"
      :title="$t('agent.effort')"
      @change="onSelect"
    >
      <option v-for="stop in stops" :key="stop" :value="stop">{{ stop }}</option>
    </select>
    <div v-else class="flex min-w-0 flex-1 flex-col gap-y-1">
      <div class="flex shrink-0 items-baseline gap-2 text-sm">
        <span class="text-slate-400">{{ $t('agent.effort') }}</span>
        <span class="font-medium text-slate-100">{{ effort }}</span>
      </div>
      <div class="flex justify-between text-xs text-slate-500">
        <span>{{ $t('agent.faster') }}</span>
        <span>{{ $t('agent.smarter') }}</span>
      </div>
      <div class="relative flex h-9 min-w-20 flex-1 items-center">
        <!-- The track with one dot per stop is drawn here; the native slider only adds the knob. -->
        <div
          class="pointer-events-none absolute inset-x-0 flex h-1.5 items-center justify-between rounded-full bg-slate-700 px-[7px]"
          :class="{ 'opacity-50': disabled }"
        >
          <span v-for="(_stop, index) in stops" :key="index" class="size-1 rounded-full bg-slate-400" />
        </div>
        <input
          type="range"
          class="effort-slider relative h-full w-full cursor-pointer appearance-none bg-transparent disabled:cursor-not-allowed disabled:opacity-50"
          min="0"
          :max="stops.length - 1"
          step="1"
          :value="position"
          :disabled="disabled"
          :aria-label="$t('agent.effort')"
          :aria-valuetext="effort"
          @input="onInput"
          @change="onChange"
        />
      </div>
    </div>
    <ToggleSwitch
      v-if="ultracodeOffered"
      class="text-slate-300"
      :class="compact ? 'h-7 text-xs' : 'h-9 text-sm'"
      :checked="modelValue.ultracode"
      :disabled="disabled"
      :title="$t('agent.ultracodeHint')"
      @click="toggleUltracode"
    >
      {{ $t('agent.ultracode') }}
    </ToggleSwitch>
  </div>
</template>

<style scoped>
/* Only the knob of the native slider is shown; the track is drawn underneath. */
.effort-slider::-webkit-slider-runnable-track {
  background: transparent;
}
.effort-slider::-moz-range-track {
  background: transparent;
}
.effort-slider::-webkit-slider-thumb {
  appearance: none;
  /* 14 px: the dots of the track are inset by half of it (px-[7px]). */
  width: 14px;
  height: 14px;
  border-radius: 9999px;
  background: var(--color-slate-100);
  box-shadow: 0 0 0 2px var(--color-red-500);
}
.effort-slider::-moz-range-thumb {
  width: 14px;
  height: 14px;
  border: none;
  border-radius: 9999px;
  background: var(--color-slate-100);
  box-shadow: 0 0 0 2px var(--color-red-500);
}
</style>
