<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api, type DictationService } from '../../api'
import { hasBrowserRecognition } from '../../composables/useDictation'
import { useSettings } from '../../composables/useSettings'
import { useToast } from '../../composables/useToast'
import ToggleSwitch from '../ToggleSwitch.vue'

// The dictation. What recognises it (the STT-Suite or the browser) is chosen for this device; where the STT-Suite
// transcribes (CPU or GPU) and whether a dictation goes to the agent at once are the same on every device; what
// the STT-Suite uses is its own business and only shown.
const { dictationEngine, dictationDevice, dictationSendsAtOnce } = useSettings()
const toast = useToast()
// Whether an STT-Suite service is configured, and what it transcribes with; asked when the window opens.
const stt = ref(false)
const service = ref<DictationService | null>(null)
const usesService = computed(() => stt.value && dictationEngine.value === 'stt-suite')
onMounted(async () => {
  try {
    const settings = await api.dictationSettings()
    stt.value = settings.stt
    service.value = settings.service
  } catch (error) {
    toast.error(error)
  }
})
</script>

<template>
  <div>
    <!-- Offered with a service only: without one the browser listens anyway. Where the browser has no
         recognition of its own, "Browser" cannot be chosen. -->
    <div v-if="stt" class="text-sm text-soft">
      <div class="flex items-center justify-between gap-2">
        <span>{{ $t('settings.dictationEngine') }}</span>
        <div class="flex overflow-hidden rounded-md border border-line-strong text-xs">
          <button
            v-for="choice in (['stt-suite', 'browser'] as const)"
            :key="choice"
            class="px-2 py-1 disabled:opacity-40"
            :class="dictationEngine === choice ? 'segment-on' : 'text-dim'"
            :disabled="choice === 'browser' && !hasBrowserRecognition"
            @click="dictationEngine = choice"
          >
            {{ $t(`settings.dictationEngine_${choice}`) }}
          </button>
        </div>
      </div>
      <p class="mt-1 text-xs text-hint">{{ $t('settings.dictationEngineHint') }}</p>
      <p v-if="!hasBrowserRecognition" class="mt-1 text-xs text-hint">{{ $t('settings.dictationEngineMissing') }}</p>
    </div>
    <div v-if="usesService && service" class="mt-4 text-sm text-soft">
      <span>{{ $t('settings.dictationService') }}</span>
      <p class="mt-1 text-xs text-dim capitalize">
        {{ $t('settings.dictationServiceLine', service) }}
      </p>
      <p class="mt-1 text-xs text-hint">{{ $t('settings.dictationServiceHint') }}</p>
    </div>
    <!-- The dictation: where the STT-Suite transcribes (CPU or GPU) and whether it goes to the agent at once. -->
    <div class="mt-4 border-t border-line pt-3 text-sm text-soft">
      <div v-if="usesService && service" class="flex items-center justify-between gap-2">
        <span>{{ $t('settings.dictationDevice') }}</span>
        <div class="flex overflow-hidden rounded-md border border-line-strong text-xs">
          <button
            v-for="choice in (['cpu', 'cuda', 'auto'] as const)"
            :key="choice"
            class="px-2 py-1"
            :class="dictationDevice === choice ? 'segment-on' : 'text-dim'"
            @click="dictationDevice = choice"
          >
            {{ $t(`settings.dictationDevice_${choice}`) }}
          </button>
        </div>
      </div>
      <p v-if="usesService && service" class="mt-1 text-xs text-hint">{{ $t('settings.dictationDeviceHint') }}</p>
      <ToggleSwitch class="mt-2 h-7 text-soft" :checked="dictationSendsAtOnce" @click="dictationSendsAtOnce = !dictationSendsAtOnce">
        {{ $t('settings.dictationSendsAtOnce') }}
      </ToggleSwitch>
      <p class="mt-1 text-xs text-hint">{{ $t('settings.dictationSendsAtOnceHint') }}</p>
    </div>

  </div>
</template>
