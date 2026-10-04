<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import messages from '../locales/de.json'
import AppIcon from './AppIcon.vue'

// Usage hints in one place, opened from a light bulb (as in AIfred). Every language has the
// same sections and hints; the German file gives their number, the current language the text.
const { t } = useI18n()
const open = ref(false)

const sections = computed(() =>
  messages.help.sections.map((section, sectionIndex) => ({
    title: t(`help.sections.${sectionIndex}.title`),
    items: section.items.map((_item, itemIndex) => t(`help.sections.${sectionIndex}.items.${itemIndex}`)),
  })),
)
</script>

<template>
  <button
    class="btn-icon text-amber-300 hover:text-amber-200"
    :title="$t('help.button')"
    :aria-label="$t('help.button')"
    @click="open = true"
  >
    <AppIcon name="lightbulb" />
  </button>
  <!-- In <body>: the blurred header would otherwise be the frame of the fixed dialog. -->
  <Teleport v-if="open" to="body">
    <div
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-2"
      data-modal
      @click.self="open = false"
      @keydown.esc="open = false"
    >
      <div
        class="flex max-h-[90dvh] w-full max-w-3xl flex-col rounded-xl border border-amber-300/40 bg-slate-900 shadow-2xl"
        role="dialog"
        :aria-label="$t('help.title')"
      >
        <div class="flex items-center gap-2 border-b border-slate-700 px-5 py-3">
          <AppIcon name="lightbulb" class="text-amber-300" />
          <h2 class="flex-1 font-semibold text-slate-100">{{ $t('help.title') }}</h2>
          <button class="btn-icon" :aria-label="$t('help.close')" @click="open = false">×</button>
        </div>
        <div class="min-h-0 flex-1 overflow-y-auto px-5 py-4">
          <section v-for="section in sections" :key="section.title" class="mb-5 last:mb-0">
            <h3 class="mb-2 flex items-center gap-2 text-sm font-semibold text-amber-300">
              <!-- Claude Code's orange star. -->
              <span class="text-base text-orange-400">✻</span>{{ section.title }}
            </h3>
            <ul class="flex flex-col gap-1.5 pl-6 text-sm leading-relaxed text-slate-300">
              <li v-for="item in section.items" :key="item" class="list-disc marker:text-slate-600">{{ item }}</li>
            </ul>
          </section>
        </div>
        <div class="flex justify-end border-t border-slate-700 px-5 py-3">
          <button class="btn-secondary" @click="open = false">{{ $t('help.close') }}</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>
