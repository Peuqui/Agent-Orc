<script setup lang="ts">
import { onBeforeUnmount, ref } from 'vue'
import { api, type TerminalKey } from '../api'
import { useReorder } from '../composables/useReorder'
import { useSettings } from '../composables/useSettings'
import { useToast } from '../composables/useToast'
import { KEY_CATALOG, keyFromEvent } from '../keyCatalog'
import BaseDialog from './BaseDialog.vue'

// The extra keys for every device: drag to arrange (also between rows), add ready-made keys,
// record a key combination or a text key (macro). Row 1 stays visible when the keys are folded,
// so new keys land there.
const emit = defineEmits<{ close: [] }>()
const toast = useToast()
const { extraKeysVersion } = useSettings()

interface EditedKey {
  uid: string
  key: TerminalKey
}
const ROW_END = 'end:'
let nextUid = 0
const rows = ref<EditedKey[][]>([])
const arranged = ref(false)
const recording = ref(false)
const macroLabel = ref('')
const macroText = ref('')
const macroSubmit = ref(true)

function edited(key: TerminalKey): EditedKey {
  nextUid += 1
  return { uid: String(nextUid), key }
}

api
  .terminalSettings()
  .then((settings) => {
    rows.value = settings.keys.map((row) => row.map(edited))
    arranged.value = settings.keys_arranged
  })
  .catch(toast.error)

function add(key: TerminalKey): void {
  if (rows.value.length === 0) rows.value.push([])
  rows.value[0].push(edited({ ...key }))
}

function remove(uid: string): void {
  rows.value = rows.value.map((row) => row.filter((item) => item.uid !== uid))
}

/** Move a key before the key target, or to the end of a row (target "end:<row>"). */
function move(uid: string, target: string): void {
  const moved = rows.value.flat().find((item) => item.uid === uid)
  if (!moved) return
  remove(uid)
  if (target.startsWith(ROW_END)) {
    rows.value[Number(target.slice(ROW_END.length))].push(moved)
    return
  }
  for (const row of rows.value) {
    const index = row.findIndex((item) => item.uid === target)
    if (index !== -1) row.splice(index, 0, moved)
  }
}

const reorder = useReorder({
  targetAt: (x, y) =>
    document
      .elementsFromPoint(x, y)
      .map((element) => element.closest<HTMLElement>('[data-key]')?.dataset.key)
      .find((key) => key !== undefined) ?? null,
  onDrop: (uid, target) => {
    if (uid !== target) move(uid, target)
  },
  ignore: '[data-no-drag]',
})
const drag = reorder.drag

// Recording: the next key combination pressed becomes a key (Esc included, so it is caught
// before the dialog would close on it).
function onRecordKey(event: KeyboardEvent): void {
  const key = keyFromEvent(event)
  if (key === null) return
  event.preventDefault()
  event.stopPropagation()
  add(key)
  stopRecording()
}

function startRecording(): void {
  recording.value = true
  window.addEventListener('keydown', onRecordKey, true)
}

function stopRecording(): void {
  recording.value = false
  window.removeEventListener('keydown', onRecordKey, true)
}
onBeforeUnmount(stopRecording)

function addMacro(): void {
  add({ label: macroLabel.value.trim(), send: macroText.value, modifier: null, submit: macroSubmit.value })
  macroLabel.value = ''
  macroText.value = ''
}

async function save(): Promise<void> {
  try {
    await api.arrangeKeys(rows.value.map((row) => row.map((item) => item.key)).filter((row) => row.length))
    extraKeysVersion.value += 1
    emit('close')
  } catch (error) {
    toast.error(error)
  }
}

async function reset(): Promise<void> {
  try {
    await api.resetKeys()
    extraKeysVersion.value += 1
    emit('close')
  } catch (error) {
    toast.error(error)
  }
}
</script>

