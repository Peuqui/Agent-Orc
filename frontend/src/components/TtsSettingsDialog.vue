<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { api, type TtsCatalogRow, type TtsChoices, type TtsEntry, type TtsTuning, type TtsUnit } from '../api'
import { useHosts } from '../composables/useHosts'
import { moveInList, useReorder } from '../composables/useReorder'
import { formatFactor, parseFactor } from '../format'
import { useToast } from '../composables/useToast'
import BaseDialog from './BaseDialog.vue'
import SelectMenu from './SelectMenu.vue'
import ToggleSwitch from './ToggleSwitch.vue'

// The engines of the TTS service for this Agent-Orc: drag to set the order they are tried in, switch
// them on or off, choose how much text each is given at once and a voice per engine (asked of the
// service). An engine on another machine is its own row. Kept on the server, as the server asks the
// service. An engine that fails is followed by the next one that is on.
const emit = defineEmits<{ close: [] }>()
const toast = useToast()
const { t, locale } = useI18n()
// This machine's own name (the engines of the service's own machine run here).
const { state: hostsState, loadHosts } = useHosts()
const own = computed(() => hostsState.value?.self ?? t('ttsSettings.thisMachine'))
loadHosts().catch(toast.error)

const UNITS: TtsUnit[] = ['sentence', 'paragraph', 'whole']
const choices = ref<TtsChoices>({ entries: [], voices: {}, tuning: {}, paragraph_pause_ms: 0, prefer_loaded: false })
const catalog = ref<TtsCatalogRow[]>([])
// The voices of each engine, asked when the window opens; an engine without any has no choice.
const voices = ref<Record<string, { id: string; label: string }[]>>({})
const loaded = ref(false)

/** One row of the list is an engine on a machine. */
const placeOf = (entry: { engine: string; host: string | null }): string => `${entry.engine}@${entry.host ?? ''}`

async function load(): Promise<void> {
  try {
    const [rows, chosen] = await Promise.all([api.ttsCatalog(), api.ttsChoices()])
    catalog.value = rows
    choices.value = chosen
    loaded.value = true
    const engines = [...new Set(chosen.entries.filter((entry) => entry.offered).map((entry) => entry.engine))]
    await Promise.all(
      engines.map(async (engine) => {
        // Added once they are there: the object is read after the wait, or answers that arrive
        // in between would be overwritten.
        const listed = await api.ttsVoices(engine)
        voices.value = { ...voices.value, [engine]: listed }
        // An engine speaks with a voice: the first one until another is chosen.
        if (!choices.value.voices[engine] && listed.length > 0) choices.value.voices[engine] = listed[0].id
      }),
    )
  } catch (error) {
    toast.error(error)
  }
}
void load()

/** Switched on, but the machine does not answer: the service skips it when speaking. */
const unreachable = (entry: TtsEntry): boolean =>
  entry.enabled &&
  entry.offered &&
  catalog.value.find((row) => placeOf(row) === placeOf(entry))?.status === 'unreachable'

const catalogRow = (entry: TtsEntry): TtsCatalogRow | undefined =>
  catalog.value.find((candidate) => placeOf(candidate) === placeOf(entry))

/** The short name of the engine; where it runs is in a line of its own (see `where`). */
function label(entry: TtsEntry): string {
  const row = catalogRow(entry)
  return row?.label_short[locale.value] ?? row?.label_short.en ?? entry.engine
}

/** Where the engine runs: in the cloud, on another machine, or on this one (named, so that two entries of an engine can be told apart). */
function where(entry: TtsEntry): string {
  if (catalogRow(entry)?.cloud) return t('ttsSettings.cloud')
  return entry.host ?? own.value
}

/** What is shown in the field of an engine's speed or pitch: the number the way the language writes it, or nothing. */
function tuningText(engine: string, field: 'speed' | 'pitch'): string {
  const value = choices.value.tuning[engine]?.[field]
  return value === null || value === undefined ? '' : formatFactor(value, locale.value)
}

/** Speed or pitch of an engine as typed (a comma counts as the decimal point). An empty field is "the service
 * decides" (null), and an engine with both empty has no entry; what is no number is refused and the field shows
 * what is kept. */
function setTuning(engine: string, field: 'speed' | 'pitch', input: HTMLInputElement): void {
  const parsed = parseFactor(input.value)
  if (Number.isNaN(parsed)) {
    toast.error(new Error(t('ttsSettings.notANumber')))
    input.value = tuningText(engine, field)
    return
  }
  const tuning: TtsTuning = choices.value.tuning[engine] ?? { speed: null, pitch: null }
  tuning[field] = parsed
  if (tuning.speed === null && tuning.pitch === null) delete choices.value.tuning[engine]
  else choices.value.tuning[engine] = tuning
  input.value = tuningText(engine, field)
}

const unitOptions = computed(() => UNITS.map((unit) => ({ value: unit, label: t(`ttsSettings.unit.${unit}`) })))

function voiceOptions(engine: string): { value: string; label: string }[] {
  return (voices.value[engine] ?? []).map((voice) => ({ value: voice.id, label: voice.label }))
}

