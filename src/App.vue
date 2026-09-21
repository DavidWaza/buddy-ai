<script setup lang="ts">
import BuddyVoice from './components/BuddyVoice.vue'

// Greeting name, overridable with ?name=Ada
const name = new URLSearchParams(window.location.search).get('name')?.trim() || 'Favour'
</script>

<template>
  <BuddyVoice :name="name" />
</template>
