<script setup lang="ts">
import { ref } from 'vue'
import { api, authenticated } from '../api'
import AppLogo from '../components/AppLogo.vue'
import { useToast } from '../composables/useToast'

const password = ref('')
const busy = ref(false)
const toast = useToast()

async function submit(): Promise<void> {
  busy.value = true
  try {
    await api.login(password.value)
    password.value = ''
    // Errors from failed attempts no longer apply once logged in.
    toast.clear()
    authenticated.value = true
  } catch (error) {
    toast.error(error)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="flex min-h-dvh items-center justify-center px-4">
    <form class="card w-full max-w-sm p-6" @submit.prevent="submit">
      <div class="mb-6 flex justify-center"><AppLogo /></div>
      <h1 class="mb-4 text-lg font-semibold">{{ $t('login.title') }}</h1>
      <label class="mb-1 block text-sm text-slate-400" for="password">{{ $t('login.password') }}</label>
      <input
        id="password"
        v-model="password"
        class="input mb-5"
        type="password"
        autocomplete="current-password"
        autofocus
      />
      <button type="submit" class="btn-primary w-full" :disabled="busy || !password">
        {{ $t('login.submit') }}
      </button>
    </form>
  </div>
</template>
