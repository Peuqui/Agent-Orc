<script setup lang="ts">
// Imported, so the bundler emits a path that also works under a proxy sub-path.
import iconUrl from '../../brand/icon.svg'
</script>

<template>
  <div class="flex items-center gap-2.5">
    <img :src="iconUrl" alt="" class="size-10" />
    <div class="flex flex-col leading-none">
      <span class="text-2xl font-medium tracking-tight text-slate-100" aria-label="AI-Orc">
        AI-<span class="font-serif text-red-500 italic">Ø</span>rc
      </span>
      <span class="mt-1 text-[0.55rem] font-semibold tracking-[0.18em] text-slate-400 uppercase">
        {{ $t('app.tagline') }}
      </span>
    </div>
  </div>
</template>
