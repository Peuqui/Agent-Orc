<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useScope } from '../composables/useScope'
import { useToast } from '../composables/useToast'

// The folder where the file manager and new agents begin, on the machine whose app this is. It is
// confirmed with the password (it widens what the file manager reaches), unless the machine has
// no login (it is controlled over SSH).
const { scope, load, setBaseDir } = useScope()
const toast = useToast()
const { t } = useI18n()
const path = ref('')
const password = ref('')

onMounted(async () => {
  try {
    await load()
    path.value = scope.value?.base_dir ?? ''
  } catch (error) {
    toast.error(error)
  }
})

const changed = computed(() => path.value.trim() !== '' && path.value.trim() !== scope.value?.base_dir)

async function save(): Promise<void> {
  try {
    await setBaseDir(path.value.trim(), password.value)
    password.value = ''
    toast.info(t('settings.baseDirSaved'))
  } catch (error) {
    toast.error(error)
  }
}
</script>

<template>
  <form v-if="scope" class="mt-3 border-t border-slate-700 pt-3 text-sm text-slate-300" @submit.prevent="save">
    <label for="base-dir">{{ $t('settings.baseDir') }}</label>
    <input id="base-dir" v-model="path" class="input mt-1 w-full text-xs" spellcheck="false" autocomplete="off" />
    <input
      v-if="scope.password_required"
      v-model="password"
      type="password"
      class="input mt-1 w-full text-xs"
      autocomplete="current-password"
      :placeholder="$t('login.password')"
      :aria-label="$t('login.password')"
    />
    <button type="submit" class="btn-secondary btn-small mt-2 w-full justify-center" :disabled="!changed">
      {{ $t('common.save') }}
    </button>
    <p class="mt-1 text-xs text-slate-500">{{ $t('settings.baseDirHint') }}</p>
  </form>
</template>
