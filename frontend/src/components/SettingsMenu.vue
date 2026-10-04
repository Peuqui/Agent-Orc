<script setup lang="ts">
import { ref, watch } from 'vue'
import { api } from '../api'
import { useToast } from '../composables/useToast'
import { useI18n } from 'vue-i18n'
import {
  LINE_HEIGHT_STEP,
  MAX_FONT_SIZE,
  MIN_FONT_SIZE,
  TERMINAL_FONTS,
  type TerminalFont,
  MAX_LINE_HEIGHT,
  MAX_SCROLL_LINES,
  MIN_LINE_HEIGHT,
  MIN_SCROLL_LINES,
  useSettings,
} from '../composables/useSettings'
import AppIcon from './AppIcon.vue'
import HandoverSettings from './HandoverSettings.vue'
import PushSettings from './PushSettings.vue'

// Settings of this device; more entries join here as they become adjustable.
const { scrollLines, lineHeight, fontSize, terminalFont, dictationEngine } = useSettings()
const toast = useToast()
const open = ref(false)
// The engines the Whisper service offers; asked when the menu opens.
const engines = ref<string[]>([])

watch(open, async (isOpen) => {
  if (!isOpen) return
  try {
    engines.value = (await api.dictationSettings()).engines
  } catch (error) {
    toast.error(error)
  }
})
const FONT_NAMES: Record<TerminalFont, string> = { jetbrains: 'JetBrains Mono', system: 'System' }
const { locale } = useI18n()

function changeFontSize(delta: number): void {
  fontSize.value = Math.min(MAX_FONT_SIZE, Math.max(MIN_FONT_SIZE, fontSize.value + delta))
}

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
  <div class="relative">
    <button class="btn-icon" :title="$t('settings.title')" :aria-label="$t('settings.title')" @click="open = !open">
      <AppIcon name="menu" />
    </button>
    <div v-if="open" class="card absolute top-full right-0 z-30 mt-1 w-64 p-3 shadow-xl">
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
          <button class="btn-icon size-7" :aria-label="$t('settings.less')" @click="changeFontSize(-1)">−</button>
          <span class="w-6 text-center tabular-nums">{{ fontSize }}</span>
          <button class="btn-icon size-7" :aria-label="$t('settings.more')" @click="changeFontSize(1)">+</button>
        </div>
      </div>
      <p class="mt-1 mb-3 text-xs text-slate-500">{{ $t('settings.fontSizeHint') }}</p>
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
      <div v-if="engines.length" class="mt-3 border-t border-slate-700 pt-3 text-sm text-slate-300">
        <span>{{ $t('settings.dictationEngine') }}</span>
        <!-- A row of its own: the service may offer more engines than fit beside the label. -->
        <div class="mt-1 flex overflow-hidden rounded-md border border-slate-600 text-xs">
          <button
            v-for="engine in ['', ...engines]"
            :key="engine"
            class="flex-1 px-2 py-1 capitalize"
            :class="dictationEngine === engine ? 'bg-slate-600 text-slate-100' : 'text-slate-400'"
            @click="dictationEngine = engine"
          >
            {{ engine === '' ? $t('settings.engineDefault') : engine }}
          </button>
        </div>
        <p class="mt-1 text-xs text-slate-500">{{ $t('settings.dictationEngineHint') }}</p>
      </div>
      <PushSettings />
      <HandoverSettings />
    </div>
  </div>
</template>
