<script setup lang="ts">
import { ref, watch } from 'vue'
import { api, type DictationService } from '../api'
import { useToast } from '../composables/useToast'
import { useI18n } from 'vue-i18n'
import {
  LINE_HEIGHT_STEP,
  TERMINAL_FONTS,
  type TerminalFont,
  MAX_LINE_HEIGHT,
  MAX_SCROLL_LINES,
  MIN_LINE_HEIGHT,
  MIN_SCROLL_LINES,
  useSettings,
} from '../composables/useSettings'
import AppIcon from './AppIcon.vue'
import DropdownMenu from './DropdownMenu.vue'
import HandoverSettings from './HandoverSettings.vue'
import KeysEditor from './KeysEditor.vue'
import PushSettings from './PushSettings.vue'
import SpeechSettings from './SpeechSettings.vue'
import { reloadToNewVersion } from '../update'

// Settings of this device; more entries join here as they become adjustable.
const { scrollLines, lineHeight, fontSize, stepFontSize, answersScale, stepAnswersScale, terminalFont } = useSettings()
const toast = useToast()
const open = ref(false)
// The extra-keys editor stays open after the menu has closed.
const editingKeys = ref(false)
// What the Whisper service transcribes with; asked when the menu opens.
const service = ref<DictationService | null>(null)

watch(open, async (isOpen) => {
  if (!isOpen) return
  try {
    service.value = (await api.dictationSettings()).service
  } catch (error) {
    toast.error(error)
  }
})
const FONT_NAMES: Record<TerminalFont, string> = { jetbrains: 'JetBrains Mono', system: 'System' }
const { locale } = useI18n()

function changeLineHeight(delta: number): void {
  // Rounded, so repeated steps do not drift (1.2000000000000002).
  const height = Math.round((lineHeight.value + delta) * 100) / 100
  lineHeight.value = Math.min(MAX_LINE_HEIGHT, Math.max(MIN_LINE_HEIGHT, height))
}

function changeScrollLines(delta: number): void {
  scrollLines.value = Math.min(MAX_SCROLL_LINES, Math.max(MIN_SCROLL_LINES, scrollLines.value + delta))
}
</script>

<template>
  <DropdownMenu v-model:open="open" right panel-class="w-64 p-3">
    <template #trigger="{ toggle }">
      <button class="btn-icon" :title="$t('settings.title')" :aria-label="$t('settings.title')" @click="toggle">
        <AppIcon name="menu" />
      </button>
    </template>
    <div>
      <h2 class="mb-2 text-sm font-semibold text-slate-200">{{ $t('settings.title') }}</h2>
      <div class="flex items-center justify-between gap-2 text-sm text-slate-300">
        <span>{{ $t('settings.font') }}</span>
        <div class="flex overflow-hidden rounded-md border border-slate-600 text-xs">
          <button
            v-for="(_family, font) in TERMINAL_FONTS"
            :key="font"
            class="px-2 py-1"
            :class="terminalFont === font ? 'bg-slate-600 text-slate-100' : 'text-slate-400'"
            @click="terminalFont = font"
          >
            {{ FONT_NAMES[font] }}
          </button>
        </div>
      </div>
      <div class="mt-3 flex items-center justify-between gap-2 text-sm text-slate-300">
        <span>{{ $t('settings.fontSize') }}</span>
        <div class="flex items-center gap-1">
          <button class="btn-icon size-7" :aria-label="$t('settings.less')" @click="stepFontSize(-1)">−</button>
          <span class="w-6 text-center tabular-nums">{{ fontSize }}</span>
          <button class="btn-icon size-7" :aria-label="$t('settings.more')" @click="stepFontSize(1)">+</button>
        </div>
      </div>
      <p class="mt-1 mb-3 text-xs text-slate-500">{{ $t('settings.fontSizeHint') }}</p>
      <div class="flex items-center justify-between gap-2 text-sm text-slate-300">
        <span>{{ $t('settings.answersScale') }}</span>
        <div class="flex items-center gap-1">
          <button class="btn-icon size-7" :aria-label="$t('settings.less')" @click="stepAnswersScale(-1)">−</button>
          <span class="w-11 text-center tabular-nums">{{ answersScale }} %</span>
          <button class="btn-icon size-7" :aria-label="$t('settings.more')" @click="stepAnswersScale(1)">+</button>
        </div>
      </div>
      <p class="mt-1 mb-3 text-xs text-slate-500">{{ $t('settings.answersScaleHint') }}</p>
      <div class="flex items-center justify-between gap-2 text-sm text-slate-300">
        <span>{{ $t('settings.scrollLines') }}</span>
        <div class="flex items-center gap-1">
          <button class="btn-icon size-7" :aria-label="$t('settings.less')" @click="changeScrollLines(-1)">−</button>
          <span class="w-6 text-center tabular-nums">{{ scrollLines }}</span>
          <button class="btn-icon size-7" :aria-label="$t('settings.more')" @click="changeScrollLines(1)">+</button>
        </div>
      </div>
      <p class="mt-1 text-xs text-slate-500">{{ $t('settings.scrollLinesHint') }}</p>
      <div class="mt-3 flex items-center justify-between gap-2 text-sm text-slate-300">
        <span>{{ $t('settings.lineHeight') }}</span>
        <div class="flex items-center gap-1">
          <button class="btn-icon size-7" :aria-label="$t('settings.less')" @click="changeLineHeight(-LINE_HEIGHT_STEP)">−</button>
          <span class="w-10 text-center tabular-nums">{{ lineHeight.toLocaleString(locale, { minimumFractionDigits: 2 }) }}</span>
          <button class="btn-icon size-7" :aria-label="$t('settings.more')" @click="changeLineHeight(LINE_HEIGHT_STEP)">+</button>
        </div>
      </div>
      <p class="mt-1 text-xs text-slate-500">{{ $t('settings.lineHeightHint') }}</p>
      <div v-if="service" class="mt-3 border-t border-slate-700 pt-3 text-sm text-slate-300">
        <span>{{ $t('settings.dictationService') }}</span>
        <p class="mt-1 text-xs text-slate-400 capitalize">
          {{ $t('settings.dictationServiceLine', service) }}
        </p>
        <p class="mt-1 text-xs text-slate-500">{{ $t('settings.dictationServiceHint') }}</p>
      </div>
      <button
        class="btn-secondary btn-small mt-3 w-full justify-center"
        @click="((editingKeys = true), (open = false))"
      >
        {{ $t('settings.keys') }}
      </button>
      <SpeechSettings />
      <PushSettings />
      <HandoverSettings />
      <button class="btn-secondary btn-small mt-3 w-full justify-center" @click="reloadToNewVersion">
        {{ $t('settings.reload') }}
      </button>
      <p class="mt-1 text-xs text-slate-500">{{ $t('settings.reloadHint') }}</p>
    </div>
    <template #extra><KeysEditor v-if="editingKeys" @close="editingKeys = false" /></template>
  </DropdownMenu>
</template>
