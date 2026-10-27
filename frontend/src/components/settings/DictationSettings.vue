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
    <!-- Offered with a service only: without one the browser listens anyway. Also on a device without the
         browser's recognition, so the STT-Suite can be chosen again from there. -->
    <div v-if="stt" class="text-sm text-slate-300">
      <div class="flex items-center justify-between gap-2">
        <span>{{ $t('settings.dictationEngine') }}</span>
        <div class="flex overflow-hidden rounded-md border border-slate-600 text-xs">
          <button
            v-for="choice in (['stt-suite', 'browser'] as const)"
            :key="choice"
            class="px-2 py-1"
            :class="dictationEngine === choice ? 'segment-on' : 'text-slate-400'"
            @click="dictationEngine = choice"
          >
            {{ $t(`settings.dictationEngine_${choice}`) }}
          </button>
        </div>
      </div>
      <p class="mt-1 text-xs text-slate-500">{{ $t('settings.dictationEngineHint') }}</p>
      <p v-if="dictationEngine === 'browser' && !hasBrowserRecognition" class="mt-1 text-xs text-amber-300">
        {{ $t('settings.dictationEngineMissing') }}
      </p>
    </div>
    <div v-if="usesService && service" class="mt-4 text-sm text-slate-300">
      <span>{{ $t('settings.dictationService') }}</span>
      <p class="mt-1 text-xs text-slate-400 capitalize">
        {{ $t('settings.dictationServiceLine', service) }}
      </p>
      <p class="mt-1 text-xs text-slate-500">{{ $t('settings.dictationServiceHint') }}</p>
    </div>
    <!-- The dictation: where the STT-Suite transcribes (CPU or GPU) and whether it goes to the agent at once. -->
    <div class="mt-4 border-t border-slate-700 pt-3 text-sm text-slate-300">
      <div v-if="usesService && service" class="flex items-center justify-between gap-2">
        <span>{{ $t('settings.dictationDevice') }}</span>
        <div class="flex overflow-hidden rounded-md border border-slate-600 text-xs">
          <button
            v-for="choice in (['cpu', 'cuda', 'auto'] as const)"
            :key="choice"
            class="px-2 py-1"
            :class="dictationDevice === choice ? 'segment-on' : 'text-slate-400'"
            @click="dictationDevice = choice"
          >
            {{ $t(`settings.dictationDevice_${choice}`) }}
          </button>
        </div>
      </div>
      <p v-if="usesService && service" class="mt-1 text-xs text-slate-500">{{ $t('settings.dictationDeviceHint') }}</p>
      <ToggleSwitch class="mt-2 h-7 text-slate-300" :checked="dictationSendsAtOnce" @click="dictationSendsAtOnce = !dictationSendsAtOnce">
        {{ $t('settings.dictationSendsAtOnce') }}
      </ToggleSwitch>
      <p class="mt-1 text-xs text-slate-500">{{ $t('settings.dictationSendsAtOnceHint') }}</p>
    </div>

  </div>
</template>
