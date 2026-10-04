<script setup lang="ts">
import { ref } from 'vue'
import { api, type PromptTemplate } from '../api'
import { useToast } from '../composables/useToast'
import AppIcon from './AppIcon.vue'
import BaseDialog from './BaseDialog.vue'

// Prompts used again and again, kept on the server: a tap puts one into the input field (not
// sent yet, so it can be completed); "manage" adds, edits and removes them. Opened from the
// attach menu, so it takes no room of its own in the input row.
const emit = defineEmits<{ insert: [text: string] }>()
const toast = useToast()
const open = ref(false)
const templates = ref<PromptTemplate[]>([])
const editing = ref<PromptTemplate[] | null>(null)

async function show(): Promise<void> {
  open.value = true
  try {
    templates.value = await api.promptTemplates()
  } catch (error) {
    toast.error(error)
  }
}

function use(template: PromptTemplate): void {
  open.value = false
  emit('insert', template.text)
}

function manage(): void {
  open.value = false
  editing.value = templates.value.map((template) => ({ ...template }))
}

defineExpose({ show })

async function save(): Promise<void> {
  if (!editing.value) return
  const kept = editing.value.filter((template) => template.label.trim() && template.text.trim())
  try {
    await api.storePromptTemplates(kept)
    templates.value = kept
    editing.value = null
  } catch (error) {
    toast.error(error)
  }
}
</script>

<template>
  <div>
    <div v-if="open" class="card absolute bottom-full left-0 z-30 mb-1 flex w-72 flex-col p-1 shadow-xl">
      <button
        v-for="template in templates"
        :key="template.label"
        type="button"
        class="flex flex-col items-start rounded-md px-3 py-2 text-left hover:bg-slate-700"
        @click="use(template)"
      >
        <span class="text-sm text-slate-100">{{ template.label }}</span>
        <span class="line-clamp-1 text-xs text-slate-500">{{ template.text }}</span>
      </button>
      <p v-if="templates.length === 0" class="px-3 py-2 text-sm text-slate-500">{{ $t('templates.none') }}</p>
      <button type="button" class="btn-secondary btn-small mt-1" @click="manage">
        <AppIcon name="pencil" />{{ $t('templates.manage') }}
      </button>
    </div>
    <BaseDialog v-if="editing" :title="$t('templates.manage')" @close="editing = null">
      <div class="flex max-h-[60dvh] flex-col gap-3 overflow-y-auto">
        <div v-for="(template, index) in editing" :key="index" class="flex flex-col gap-1 rounded-lg border border-slate-700 p-2">
          <div class="flex items-center gap-2">
            <input v-model="template.label" class="input min-w-0 flex-1 text-sm" :placeholder="$t('templates.label')" />
            <button type="button" class="btn-icon size-8" :aria-label="$t('templates.remove')" @click="editing.splice(index, 1)">×</button>
          </div>
          <textarea v-model="template.text" rows="3" class="input text-sm" :placeholder="$t('templates.text')" />
        </div>
        <button type="button" class="btn-secondary btn-small self-start" @click="editing.push({ label: '', text: '' })">
          <AppIcon name="plus" />{{ $t('templates.add') }}
        </button>
      </div>
      <div class="mt-4 flex gap-2">
        <button class="btn-primary flex-1" @click="save">{{ $t('common.save') }}</button>
        <button class="btn" @click="editing = null">{{ $t('common.cancel') }}</button>
      </div>
    </BaseDialog>
  </div>
</template>
