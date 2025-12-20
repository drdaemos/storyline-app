<script setup lang="ts">
import { SquareLibrary } from 'lucide-vue-next'
import { computed, ref } from 'vue'
import { SignedIn, SignedOut, SignInButton, UserButton } from '@clerk/vue'
import SettingsMenu from './components/SettingsMenu.vue'

const globalError = ref<string | null>(null)

const items = computed(() => [
  { label: 'Characters', to: '/' },
  { label: 'Create', to: '/create' },
])

const clearGlobalError = () => {
  globalError.value = null
}

// Global error handler
window.addEventListener('unhandledrejection', (_event) => {
  globalError.value = 'Something went wrong. Please try again.'
})

window.addEventListener('error', (_event) => {
  globalError.value = 'Something went wrong. Please try again.'
})

const appearance = {
  elements: {
    userButtonBox: 'rounded-md p-0.5',
  },
}
</script>


<template>
  <UApp>
    <UHeader>
      <template #title>
        <SquareLibrary :size="28" class="drop-shadow-sm drop-shadow-primary" />
        <span class="font-display font-light text-shadow-sm text-shadow-primary/50">Storyline</span>
      </template>

      <SignedIn>
        <UNavigationMenu :items="items" />
      </SignedIn>

      <template #right>
        <UColorModeButton class="cursor-pointer" />

        <SignedOut>
          <SignInButton>
            <UButton variant="soft" icon="i-lucide-log-in" class="cursor-pointer"></UButton>
          </SignInButton>
        </SignedOut>
        <SignedIn>
          <SettingsMenu />
          <UserButton :appearance="appearance" />
        </SignedIn>
      </template>

      <template #body>
        <SignedIn>
          <UNavigationMenu :items="items" orientation="vertical" class="-mx-2.5" />
        </SignedIn>
      </template>
    </UHeader>
    <UContainer class="pt-8">
      <SignedIn>
        <router-view />
      </SignedIn>
      <SignedOut>
        <div class="max-w-md mx-auto text-center space-y-6">
          <h2 class="text-3xl font-bold flex justify-center gap-1 items-center">
            Welcome to <SquareLibrary :size="32" class="drop-shadow-sm drop-shadow-primary" /><span class="font-serif text-shadow-sm text-shadow-primary/50">Storyline</span>
          </h2>
          <p>
            Create and chat with AI-powered characters. Sign in to get started!
          </p>
          <SignInButton>
            <UButton color="primary" variant="solid" icon="i-lucide-log-in" class="cursor-pointer">
              Sign In
            </UButton>
          </SignInButton>
        </div>
      </SignedOut>
    </UContainer>

    <UAlert v-if="globalError" @close="clearGlobalError">
      <template #title>Error</template>
      <template #description>
        {{ globalError }}
      </template>
    </UAlert>

    <UNotifications />
  </UApp>
</template>