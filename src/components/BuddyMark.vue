<script setup lang="ts">
// The buddy's face as a logo mark. `id` keeps the gradient unique per instance.
defineProps<{ size?: number; id?: string }>()
</script>

<template>
  <svg :width="size ?? 26" :height="size ?? 26" viewBox="0 0 64 64" class="mark" aria-hidden="true">
    <defs>
      <radialGradient :id="`buddy-mark-${id ?? 'default'}`" cx="0.38" cy="0.34" r="0.75">
        <stop offset="0" stop-color="#ffc4aa" />
        <stop offset="0.5" stop-color="#e8805e" />
        <stop offset="1" stop-color="#b04c32" />
      </radialGradient>
    </defs>
    <ellipse cx="32" cy="32" rx="29" ry="28" :fill="`url(#buddy-mark-${id ?? 'default'})`" />
    <ellipse cx="22.5" cy="29" rx="3.5" ry="5.5" fill="#421a12" />
    <ellipse cx="41.5" cy="29" rx="3.5" ry="5.5" fill="#421a12" />
    <path
      d="M26 40q6 5 12 0"
      fill="none"
      stroke="#421a12"
      stroke-width="2.6"
      stroke-linecap="round"
    />
  </svg>
</template>

<style scoped>
.mark {
  filter: drop-shadow(0 2px 6px rgba(0, 0, 0, 0.45));
}
</style>
