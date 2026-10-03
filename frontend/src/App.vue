<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ApiError, NETWORK_ERROR, api, authenticated } from './api'
import AppHeader from './components/AppHeader.vue'
import BottomNav from './components/BottomNav.vue'
import ToastList from './components/ToastList.vue'
import { useSessions } from './composables/useSessions'
import { useToast } from './composables/useToast'
import LoginView from './views/LoginView.vue'

const { startPolling, stopPolling, loadProfiles } = useSessions()
const toast = useToast()
const route = useRoute()

const unreachable = ref(false)

async function checkLogin(): Promise<void> {
  unreachable.value = false
  try {
    await api.me()
    authenticated.value = true
  } catch (error) {
    if (error instanceof ApiError && error.code === NETWORK_ERROR) unreachable.value = true
    // A 401 already switched to the login view; anything else is a real problem.
    else if (!(error instanceof ApiError && error.status === 401)) toast.error(error)
  }
}

onMounted(checkLogin)

watch(authenticated, (isAuthenticated) => {
  if (isAuthenticated) {
    startPolling()
    loadProfiles().catch(toast.error)
  } else {
    stopPolling()
  }
})
</script>

<template>
  <div v-if="unreachable" class="flex min-h-dvh flex-col items-center justify-center gap-4 px-4">
    <p class="text-slate-300">{{ $t('errors.NetworkError') }}</p>
    <button class="btn-primary" @click="checkLogin">{{ $t('app.retry') }}</button>
  </div>
  <LoginView v-else-if="authenticated === false" />
  <RouterView v-else-if="authenticated && route.meta.fullscreen" />
  <div v-else-if="authenticated" class="min-h-dvh pb-20 md:pb-4">
    <AppHeader />
    <main class="mx-auto max-w-5xl px-4 py-4">
      <RouterView />
    </main>
    <BottomNav />
  </div>
  <ToastList />
</template>