<template>
  <BaseDialog :title="$t('keysEditor.title')" @close="emit('close')">
    <div class="flex max-h-[65dvh] flex-col gap-4 overflow-y-auto text-sm">
      <p class="text-xs text-slate-500">{{ $t('keysEditor.hint') }}</p>
      <div v-for="(row, index) in rows" :key="index" class="flex flex-col gap-1">
        <span class="text-xs text-slate-400">{{ $t('keysEditor.row', { number: index + 1 }) }}</span>
        <div class="flex flex-wrap items-center gap-1 rounded-lg border border-slate-700 p-1">
          <span
            v-for="item in row"
            :key="item.uid"
            :data-key="item.uid"
            class="flex cursor-grab touch-pan-y items-center gap-1 rounded-md bg-slate-800 py-1 pr-1 pl-2 select-none [-webkit-touch-callout:none]"
            :class="[
              item.key.submit ? 'text-amber-300' : 'text-slate-200',
              drag?.active && drag.target === item.uid && drag.id !== item.uid ? 'ring-2 ring-amber-400' : '',
              drag?.active && drag.id === item.uid ? 'opacity-50' : '',
            ]"
            :title="item.key.submit ? $t('keysEditor.macroTitle', { text: item.key.send }) : undefined"
            @pointerdown="reorder.onPointerDown($event, item.uid)"
            @pointermove="reorder.onPointerMove"
            @pointerup="reorder.onPointerUp"
            @pointercancel="reorder.cancel"
            @touchmove="reorder.onTouchMove"
            @contextmenu.prevent
          >
            {{ item.key.label }}
            <button
              data-no-drag
              class="px-1 text-slate-500 hover:text-slate-200"
              :aria-label="$t('keysEditor.remove')"
              @click="remove(item.uid)"
            >
              ×
            </button>
          </span>
          <!-- Dropped here, a key goes to the end of this row (also into an empty one). -->
          <span
            :data-key="`${ROW_END}${index}`"
            class="min-w-12 flex-1 rounded-md border border-dashed px-2 py-1 text-center text-xs text-slate-600"
            :class="drag?.active && drag.target === `${ROW_END}${index}` ? 'border-amber-400' : 'border-slate-700'"
          >
            {{ $t('keysEditor.rowEnd') }}
          </span>
        </div>
      </div>
      <button class="btn-secondary btn-small self-start" @click="rows.push([])">+ {{ $t('keysEditor.addRow') }}</button>

      <div class="flex flex-col gap-2 border-t border-slate-700 pt-3">
        <span class="font-medium text-slate-300">{{ $t('keysEditor.add') }}</span>
        <div v-for="group in KEY_CATALOG" :key="group.group" class="flex flex-wrap items-center gap-1">
          <span class="w-full text-xs text-slate-500">{{ $t(group.group) }}</span>
          <button
            v-for="key in group.keys"
            :key="key.label"
            class="rounded-md bg-slate-800 px-2 py-1 text-slate-200 hover:bg-slate-700"
            @click="add(key)"
          >
            {{ key.label }}
          </button>
        </div>
        <button class="btn-secondary btn-small self-start" :class="{ 'animate-pulse': recording }" @click="recording ? stopRecording() : startRecording()">
          {{ recording ? $t('keysEditor.recording') : $t('keysEditor.record') }}
        </button>
      </div>

      <form class="flex flex-col gap-2 border-t border-slate-700 pt-3" @submit.prevent="addMacro">
        <span class="font-medium text-slate-300">{{ $t('keysEditor.macro') }}</span>
        <p class="text-xs text-slate-500">{{ $t('keysEditor.macroHint') }}</p>
        <div class="flex gap-2">
          <input v-model="macroLabel" class="input w-24 text-sm" :placeholder="$t('keysEditor.macroLabel')" required />
          <input v-model="macroText" class="input min-w-0 flex-1 text-sm" :placeholder="$t('keysEditor.macroText')" required />
        </div>
        <label class="flex items-center gap-2 text-slate-300">
          <input v-model="macroSubmit" type="checkbox" class="size-4" />{{ $t('keysEditor.macroSubmit') }}
        </label>
        <button type="submit" class="btn-secondary btn-small self-start" :disabled="!macroLabel.trim() || !macroText">
          + {{ $t('keysEditor.macroAdd') }}
        </button>
      </form>
    </div>
    <div class="mt-4 flex flex-wrap gap-2">
      <button class="btn-primary flex-1" @click="save">{{ $t('common.save') }}</button>
      <button class="btn" @click="emit('close')">{{ $t('common.cancel') }}</button>
      <button v-if="arranged" class="btn-secondary w-full" @click="reset">{{ $t('keysEditor.reset') }}</button>
    </div>
  </BaseDialog>
</template>
