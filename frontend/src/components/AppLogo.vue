<script setup lang="ts">
// Imported, so the bundler emits a path that also works under a proxy sub-path.
import iconUrl from '../../brand/icon.svg'

// nameClass: when the name shows beside the icon (the page header leaves it out where room is short).
defineProps<{ nameClass?: string }>()
</script>

<template>
  <div class="flex items-center gap-2.5">
    <img :src="iconUrl" alt="" class="size-11 sm:size-12" />
    <div class="flex-col leading-none" :class="nameClass ?? 'flex'">
      <span class="text-2xl font-medium tracking-tight whitespace-nowrap text-bright sm:text-3xl" aria-label="Agent-Orc">
        Agent-<span class="font-serif text-accent-500 italic">Ø</span>rc
      </span>
      <span class="mt-1 text-[0.55rem] font-semibold tracking-[0.18em] text-dim uppercase">
        {{ $t('app.tagline') }}
      </span>
    </div>
  </div>
</template>
