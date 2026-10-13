<script setup lang="ts">
import { SignIn } from '@clerk/vue'
import { clerkAppearance } from '@/theme'
</script>

<template>
  <main class="sign-in">
    <h1 class="sign-in__title">Storyline</h1>
    <p class="sign-in__lead">Sign in to meet the writer.</p>
    <SignIn :appearance="clerkAppearance" />
  </main>
</template>

<style scoped>
.sign-in {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
  min-height: 100%;
  padding: 2rem 1rem;
}

.sign-in__title {
  margin: 0;
  font-size: 2.5rem;
  font-style: italic;
  font-weight: 400;
}

.sign-in__lead {
  margin: 0 0 0.75rem;
  color: var(--ink-on-desk-muted);
}
</style>
