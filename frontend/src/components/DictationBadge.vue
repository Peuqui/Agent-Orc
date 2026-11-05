<script setup lang="ts">
// The STT-Suite's logo in a round badge (assets/status-icons/stt-suite-icon.svg of AIfred), in the TTS-Suite
// logo's amber (Peuqui: the blue was too dark to see) and with a light rim, so it stands out on the dark page.
// The dictation's symbol: ready, it stands still and waits to be pressed; while speech is taken in, its bars
// rise and fall like a level, the arcs glow and the rim turns red (also where motion is reduced, so that
// ready and recording never look alike); while it is transcribed, it stands still and grey.
export type BadgePhase = 'ready' | 'listening' | 'transcribing'
defineProps<{ phase: BadgePhase }>()
// The logo's own measures: they fit the circle as they are.
const BARS = [
  { x: 96, from: 226, to: 286 },
  { x: 156, from: 176, to: 336 },
  { x: 216, from: 116, to: 396 },
  { x: 276, from: 166, to: 346 },
  { x: 336, from: 206, to: 306 },
]
</script>

<template>
  <!-- Grey through Tailwind's filter classes, which add up with a drop-shadow given from outside (one CSS
       filter of its own here would replace it). -->
  <svg viewBox="0 0 512 512" :class="[phase, { 'grayscale opacity-60': phase === 'transcribing' }]" aria-hidden="true">
    <defs>
      <linearGradient id="dictationBadgeWave" gradientUnits="userSpaceOnUse" x1="96" y1="116" x2="336" y2="396">
        <stop offset="0" stop-color="#f59e0b" />
        <stop offset="1" stop-color="#b45309" />
      </linearGradient>
    </defs>
    <circle class="rim" cx="256" cy="256" r="244" fill="#0f172a" stroke-width="24" />
    <g fill="none" stroke="url(#dictationBadgeWave)" stroke-width="30" stroke-linecap="round">
      <line v-for="bar in BARS" :key="bar.x" class="bar" :x1="bar.x" :y1="bar.from" :x2="bar.x" :y2="bar.to" />
    </g>
    <path class="arc" d="M388 196 q48 60 0 120" fill="none" stroke="#e2e8f0" stroke-width="22" stroke-linecap="round" />
    <path class="arc far" d="M424 156 q84 100 0 200" fill="none" stroke="#64748b" stroke-width="22" stroke-linecap="round" />
  </svg>
</template>

<style scoped>
.bar {
  transform-box: fill-box;
  transform-origin: center;
  animation: level 0.9s ease-in-out infinite;
}
.bar:nth-child(2) {
  animation-delay: -0.6s;
}
.bar:nth-child(3) {
  animation-delay: -0.3s;
}
.bar:nth-child(4) {
  animation-delay: -0.75s;
}
.bar:nth-child(5) {
  animation-delay: -0.45s;
}
.arc {
  animation: glow 1.2s ease-in-out infinite;
}
.arc.far {
  animation-delay: -0.6s;
}
.rim {
  stroke: #94a3b8;
}
.listening .rim {
  stroke: var(--color-accent-500);
}
.ready .bar,
.ready .arc,
.transcribing .bar,
.transcribing .arc {
  animation: none;
}
@media (prefers-reduced-motion: reduce) {
  .bar,
  .arc {
    animation: none;
  }
}
@keyframes level {
  0%,
  100% {
    transform: scaleY(0.45);
  }
  50% {
    transform: scaleY(1);
  }
}
@keyframes glow {
  0%,
  100% {
    opacity: 0.35;
  }
  50% {
    opacity: 1;
  }
}
</style>
