<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { Reasoning } from '../api'

// Reasoning of an agent: the effort as a slider (first stop: the agent's own default, then
// the profile's levels from fast to smart; chosen on release) and, where the agent offers it,
// the ultracode switch next to it.
const props = defineProps<{
  levels: string[]
  ultracodeOffered: boolean
  modelValue: Reasoning
  disabled?: boolean
}>()
const emit = defineEmits<{ 'update:modelValue': [reasoning: Reasoning] }>()

const stops = computed<(string | null)[]>(() => [null, ...props.levels])
const position = ref(0)

watch(
  () => [props.modelValue.effort, props.levels] as const,
  () => {
    position.value = Math.max(0, stops.value.indexOf(props.modelValue.effort))
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

function toggleUltracode(): void {
  emit('update:modelValue', { ...props.modelValue, ultracode: !props.modelValue.ultracode })
}
</script>

<template>
  <div class="flex items-end gap-4">
    <div class="flex min-w-0 flex-1 flex-col gap-1">
      <div class="flex items-baseline gap-2 text-sm">
        <span class="text-slate-400">{{ $t('agent.effort') }}</span>
        <span class="font-medium text-slate-100">{{ effort ?? $t('agent.effortDefaultShort') }}</span>
      </div>
      <div class="flex justify-between text-xs text-slate-500">
        <span>{{ $t('agent.faster') }}</span>
        <span>{{ $t('agent.smarter') }}</span>
      </div>
      <div class="relative flex h-9 items-center">
        <!-- The track with one dot per stop is drawn here; the native slider only adds the knob. -->
        <div
          class="pointer-events-none absolute inset-x-0 flex h-2 items-center justify-between rounded-full bg-slate-700 px-3"
          :class="{ 'opacity-50': disabled }"
        >
          <span v-for="(_stop, index) in stops" :key="index" class="size-1 rounded-full bg-slate-400" />
        </div>
        <input
          type="range"
          class="effort-slider relative h-9 w-full cursor-pointer appearance-none bg-transparent disabled:cursor-not-allowed disabled:opacity-50"
          min="0"
          :max="stops.length - 1"
          step="1"
          :value="position"
          :disabled="disabled"
          :aria-label="$t('agent.effort')"
          :aria-valuetext="effort ?? $t('agent.effortDefaultShort')"
          @input="onInput"
          @change="onChange"
        />
      </div>
    </div>
    <button
      v-if="ultracodeOffered"
      type="button"
      role="switch"
      class="flex h-9 shrink-0 items-center gap-2 text-sm text-slate-300 disabled:opacity-50"
      :aria-checked="modelValue.ultracode"
      :disabled="disabled"
      :title="$t('agent.ultracodeHint')"
      @click="toggleUltracode"
    >
      {{ $t('agent.ultracode') }}
      <span
        class="relative h-6 w-11 rounded-full transition-colors"
        :class="modelValue.ultracode ? 'bg-red-500' : 'bg-slate-600'"
      >
        <span
          class="absolute top-0.5 size-5 rounded-full bg-white transition-all"
          :class="modelValue.ultracode ? 'left-5.5' : 'left-0.5'"
        />
      </span>
    </button>
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
  width: 1.5rem;
  height: 1.5rem;
  border-radius: 9999px;
  background: var(--color-slate-100);
  box-shadow: 0 0 0 3px var(--color-red-500);
}
.effort-slider::-moz-range-thumb {
  width: 1.5rem;
  height: 1.5rem;
  border: none;
  border-radius: 9999px;
  background: var(--color-slate-100);
  box-shadow: 0 0 0 3px var(--color-red-500);
}
</style>
