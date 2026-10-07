<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api, type ModelChoice } from '../api'
import { preferredModel, rememberModel } from '../composables/useModelChoice'
import { useToast } from '../composables/useToast'
import BaseDialog from './BaseDialog.vue'

// An agent cannot be started without a model: this asks for one where the agent has none stored
// (started before the choice existed), e.g. on restart or resume.
const props = defineProps<{ title: string; message: string; confirmLabel: string; profile: string; current?: string | null }>()
const emit = defineEmits<{ choose: [model: string]; close: [] }>()
const toast = useToast()
const models = ref<ModelChoice[]>([])
const model = ref<string | null>(null)

onMounted(async () => {
  try {
    models.value = await api.agentModels(props.profile)
    const offered = models.value.map((choice) => choice.name)
    model.value =
      props.current && offered.includes(props.current) ? props.current : preferredModel(props.profile, offered)
  } catch (error) {
    toast.error(error)
  }
})

function confirm(): void {
  if (model.value === null) return
  rememberModel(props.profile, model.value)
  emit('choose', model.value)
}
</script>

<template>
  <BaseDialog :title="title" @close="emit('close')">
    <p class="mb-4 text-slate-300">{{ message }}</p>
    <label class="mb-5 flex flex-col gap-1 text-sm text-slate-400">
      {{ $t('agent.model') }}
      <select v-model="model" class="input text-sm text-slate-200">
        <option v-for="choice in models" :key="choice.name" :value="choice.name">
          {{ choice.note ? `${choice.name} – ${choice.note}` : choice.name }}
        </option>
      </select>
    </label>
    <div class="flex justify-end gap-2">
      <button class="btn-secondary" @click="emit('close')">{{ $t('common.cancel') }}</button>
      <button class="btn-primary" :disabled="model === null" @click="confirm">{{ confirmLabel }}</button>
    </div>
  </BaseDialog>
</template>
