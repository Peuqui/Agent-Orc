<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import messages from '../locales/de.json'
import AppIcon from './AppIcon.vue'

// Usage hints in one place, opened from a light bulb (as in AIfred). Every language has the
// same sections and hints; the German file gives their number, the current language the text.
const { t } = useI18n()
// `bare`: no button of its own, something else opens the dialog (v-model:open).
defineProps<{ bare?: boolean }>()
const open = defineModel<boolean>('open', { default: false })

// A hint may begin with its term in **double asterisks**; the term is set apart in amber.
function splitTerm(text: string): { term: string; rest: string } {
  const match = /^\*\*(.+?)\*\*/.exec(text)
  return match ? { term: match[1], rest: text.slice(match[0].length) } : { term: '', rest: text }
}

const body = ref<HTMLElement>()
// Sections whose entries are unfolded in the table of contents.
const unfolded = ref(new Set<number>())

function toggle(index: number): void {
  if (!unfolded.value.delete(index)) unfolded.value.add(index)
}

function jumpToTop(): void {
  body.value?.scrollTo({ top: 0, behavior: 'smooth' })
}

// Section `2` or hint `2-5` (section and position within it).
function jumpTo(anchor: string): void {
  body.value?.querySelector(`[data-anchor="${anchor}"]`)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

const sections = computed(() =>
  messages.help.sections.map((section, sectionIndex) => ({
    title: t(`help.sections.${sectionIndex}.title`),
    items: section.items.map((_item, itemIndex) => splitTerm(t(`help.sections.${sectionIndex}.items.${itemIndex}`))),
  })),
)
</script>

<template>
  <button
    v-if="!bare"
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
          <button class="btn-icon" :title="$t('help.toContents')" :aria-label="$t('help.toContents')" @click="jumpToTop">
            <AppIcon name="up" />
          </button>
          <button class="btn-icon" :aria-label="$t('help.close')" @click="open = false">×</button>
        </div>
        <div ref="body" class="min-h-0 flex-1 overflow-y-auto px-5 py-4">
          <nav class="mb-5 rounded-lg border border-amber-300/30 px-3 py-2" :aria-label="$t('help.contents')">
            <h3 class="mb-1 text-sm font-semibold text-red-400">{{ $t('help.contents') }}</h3>
            <ol class="flex flex-col text-sm">
              <li v-for="(section, index) in sections" :key="section.title">
                <div class="flex items-center">
                  <button
                    class="btn-icon text-amber-300"
                    :aria-expanded="unfolded.has(index)"
                    :aria-label="section.title"
                    @click="toggle(index)"
                  >
                    <AppIcon name="up" class="size-4 transition-transform" :class="unfolded.has(index) ? 'rotate-180' : 'rotate-90'" />
                  </button>
                  <button class="flex-1 py-1 text-left font-medium text-amber-300 hover:text-amber-200" @click="jumpTo(`${index}`)">
                    {{ section.title }}
                  </button>
                </div>
                <ul v-if="unfolded.has(index)" class="mb-1 flex flex-col pl-9">
                  <template v-for="(item, itemIndex) in section.items" :key="itemIndex">
                    <li v-if="item.term">
                      <button class="w-full py-0.5 text-left text-slate-300 hover:text-amber-300" @click="jumpTo(`${index}-${itemIndex}`)">
                        {{ item.term }}
                      </button>
                    </li>
                  </template>
                </ul>
              </li>
            </ol>
          </nav>
          <section v-for="(section, index) in sections" :key="section.title" :data-anchor="index" class="mb-5 last:mb-0">
            <h3 class="mb-2 flex items-center gap-2 text-sm font-semibold text-amber-300">
              <!-- Claude Code's orange star. -->
              <span class="text-base text-orange-400">✻</span>{{ section.title }}
            </h3>
            <ul class="flex flex-col gap-1.5 pl-6 text-sm leading-relaxed text-slate-300">
              <li v-for="(item, itemIndex) in section.items" :key="itemIndex" :data-anchor="`${index}-${itemIndex}`" class="list-disc marker:text-amber-300">
                <span v-if="item.term" class="font-medium text-amber-300">{{ item.term }}</span>{{ item.rest }}
              </li>
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
