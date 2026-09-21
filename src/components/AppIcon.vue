<script setup lang="ts">
defineProps<{ name: 'menu' | 'gear' | 'plus' | 'close' | 'mic' | 'updown'; size?: number }>()

// Eight-tooth gear outline, matching the desktop version.
const gearPoints = Array.from({ length: 8 }, (_, k) =>
  [
    [-0.3, 6.8],
    [-0.16, 9.2],
    [0.16, 9.2],
    [0.3, 6.8],
  ].map(([offset, r]) => {
    const a = ((k + offset!) * Math.PI * 2) / 8
    return `${(12 + Math.cos(a) * r!).toFixed(2)},${(12 + Math.sin(a) * r!).toFixed(2)}`
  }),
)
  .flat()
  .join(' ')
</script>

<template>
  <svg
    :width="size ?? 24"
    :height="size ?? 24"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.9"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
  >
    <template v-if="name === 'menu'">
      <path d="M4 6.5h16M4 12h16M4 17.5h10" />
    </template>
    <template v-else-if="name === 'gear'">
      <polygon :points="gearPoints" />
      <circle cx="12" cy="12" r="3" />
    </template>
    <template v-else-if="name === 'plus'">
      <path d="M12 4v16M4 12h16" />
    </template>
    <template v-else-if="name === 'close'">
      <path d="M6 6l12 12M18 6L6 18" />
    </template>
    <template v-else-if="name === 'mic'">
      <rect x="9" y="2.5" width="6" height="12" rx="3" />
      <path d="M5.5 10.5a6.5 6.5 0 0 0 13 0M12 17v4.5" />
    </template>
    <template v-else-if="name === 'updown'">
      <path d="M8 9.5l4-4 4 4M8 14.5l4 4 4-4" />
    </template>
  </svg>
</template>
