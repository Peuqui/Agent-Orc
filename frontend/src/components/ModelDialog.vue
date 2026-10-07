<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { api, type AgentChoice, type ModelChoice } from '../api'
import { preferredModel, rememberModel } from '../composables/useModelChoice'
import { useSessions } from '../composables/useSessions'
import { useToast } from '../composables/useToast'
import BaseDialog from './BaseDialog.vue'

// Asks for a model (an agent cannot be started without one), where the agent has none stored
// (started before the choice existed), e.g. on restart or resume. With `chooseProfile` the agent
// can be another one too (a local model, Codex, ...): it is then started in its place.
const props = defineProps<{
  title: string
  message: string
  confirmLabel: string
  profile: string
  current?: string | null
  chooseProfile?: boolean
}>()
const emit = defineEmits<{ choose: [choice: AgentChoice]; close: [] }>()
const toast = useToast()
const { profiles } = useSessions()
const chosenProfile = ref(props.profile)
const models = ref<ModelChoice[]>([])
const model = ref<string | null>(null)

const currentProfile = computed(() => profiles.value.find((p) => p.name === props.profile))
const targetProfile = computed(() => profiles.value.find((p) => p.name === chosenProfile.value))
// A terminal stays a terminal, an agent an agent.
const agentChoices = computed(() => profiles.value.filter((p) => p.terminal === currentProfile.value?.terminal))
const switching = computed(() => chosenProfile.value !== props.profile)
const offersModels = computed(() => targetProfile.value?.models === true)
// The conversation goes on if both keep their conversations in the same place.
const carriesConversation = computed(
  () =>
    currentProfile.value?.conversations != null &&
    currentProfile.value.conversations === targetProfile.value?.conversations,
)

async function loadModels(): Promise<void> {
  models.value = []
  model.value = null
  if (!offersModels.value) return
  try {
    models.value = await api.agentModels(chosenProfile.value)
    const offered = models.value.map((choice) => choice.name)
    model.value =
      !switching.value && props.current && offered.includes(props.current)
        ? props.current
        : preferredModel(chosenProfile.value, offered)
  } catch (error) {
    toast.error(error)
  }
}

// Nothing to ask for: a model is needed where there is a choice, and without a choice of agent
// (or with the same one and no models) there is nothing to change.
const confirmable = computed(() =>
  offersModels.value ? model.value !== null : !props.chooseProfile || switching.value,
)

watch([chosenProfile, offersModels], loadModels, { immediate: true })

function confirm(): void {
  if (!confirmable.value) return
  if (model.value !== null) rememberModel(chosenProfile.value, model.value)
  emit('choose', { profile: chosenProfile.value, model: model.value })
}
</script>

<template>
  <BaseDialog :title="title" @close="emit('close')">
    <p v-if="!switching" class="mb-4 text-slate-300">{{ message }}</p>
    <label v-if="chooseProfile && agentChoices.length > 1" class="mb-4 flex flex-col gap-1 text-sm text-slate-400">
      {{ $t('agent.profile') }}
      <select v-model="chosenProfile" class="input text-sm text-slate-200">
        <option v-for="choice in agentChoices" :key="choice.name" :value="choice.name">{{ choice.label }}</option>
      </select>
    </label>
    <p
      v-if="switching"
      class="mb-4 rounded-md border border-amber-700 bg-amber-950/40 px-3 py-2 text-sm text-amber-200"
    >
      {{ $t(carriesConversation ? 'restart.profileCarries' : 'restart.profileFresh', { agent: targetProfile?.label }) }}
    </p>
    <label v-if="offersModels" class="mb-5 flex flex-col gap-1 text-sm text-slate-400">
      {{ $t('agent.model') }}
      <select v-model="model" class="input text-sm text-slate-200">
        <option v-for="choice in models" :key="choice.name" :value="choice.name">
          {{ choice.note ? `${choice.name} – ${choice.note}` : choice.name }}
        </option>
      </select>
    </label>
    <div class="flex justify-end gap-2">
      <button class="btn-secondary" @click="emit('close')">{{ $t('common.cancel') }}</button>
      <button class="btn-primary" :disabled="!confirmable" @click="confirm">{{ confirmLabel }}</button>
    </div>
  </BaseDialog>
</template>
