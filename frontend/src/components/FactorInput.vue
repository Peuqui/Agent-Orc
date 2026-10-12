<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useToast } from '../composables/useToast'
import { formatFactor, parseFactor } from '../format'

// A field for a speed or a pitch (a decimal number above 0, 1 = unchanged): typed with a comma or a point, shown the
// way the language writes it (1,15 in German, 1.15 in English). Empty means "not set" (null); the grey placeholder
// says what applies then. What is no number is refused and the field shows what is kept.
const props = defineProps<{ modelValue: number | null; placeholder: string }>()
const emit = defineEmits<{ 'update:modelValue': [value: number | null] }>()
const { t, locale } = useI18n()
const toast = useToast()
const shown = computed(() => (props.modelValue === null ? '' : formatFactor(props.modelValue, locale.value)))

function leave(event: Event): void {
  const input = event.target as HTMLInputElement
  const parsed = parseFactor(input.value)
  if (Number.isNaN(parsed)) {
    toast.error(new Error(t('factor.notANumber')))
    input.value = shown.value
    return
  }
  emit('update:modelValue', parsed)
  input.value = parsed === null ? '' : formatFactor(parsed, locale.value)
}
</script>

<template>
  <input
    type="text"
    inputmode="decimal"
    autocomplete="off"
    class="input text-sm text-slate-200"
    :value="shown"
    :placeholder="placeholder"
    @change="leave"
  />
</template>
