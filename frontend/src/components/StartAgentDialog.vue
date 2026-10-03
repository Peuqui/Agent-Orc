<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { api } from '../api'
import { useSessions } from '../composables/useSessions'
import { useToast } from '../composables/useToast'
import { baseName } from '../format'
import BaseDialog from './BaseDialog.vue'

const props = defineProps<{ path: string }>()
const emit = defineEmits<{ started: []; close: [] }>()

const { profiles, loadProfiles, refresh } = useSessions()
const toast = useToast()
const selected = ref('')
// Empty string: the agent's own default effort.
const effort = ref('')
const busy = ref(false)

const effortLevels = computed(
  () => profiles.value.find((profile) => profile.name === selected.value)?.effort_levels ?? [],
)
watch(selected, () => {
  effort.value = ''
})

onMounted(async () => {
  if (profiles.value.length === 0) await loadProfiles()
  selected.value = profiles.value[0]?.name ?? ''
})

async function start(resume: boolean): Promise<void> {
  busy.value = true
  try {
    await api.startSession(selected.value, props.path, resume, effort.value || null)
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
  </BaseDialog>
</template>
