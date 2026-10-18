<script setup lang="ts">
import { type Component, ref } from 'vue'
import AppIcon from './AppIcon.vue'
import BaseDialog from './BaseDialog.vue'
import BaseDirSettings from './BaseDirSettings.vue'
import DropdownMenu from './DropdownMenu.vue'
import HandoverSettings from './HandoverSettings.vue'
import KeepWarmSettings from './KeepWarmSettings.vue'
import KeysEditor from './KeysEditor.vue'
import PushSettings from './PushSettings.vue'
import SpeechSettings from './SpeechSettings.vue'
import TtsSettingsDialog from './TtsSettingsDialog.vue'
import { reloadToNewVersion } from '../update'
import DictationSettings from './settings/DictationSettings.vue'
import DisplaySettings from './settings/DisplaySettings.vue'

// The menu is a short list; each entry opens a window of its own, right below the menu button. What a
// window holds is set at once, there is no button to save it (the project folder, which asks for a
// password, has its own).
const SECTIONS = [
  { id: 'display', component: DisplaySettings },
  { id: 'dictation', component: DictationSettings },
  { id: 'speech', component: SpeechSettings },
  { id: 'baseDir', component: BaseDirSettings },
  { id: 'push', component: PushSettings },
  { id: 'handover', component: HandoverSettings },
  { id: 'keepWarm', component: KeepWarmSettings },
] as const satisfies readonly { id: string; component: Component }[]
type SectionId = (typeof SECTIONS)[number]['id']

const open = ref(false)
const section = ref<SectionId | null>(null)
// Where the menu button is: the windows open beside it, whichever entry was pressed.
const menuButton = ref<HTMLElement>()
const near = ref<DOMRect | null>(null)
// The windows that open from inside another one (the extra keys, the engines of the TTS service) take its
// place: the section closes.
const editingKeys = ref(false)
const editingTts = ref(false)

function choose(id: SectionId): void {
  near.value = menuButton.value?.getBoundingClientRect() ?? null
  section.value = id
  open.value = false
}

function openKeys(): void {
  section.value = null
  editingKeys.value = true
}

function openTts(): void {
  section.value = null
  editingTts.value = true
}
</script>

<template>
  <DropdownMenu v-model:open="open" right panel-class="w-60 overscroll-contain p-2">
    <template #trigger="{ toggle }">
      <button ref="menuButton" class="btn-icon" :title="$t('settings.title')" :aria-label="$t('settings.title')" @click="toggle">
        <AppIcon name="menu" />
      </button>
    </template>
    <div class="flex flex-col">
      <h2 class="px-2 pt-1 pb-2 text-sm font-semibold text-amber-400">{{ $t('settings.title') }}</h2>
      <button
        v-for="entry in SECTIONS"
        :key="entry.id"
        class="rounded-md px-2 py-2 text-left text-sm text-slate-200 hover:bg-slate-700"
        @click="choose(entry.id)"
      >
        {{ $t(`settings.sections.${entry.id}`) }}
      </button>
      <!-- Not a window of its own: it is one press. -->
      <button class="btn-secondary btn-small mx-2 mt-2 justify-center" :title="$t('settings.reloadHint')" @click="reloadToNewVersion">
        {{ $t('settings.reload') }}
      </button>
    </div>
    <template #extra>
      <BaseDialog v-if="section" :near="near" :title="$t(`settings.sections.${section}`)" @close="section = null">
        <DisplaySettings v-if="section === 'display'" @keys="openKeys" />
        <DictationSettings v-else-if="section === 'dictation'" />
        <SpeechSettings v-else-if="section === 'speech'" @configure="openTts" />
        <BaseDirSettings v-else-if="section === 'baseDir'" />
        <PushSettings v-else-if="section === 'push'" />
        <HandoverSettings v-else-if="section === 'handover'" />
        <KeepWarmSettings v-else-if="section === 'keepWarm'" />
      </BaseDialog>
      <KeysEditor v-if="editingKeys" @close="editingKeys = false" />
      <TtsSettingsDialog v-if="editingTts" @close="editingTts = false" />
    </template>
  </DropdownMenu>
</template>
