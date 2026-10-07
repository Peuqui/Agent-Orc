<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ApiError, NETWORK_ERROR, api, authenticated } from './api'
import AppHeader from './components/AppHeader.vue'
import ApprovalBanner from './components/ApprovalBanner.vue'
import BottomNav from './components/BottomNav.vue'
import AppIcon from './components/AppIcon.vue'
import ToastList from './components/ToastList.vue'
import UpdateBanner from './components/UpdateBanner.vue'
import { useSessions } from './composables/useSessions'
import { useToast } from './composables/useToast'
import LoginView from './views/LoginView.vue'

const { startPolling, stopPolling, loadProfiles } = useSessions()
const toast = useToast()
const route = useRoute()
const router = useRouter()
// A column of the workspace shows its agent's terminal in an iframe; pages opened from there
// (the project folder) get no app header or navigation, which would lead to a workspace inside
// the column, but a way back to the column's terminal.
const columnTab = window.self === window.top ? null : window.frameElement?.getAttribute('data-tab')

function backToTerminal(): void {
  if (columnTab) void router.push({ path: `/terminal/${encodeURIComponent(columnTab)}`, query: { embedded: null } })
}

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

// The full-screen views (workspace, terminal, ...) fill the screen and scroll inside; the page
// itself must not scroll. A page that did (the browser pans it to a focused field, and the
// offset stayed after the keyboard closed) lost its header at the top.
watch(
  () => Boolean(route.meta.fullscreen),
  (fullscreen) => document.documentElement.classList.toggle('app-shell', fullscreen),
  { immediate: true },
)

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
  <!-- A page per address path; the editor also per file (its query), so a link from one file to
       another loads the other instead of keeping the first. -->
  <RouterView v-else-if="authenticated && route.meta.fullscreen" v-slot="{ Component }">
    <component :is="Component" :key="route.meta.perQuery ? route.fullPath : route.path" />
  </RouterView>
  <div v-else-if="authenticated && columnTab" class="min-h-dvh">
    <header class="flex items-center gap-1 border-b border-slate-800 px-1 py-1">
      <button class="btn-icon" :aria-label="$t('app.backToTerminal')" @click="backToTerminal">
        <AppIcon name="up" class="-rotate-90" />
      </button>
      <span class="text-sm text-slate-300">{{ $t('app.backToTerminal') }}</span>
    </header>
    <main class="px-3 py-3">
      <RouterView />
    </main>
  </div>
  <div v-else-if="authenticated" class="min-h-dvh pb-20 lg:pb-4">
    <AppHeader />
    <main class="page-width py-4">
      <RouterView />
    </main>
    <BottomNav />
  </div>
  <ApprovalBanner v-if="authenticated" />
  <ToastList />
  <UpdateBanner />
</template>
