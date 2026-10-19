<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import {
  LINE_HEIGHT_STEP,
  MAX_LINE_HEIGHT,
  MAX_SCROLL_LINES,
  MIN_LINE_HEIGHT,
  MIN_SCROLL_LINES,
  TERMINAL_FONTS,
  type TerminalFont,
  useSettings,
} from '../../composables/useSettings'

// What depends on the device itself (its screen, its mouse or finger), kept in the browser: the fonts, the
// scrolling, the line spacing; and the arrangement of the extra keys (its editor opens from here).
defineEmits<{ keys: [] }>()
const { scrollLines, lineHeight, fontSize, stepFontSize, viewFontSize, stepViewFontSize, controlsScale, stepControlsScale, terminalFont } = useSettings()
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
  <div>
    <div class="flex items-center justify-between gap-2 text-sm text-slate-300">
      <span>{{ $t('settings.font') }}</span>
      <div class="flex overflow-hidden rounded-md border border-slate-600 text-xs">
        <button
          v-for="(_family, font) in TERMINAL_FONTS"
          :key="font"
          class="px-2 py-1"
          :class="terminalFont === font ? 'segment-on' : 'text-slate-400'"
          @click="terminalFont = font"
        >
          {{ FONT_NAMES[font] }}
        </button>
      </div>
    </div>
    <div class="mt-4 flex items-center justify-between gap-2 text-sm text-slate-300">
      <span>{{ $t('settings.fontSize') }}</span>
      <div class="flex items-center gap-1">
        <button class="btn-icon size-7" :aria-label="$t('settings.less')" @click="stepFontSize(-1)">A−</button>
        <span class="w-12 text-center tabular-nums">{{ fontSize }} px</span>
        <button class="btn-icon size-7" :aria-label="$t('settings.more')" @click="stepFontSize(1)">A+</button>
      </div>
    </div>
    <p class="mt-1 mb-3 text-xs text-slate-500">{{ $t('settings.fontSizeHint') }}</p>
    <div class="flex items-center justify-between gap-2 text-sm text-slate-300">
      <span>{{ $t('settings.viewFontSize') }}</span>
      <div class="flex items-center gap-1">
        <button class="btn-icon size-7" :aria-label="$t('settings.less')" @click="stepViewFontSize(-1)">A−</button>
        <span class="w-12 text-center tabular-nums">{{ viewFontSize }} px</span>
        <button class="btn-icon size-7" :aria-label="$t('settings.more')" @click="stepViewFontSize(1)">A+</button>
      </div>
    </div>
    <p class="mt-1 mb-3 text-xs text-slate-500">{{ $t('settings.viewFontSizeHint') }}</p>
    <div class="flex items-center justify-between gap-2 text-sm text-slate-300">
      <span>{{ $t('settings.controlsScale') }}</span>
      <div class="flex items-center gap-1">
        <button class="btn-icon size-7" :aria-label="$t('settings.less')" @click="stepControlsScale(-1)">A−</button>
        <span class="w-12 text-center tabular-nums">{{ controlsScale }} %</span>
        <button class="btn-icon size-7" :aria-label="$t('settings.more')" @click="stepControlsScale(1)">A+</button>
      </div>
    </div>
    <p class="mt-1 mb-3 text-xs text-slate-500">{{ $t('settings.controlsScaleHint') }}</p>
    <div class="flex items-center justify-between gap-2 text-sm text-slate-300">
      <span>{{ $t('settings.scrollLines') }}</span>
      <div class="flex items-center gap-1">
        <button class="btn-icon size-7" :aria-label="$t('settings.less')" @click="changeScrollLines(-1)">−</button>
        <span class="w-6 text-center tabular-nums">{{ scrollLines }}</span>
        <button class="btn-icon size-7" :aria-label="$t('settings.more')" @click="changeScrollLines(1)">+</button>
      </div>
    </div>
    <p class="mt-1 text-xs text-slate-500">{{ $t('settings.scrollLinesHint') }}</p>
    <div class="mt-4 flex items-center justify-between gap-2 text-sm text-slate-300">
      <span>{{ $t('settings.lineHeight') }}</span>
      <div class="flex items-center gap-1">
        <button class="btn-icon size-7" :aria-label="$t('settings.less')" @click="changeLineHeight(-LINE_HEIGHT_STEP)">−</button>
        <span class="w-10 text-center tabular-nums">{{ lineHeight.toLocaleString(locale, { minimumFractionDigits: 2 }) }}</span>
        <button class="btn-icon size-7" :aria-label="$t('settings.more')" @click="changeLineHeight(LINE_HEIGHT_STEP)">+</button>
      </div>
    </div>
    <p class="mt-1 text-xs text-slate-500">{{ $t('settings.lineHeightHint') }}</p>

    <button class="btn-secondary btn-small mt-4 w-full justify-center" @click="$emit('keys')">
      {{ $t('settings.keys') }}
    </button>
  </div>
</template>
