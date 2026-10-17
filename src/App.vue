<script setup lang="ts">
import BuddyVoice from './components/BuddyVoice.vue'
import LoginScreen from './components/LoginScreen.vue'
import { session } from './session'

// ?name=Ada just prefills the sign-in field.
const suggestedName = new URLSearchParams(window.location.search).get('name')?.trim() ?? ''
</script>

<template>
  <LoginScreen v-if="!session" :suggested-name="suggestedName" />
  <BuddyVoice v-else :key="session.name" :name="session.name" />
</template>
