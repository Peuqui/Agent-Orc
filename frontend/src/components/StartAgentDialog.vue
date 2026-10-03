<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { api, type Conversation } from '../api'
import { useSessions } from '../composables/useSessions'
import { useToast } from '../composables/useToast'
import { baseName, formatDate, formatSize } from '../format'
import BaseDialog from './BaseDialog.vue'

const props = defineProps<{ path: string }>()
const emit = defineEmits<{ started: []; close: [] }>()

const { profiles, loadProfiles, refresh } = useSessions()
const toast = useToast()
const selected = ref('')
// Empty string: the agent's own default effort.
const effort = ref('')
const busy = ref(false)
const conversations = ref<Conversation[]>([])
const MILLISECONDS_PER_SECOND = 1000
const { locale } = useI18n()

const effortLevels = computed(
  () => profiles.value.find((profile) => profile.name === selected.value)?.effort_levels ?? [],
)
// For the chosen agent: preselect the folder's stored effort, list earlier conversations.
watch(selected, async (profile) => {
  effort.value = ''
  conversations.value = []
  if (!profile) return
  try {
    effort.value = (await api.folderEffort(profile, props.path)).effort ?? ''
    conversations.value = await api.conversations(profile, props.path)
  } catch (error) {
    toast.error(error)
  }
})

onMounted(async () => {
  if (profiles.value.length === 0) await loadProfiles()
  selected.value = profiles.value[0]?.name ?? ''
})

async function start(resume: boolean, conversation: string | null = null): Promise<void> {
  busy.value = true
  try {
    await api.startSession(selected.value, props.path, resume, effort.value || null, conversation)
    await refresh()
    emit('started')
  } catch (error) {
    toast.error(error)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <BaseDialog :title="$t('agent.title', { name: baseName(path) })" @close="emit('close')">
    <fieldset class="mb-5 flex flex-col gap-2">
      <legend class="mb-2 text-sm text-slate-400">{{ $t('agent.profile') }}</legend>
      <label
        v-for="profile in profiles"
        :key="profile.name"
        class="flex min-h-11 cursor-pointer items-center gap-3 rounded-lg border px-3"
        :class="selected === profile.name ? 'border-red-500 bg-red-900/20' : 'border-slate-600'"
      >
        <input v-model="selected" type="radio" :value="profile.name" class="accent-red-500" />
        {{ profile.label }}
      </label>
    </fieldset>
    <label v-if="effortLevels.length" class="mb-5 block">
      <span class="mb-1 block text-sm text-slate-400">{{ $t('agent.effort') }}</span>
      <select v-model="effort" class="input">
        <option value="">{{ $t('agent.effortDefault') }}</option>
        <option v-for="level in effortLevels" :key="level" :value="level">{{ level }}</option>
      </select>
    </label>
    <div class="flex flex-col gap-2">
      <button class="btn-primary" :disabled="busy || !selected" @click="start(false)">
        {{ $t('agent.startNew') }}
      </button>
      <button class="btn-secondary" :disabled="busy || !selected" @click="start(true)">
        {{ $t('agent.resume') }}
      </button>
      <button class="btn" @click="emit('close')">{{ $t('common.cancel') }}</button>
    </div>
    <div v-if="conversations.length" class="mt-5 border-t border-slate-700 pt-4">
      <h3 class="mb-2 text-sm text-slate-400">{{ $t('agent.earlier') }}</h3>
      <ul class="flex max-h-64 flex-col gap-1 overflow-y-auto">
        <li v-for="conversation in conversations" :key="conversation.id">
          <button
            class="flex w-full flex-col items-start rounded-lg px-3 py-2 text-left hover:bg-slate-700"
            :disabled="busy"
            @click="start(true, conversation.id)"
          >
            <span class="w-full truncate text-sm text-slate-100">
              {{ conversation.title || $t('agent.untitled') }}
            </span>
            <span class="text-xs text-slate-500">
              {{ formatDate(new Date(conversation.modified * MILLISECONDS_PER_SECOND), locale) }}
              · {{ formatSize(conversation.size) }}
              <span v-if="conversation.recently_active" class="text-amber-400">
                · {{ $t('agent.recentlyActive') }}
              </span>
            </span>
          </button>
        </li>
      </ul>
    </div>
  </BaseDialog>
</template>
