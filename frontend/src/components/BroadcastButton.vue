<script setup lang="ts">
import { computed, ref } from 'vue'
import { useSessions } from '../composables/useSessions'
import AppIcon from './AppIcon.vue'
import BroadcastDialog from './BroadcastDialog.vue'

const { sessions } = useSessions()
const open = ref(false)
const running = computed(() => sessions.value.filter((session) => session.running))
</script>

<template>
  <button v-if="running.length > 1" class="btn-secondary btn-small" @click="open = true">
    <AppIcon name="broadcast" />{{ $t('broadcast.button') }}
  </button>
  <BroadcastDialog v-if="open" @close="open = false" />
</template>
