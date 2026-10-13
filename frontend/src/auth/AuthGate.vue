<script setup lang="ts">
import { ClerkLoaded, ClerkLoading, SignedIn, SignedOut } from '@clerk/vue'
import { clerkEnabled } from './clerk'
import SignInScreen from './SignInScreen.vue'
import TokenBridge from './TokenBridge.vue'
</script>

<template>
  <template v-if="clerkEnabled">
    <ClerkLoading>
      <p class="gate-quiet" role="status">Opening Storyline…</p>
    </ClerkLoading>
    <ClerkLoaded>
      <SignedIn>
        <TokenBridge><slot /></TokenBridge>
      </SignedIn>
      <SignedOut>
        <SignInScreen />
      </SignedOut>
    </ClerkLoaded>
  </template>
  <slot v-else />
</template>

<style scoped>
.gate-quiet {
  margin: 0;
  padding: 2rem;
  color: var(--ink-on-desk-muted);
  font-style: italic;
}
</style>