const reorder = useReorder({
  targetAt: (x, y) =>
    document
      .elementsFromPoint(x, y)
      .map((element) => element.closest<HTMLElement>('[data-place]')?.dataset.place)
      .find((place) => place !== undefined) ?? null,
  onDrop: (place, target) => {
    const order = choices.value.entries.map(placeOf)
    moveInList(order, place, target)
    choices.value.entries = order.map((key) => choices.value.entries.find((entry) => placeOf(entry) === key) as TtsEntry)
  },
  ignore: '[data-no-drag]',
})
const drag = reorder.drag
const nothingOn = computed(() => loaded.value && !choices.value.entries.some((entry) => entry.enabled && entry.offered))

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
  <BaseDialog :title="$t('ttsSettings.title')" tall @close="emit('close')">
    <div class="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto text-sm">
      <p class="text-xs text-slate-500">{{ $t('ttsSettings.hint') }}</p>
      <div class="flex items-center justify-between gap-2" :title="$t('ttsSettings.preferLoadedHint')">
        <span>{{ $t('ttsSettings.preferLoaded') }}</span>
        <ToggleSwitch :checked="choices.prefer_loaded" @click="choices.prefer_loaded = !choices.prefer_loaded">
          <span class="sr-only">{{ $t('ttsSettings.preferLoaded') }}</span>
        </ToggleSwitch>
      </div>
      <label class="flex items-center justify-between gap-2">
        <span>{{ $t('ttsSettings.pause') }}</span>
        <input v-model.number="choices.paragraph_pause_ms" type="number" min="0" step="50" class="input w-24 text-right text-sm" />
      </label>
      <ul class="flex flex-col gap-1">
        <li
          v-for="entry in choices.entries"
          :key="placeOf(entry)"
          :data-place="placeOf(entry)"
          class="flex cursor-grab touch-pan-y flex-col gap-2 rounded-lg border border-slate-700 bg-slate-800/60 p-2 select-none [-webkit-touch-callout:none]"
          :class="[
            drag?.active && drag.target === placeOf(entry) && drag.id !== placeOf(entry) ? 'ring-2 ring-amber-400' : '',
            drag?.active && drag.id === placeOf(entry) ? 'opacity-50' : '',
          ]"
          @pointerdown="reorder.onPointerDown($event, placeOf(entry))"
          @pointermove="reorder.onPointerMove"
          @pointerup="reorder.onPointerUp"
          @pointercancel="reorder.cancel"
          @touchmove="reorder.onTouchMove"
          @contextmenu.prevent
        >
          <div class="flex items-center justify-between gap-2">
            <div class="min-w-0">
              <div class="truncate font-medium" :class="entry.enabled && entry.offered ? 'text-slate-200' : 'text-slate-500'">
                {{ label(entry) }}
              </div>
              <div class="truncate text-xs text-amber-400">{{ where(entry) }}</div>
            </div>
            <span v-if="unreachable(entry)" class="shrink-0 text-amber-400" :title="$t('ttsSettings.unreachable')" aria-hidden="false">⚠</span>
            <span v-if="!entry.offered" class="shrink-0 text-xs text-amber-400">{{ $t('ttsSettings.notOffered') }}</span>
            <ToggleSwitch v-else data-no-drag :checked="entry.enabled" @click="entry.enabled = !entry.enabled">
              <span class="sr-only">{{ $t('ttsSettings.on') }}</span>
            </ToggleSwitch>
          </div>
          <div data-no-drag class="flex flex-col gap-1">
            <SelectMenu v-model="entry.unit" :options="unitOptions" button-class="input text-sm text-slate-200" :aria-label="$t('ttsSettings.unitLabel')" />
            <SelectMenu
              v-if="(voices[entry.engine]?.length ?? 0) > 0"
              v-model="choices.voices[entry.engine]"
              :options="voiceOptions(entry.engine)"
              button-class="input text-sm text-slate-200"
              :aria-label="$t('ttsSettings.voiceLabel')"
            />
            <!-- Speed and pitch of the engine: empty leaves them to the service (what is set for the voice there). -->
            <div class="flex gap-2">
              <label class="flex min-w-0 flex-1 flex-col gap-0.5 text-xs text-slate-400">
                {{ $t('ttsSettings.speed') }}
                <input
                  type="text"
                  inputmode="decimal"
                  autocomplete="off"
                  class="input text-sm text-slate-200"
                  :placeholder="$t('ttsSettings.serviceValue')"
                  :value="tuningText(entry.engine, 'speed')"
                  @change="setTuning(entry.engine, 'speed', $event.target as HTMLInputElement)"
                />
              </label>
              <label class="flex min-w-0 flex-1 flex-col gap-0.5 text-xs text-slate-400">
                {{ $t('ttsSettings.pitch') }}
                <input
                  type="text"
                  inputmode="decimal"
                  autocomplete="off"
                  class="input text-sm text-slate-200"
                  :placeholder="$t('ttsSettings.serviceValue')"
                  :value="tuningText(entry.engine, 'pitch')"
                  @change="setTuning(entry.engine, 'pitch', $event.target as HTMLInputElement)"
                />
              </label>
            </div>
          </div>
        </li>
      </ul>
      <p v-if="!loaded" class="text-xs text-slate-500">{{ $t('ttsSettings.loading') }}</p>
      <p v-if="nothingOn" class="text-xs text-amber-400">{{ $t('ttsSettings.nothingOn') }}</p>
    </div>
    <div class="mt-4 flex shrink-0 gap-2">
      <button class="btn-primary flex-1" :disabled="!loaded" @click="save">{{ $t('common.save') }}</button>
      <button class="btn" @click="emit('close')">{{ $t('common.cancel') }}</button>
    </div>
  </BaseDialog>
</template>
