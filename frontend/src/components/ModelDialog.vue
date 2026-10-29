<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { type AgentChoice, type ModelChoice, type Reasoning } from '../api'
import { nearestLevel } from '../effort'
import { modelOptions, preferredModel, rememberModel, useModelNote } from '../composables/useModelChoice'
import { useSessions } from '../composables/useSessions'
import { useApi } from '../composables/useHostContext'
import { useToast } from '../composables/useToast'
import BaseDialog from './BaseDialog.vue'
import ReasoningControl from './ReasoningControl.vue'
import SelectMenu from './SelectMenu.vue'

// Asks for a model (an agent cannot be started without one), where the agent has none stored
// (started before the choice existed), e.g. on restart or resume. With `chooseProfile` the agent
// can be another one too (a local model, Codex, ...): it is then started in its place. The level
// of reasoning is offered for the chosen model, as it takes different ones (`currentEffort` is
// the wish it starts from).
const props = defineProps<{
  title: string
  message: string
  confirmLabel: string
  profile: string
  current?: string | null
  currentEffort?: string | null
  chooseProfile?: boolean
}>()
const emit = defineEmits<{ choose: [choice: AgentChoice]; close: [] }>()
const toast = useToast()
const modelNote = useModelNote()
const api = useApi()
const { profiles } = useSessions()
const chosenProfile = ref(props.profile)
const models = ref<ModelChoice[]>([])
const model = ref<string | null>(null)
const levels = ref<string[]>([])
// The level last wished for: kept while the user flips through models, so the preselection moves
// to the nearest one each model takes.
const wantedEffort = ref<string | null>(props.currentEffort ?? null)
const reasoning = ref<Reasoning>({ effort: null, ultracode: false })

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

// The level goes with the model: an agent that restarts needs one the new model takes, one that
// switches in place can be given another at the same time (or keep the model and change only it).
const asksEffort = computed(() => levels.value.length > 0)

async function loadLevels(): Promise<void> {
  const profile = targetProfile.value
  if (!profile) return
  try {
    levels.value = profile.models
      ? model.value === null
        ? []
        : await api.agentLevels(profile.name, model.value)
      : profile.effort_levels
  } catch (error) {
    toast.error(error)
    levels.value = []
  }
  reasoning.value = {
    effort: nearestLevel(wantedEffort.value, levels.value, profile.effort_levels),
    ultracode: false,
  }
}

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
const confirmable = computed(
  () =>
    (offersModels.value ? model.value !== null : !props.chooseProfile || switching.value) &&
    (!asksEffort.value || reasoning.value.effort !== null),
)

watch([chosenProfile, offersModels], loadModels, { immediate: true })
watch([targetProfile, model], loadLevels, { immediate: true })
watch(
  () => reasoning.value.effort,
  (effort) => {
    if (effort !== null) wantedEffort.value = effort
  },
)

function confirm(): void {
  if (!confirmable.value) return
  if (model.value !== null) rememberModel(chosenProfile.value, model.value)
  emit('choose', {
    profile: chosenProfile.value,
    model: model.value,
    effort: asksEffort.value ? reasoning.value.effort : null,
  })
}
</script>

<template>
  <BaseDialog :title="title" @close="emit('close')">
    <p v-if="!switching" class="mb-4 text-soft">{{ message }}</p>
    <label v-if="chooseProfile && agentChoices.length > 1" class="mb-4 flex flex-col gap-1 text-sm text-dim">
      {{ $t('agent.profile') }}
      <SelectMenu
        v-model="chosenProfile"
        :options="agentChoices.map((choice) => ({ value: choice.name, label: choice.label }))"
        button-class="input text-sm text-main"
      />
    </label>
    <p
      v-if="switching"
      class="mb-4 rounded-md border border-highlight-700 bg-highlight-950/40 px-3 py-2 text-sm text-highlight-200"
    >
      {{ $t(carriesConversation ? 'restart.profileCarries' : 'restart.profileFresh', { agent: targetProfile?.label }) }}
    </p>
    <label v-if="offersModels" class="mb-5 flex flex-col gap-1 text-sm text-dim">
      {{ $t('agent.model') }}
      <SelectMenu v-model="model" :options="modelOptions(models, modelNote)" button-class="input text-sm text-main" />
    </label>
    <ReasoningControl v-if="asksEffort" v-model="reasoning" :levels="levels" :ultracode-offered="false" class="mb-5" />
    <div class="flex justify-end gap-2">
      <button class="btn-secondary" @click="emit('close')">{{ $t('common.cancel') }}</button>
      <button class="btn-primary" :disabled="!confirmable" @click="confirm">{{ confirmLabel }}</button>
    </div>
  </BaseDialog>
</template>
