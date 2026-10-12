<script setup lang="ts">
import { reloadToNewVersion } from '../../update'
</script>

<template>
  <div>
    <button class="btn-secondary btn-small w-full justify-center" @click="reloadToNewVersion">
      {{ $t('settings.reload') }}
    </button>
    <p class="mt-1 text-xs text-slate-500">{{ $t('settings.reloadHint') }}</p>
  </div>
</template>
