<script setup lang="ts">
import { nextTick, onMounted, ref } from 'vue'
import BuddyMark from './BuddyMark.vue'
import { MAX_NAME, signIn } from '@/session'

const props = defineProps<{ suggestedName?: string }>()

const name = ref(props.suggestedName ?? '')
const password = ref('')
const error = ref('')
const nameField = ref<HTMLInputElement>()

onMounted(() => nextTick(() => nameField.value?.focus()))

function onSubmit() {
  if (signIn(name.value)) return
  error.value = 'Please tell me what to call you'
  nameField.value?.focus()
}
</script>

<template>
  <main class="screen">
    <form class="card" @submit.prevent="onSubmit">
      <BuddyMark :size="72" id="login" />
      <h1>Buddy AI</h1>
      <p class="tagline">Sign in and I'll call you by your name.</p>

      <label class="field">
        <span>Your name</span>
        <input
          ref="nameField"
          v-model="name"
          type="text"
          name="name"
          autocomplete="given-name"
          :maxlength="MAX_NAME"
          placeholder="Favour"
          :aria-invalid="!!error"
          :aria-describedby="error ? 'name-error' : undefined"
          @input="error = ''"
        />
      </label>

      <label class="field">
        <span>Password</span>
        <input
          v-model="password"
          type="password"
          name="password"
          autocomplete="current-password"
          placeholder="anything you like"
        />
      </label>

      <p v-if="error" id="name-error" class="error" role="alert">{{ error }}</p>

      <button class="submit" type="submit">Start talking</button>

      <p class="note">
        Demo sign-in: nothing is checked or sent anywhere. Your name is kept in this browser and
        only used for the greeting.
      </p>
    </form>
  </main>
</template>

<style scoped>
.screen {
  display: grid;
  place-items: center;
  min-height: 100dvh;
  padding: 28px 20px calc(28px + env(safe-area-inset-bottom));
  background:
    radial-gradient(120% 55% at 50% 118%, rgba(78, 112, 158, 0.45), rgba(30, 40, 56, 0) 70%),
    #161616;
  color: #eae5dc;
}

.card {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 100%;
  max-width: 380px;
  padding: 38px 28px 26px;
  border-radius: 26px;
  background: rgba(28, 28, 29, 0.82);
  border: 1px solid rgba(255, 255, 255, 0.08);
  box-shadow: 0 24px 60px rgba(0, 0, 0, 0.45);
}

h1 {
  margin-top: 16px;
  font-family: 'Newsreader', Georgia, 'Times New Roman', serif;
  font-weight: 400;
  font-size: 30px;
  letter-spacing: -0.01em;
}

.tagline {
  margin-top: 6px;
  margin-bottom: 26px;
  font-size: 14px;
  color: #9a9a9e;
  text-align: center;
}

.field {
  width: 100%;
  margin-bottom: 14px;
}

.field span {
  display: block;
  margin-bottom: 7px;
  font-size: 13px;
  color: #a6a6ab;
}

input {
  width: 100%;
  height: 50px;
  padding: 0 16px;
  border-radius: 14px;
  background: rgba(16, 16, 17, 0.9);
  border: 1px solid rgba(255, 255, 255, 0.12);
  color: #f0ece4;
  font: inherit;
  font-size: 16px;
  transition:
    border-color 0.16s,
    box-shadow 0.16s;
}

input::placeholder {
  color: #6a6a6e;
}

input:focus {
  outline: none;
  border-color: rgba(140, 185, 250, 0.8);
  box-shadow: 0 0 0 3px rgba(80, 140, 230, 0.22);
}

input[aria-invalid='true'] {
  border-color: rgba(240, 130, 110, 0.8);
}

.error {
  align-self: flex-start;
  margin: -4px 0 10px;
  font-size: 13px;
  color: #f09a86;
}

.submit {
  width: 100%;
  height: 52px;
  margin-top: 8px;
  border: 1.4px solid rgba(110, 160, 230, 0.5);
  border-radius: 26px;
  background: radial-gradient(circle at 50% 10%, rgb(44, 72, 110), rgb(20, 36, 60) 80%);
  color: #f0f4fa;
  font: inherit;
  font-size: 16px;
  cursor: pointer;
  transition:
    border-color 0.16s,
    transform 0.11s,
    box-shadow 0.2s;
  box-shadow: 0 0 24px 2px rgba(80, 140, 230, 0.18);
}

.submit:hover {
  border-color: rgba(150, 195, 255, 0.85);
  box-shadow: 0 0 34px 6px rgba(80, 140, 230, 0.3);
}

.submit:active {
  transform: scale(0.98);
}

.submit:focus-visible,
input:focus-visible {
  outline: 2px solid #8fb6ff;
  outline-offset: 3px;
}

.note {
  margin-top: 18px;
  font-size: 12px;
  line-height: 1.5;
  color: #76767a;
  text-align: center;
}
</style>
