<script setup lang="ts">
import { onMounted, ref } from 'vue'
import BaseDialog from './BaseDialog.vue'

const props = defineProps<{
  title: string
  label: string
  submitLabel: string
  initialValue?: string
  password?: boolean
  hint?: string
}>()
const emit = defineEmits<{ submit: [value: string]; close: [] }>()

const value = ref(props.initialValue ?? '')
const field = ref<HTMLInputElement>()

onMounted(() => field.value?.focus())
</script>

<template>
  <BaseDialog :title="title" @close="emit('close')">
    <form @submit.prevent="value && emit('submit', value)">
      <p v-if="hint" class="mb-4 text-sm text-slate-400">{{ hint }}</p>
      <label class="mb-1 block text-sm text-slate-400" for="dialog-input">{{ label }}</label>
      <input
        id="dialog-input"
        ref="field"
        v-model="value"
        class="input mb-5"
        :type="password ? 'password' : 'text'"
        :autocomplete="password ? 'current-password' : 'off'"
        autocapitalize="off"
        spellcheck="false"
      />
      <div class="flex justify-end gap-2">
        <button type="button" class="btn-secondary" @click="emit('close')">
          {{ $t('common.cancel') }}
        </button>
        <button type="submit" class="btn-primary" :disabled="!value">{{ submitLabel }}</button>
      </div>
    </form>
  </BaseDialog>
</template>
