<script setup lang="ts">
import BaseDialog from './BaseDialog.vue'

defineProps<{ title: string; message: string; confirmLabel: string; danger?: boolean }>()
const emit = defineEmits<{ confirm: []; close: [] }>()
</script>

<template>
  <BaseDialog :title="title" @close="emit('close')">
    <p class="mb-5 text-slate-300">{{ message }}</p>
    <div class="flex justify-end gap-2">
      <button class="btn-secondary" @click="emit('close')">{{ $t('common.cancel') }}</button>
      <button :class="danger ? 'btn-danger' : 'btn-primary'" @click="emit('confirm')">
        {{ confirmLabel }}
      </button>
    </div>
  </BaseDialog>
</template>
