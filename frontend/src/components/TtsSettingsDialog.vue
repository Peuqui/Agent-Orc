<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { api, type TtsChoice, type TtsEngine } from '../api'
import { moveInList, useReorder } from '../composables/useReorder'
import { useToast } from '../composables/useToast'
import BaseDialog from './BaseDialog.vue'
import SelectMenu from './SelectMenu.vue'
import ToggleSwitch from './ToggleSwitch.vue'

// The engines of the TTS service for this Agent-Orc: drag to set the order they are tried in, switch
// them on or off, and choose a voice for each (asked of the service). Kept on the server, as the
// server asks the service. An engine that fails is followed by the next one that is on.
const emit = defineEmits<{ close: [] }>()
const toast = useToast()
const { locale } = useI18n()

const choices = ref<TtsChoice[]>([])
const engines = ref<Record<string, TtsEngine>>({})
// The voices of each engine, asked when the window opens; an engine without any has no choice.
const voices = ref<Record<string, { id: string; label: string }[]>>({})
const loaded = ref(false)

async function load(): Promise<void> {
  try {
    const [offered, chosen] = await Promise.all([api.ttsEngines(), api.ttsChoices()])
    engines.value = Object.fromEntries(offered.map((engine) => [engine.engine, engine]))
    choices.value = chosen.engines
    loaded.value = true
    await Promise.all(
      choices.value.map(async (choice) => {
        // Added once they are there: the object is read after the wait, or answers that arrive
        // in between would be overwritten.
        const listed = await api.ttsVoices(choice.engine)
        voices.value = { ...voices.value, [choice.engine]: listed }
        // An engine speaks with a voice: the first one until another is chosen.
        if (choice.voice === '' && listed.length > 0) choice.voice = listed[0].id
      }),
    )
  } catch (error) {
    toast.error(error)
  }
}
void load()

function label(engine: string): string {
  const names = engines.value[engine]?.label
  return names?.[locale.value] ?? names?.en ?? engine
}

function voiceOptions(engine: string): { value: string; label: string }[] {
  return (voices.value[engine] ?? []).map((voice) => ({ value: voice.id, label: voice.label }))
}

const reorder = useReorder({
  targetAt: (x, y) =>
    document
      .elementsFromPoint(x, y)
      .map((element) => element.closest<HTMLElement>('[data-engine]')?.dataset.engine)
      .find((engine) => engine !== undefined) ?? null,
  onDrop: (engine, target) => {
    const order = choices.value.map((choice) => choice.engine)
    moveInList(order, engine, target)
    choices.value = order.map((key) => choices.value.find((choice) => choice.engine === key) as TtsChoice)
  },
  ignore: '[data-no-drag]',
})
const drag = reorder.drag
const nothingOn = computed(() => loaded.value && !choices.value.some((choice) => choice.enabled))

async function save(): Promise<void> {
  try {
    await api.storeTtsChoices(choices.value)
    emit('close')
  } catch (error) {
    toast.error(error)
  }
}
</script>

<template>
  <BaseDialog :title="$t('ttsSettings.title')" @close="emit('close')">
    <div class="flex max-h-[65dvh] flex-col gap-3 overflow-y-auto text-sm">
      <p class="text-xs text-slate-500">{{ $t('ttsSettings.hint') }}</p>
      <ul class="flex flex-col gap-1">
        <li
          v-for="choice in choices"
          :key="choice.engine"
          :data-engine="choice.engine"
          class="flex cursor-grab touch-pan-y flex-col gap-2 rounded-lg border border-slate-700 bg-slate-800/60 p-2 select-none [-webkit-touch-callout:none]"
          :class="[
            drag?.active && drag.target === choice.engine && drag.id !== choice.engine ? 'ring-2 ring-amber-400' : '',
            drag?.active && drag.id === choice.engine ? 'opacity-50' : '',
          ]"
          @pointerdown="reorder.onPointerDown($event, choice.engine)"
          @pointermove="reorder.onPointerMove"
          @pointerup="reorder.onPointerUp"
          @pointercancel="reorder.cancel"
          @touchmove="reorder.onTouchMove"
          @contextmenu.prevent
        >
          <div class="flex items-center justify-between gap-2">
            <span class="min-w-0 truncate font-medium" :class="choice.enabled ? 'text-slate-200' : 'text-slate-500'">
              {{ label(choice.engine) }}
            </span>
            <ToggleSwitch data-no-drag :checked="choice.enabled" @click="choice.enabled = !choice.enabled">
              <span class="sr-only">{{ $t('ttsSettings.on') }}</span>
            </ToggleSwitch>
          </div>
          <div v-if="(voices[choice.engine]?.length ?? 0) > 0" data-no-drag>
            <SelectMenu v-model="choice.voice" :options="voiceOptions(choice.engine)" button-class="input text-sm text-slate-200" />
          </div>
        </li>
      </ul>
      <p v-if="!loaded" class="text-xs text-slate-500">{{ $t('ttsSettings.loading') }}</p>
      <p v-if="nothingOn" class="text-xs text-amber-400">{{ $t('ttsSettings.nothingOn') }}</p>
    </div>
    <div class="mt-4 flex gap-2">
      <button class="btn-primary flex-1" :disabled="!loaded" @click="save">{{ $t('common.save') }}</button>
      <button class="btn" @click="emit('close')">{{ $t('common.cancel') }}</button>
    </div>
  </BaseDialog>
</template>
