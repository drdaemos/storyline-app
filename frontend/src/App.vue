<script setup lang="ts">
import { SquareLibrary } from 'lucide-vue-next'
import { computed, ref } from 'vue'
import { SignedIn, SignedOut, SignInButton, UserButton } from '@clerk/vue'
import SettingsMenu from './components/SettingsMenu.vue'
import { useAuth } from './composables/useAuth'

const globalError = ref<string | null>(null)
const { isDevAuthBypassEnabled, devBypassUser } = useAuth()
const authBypassEnabled = computed(() => isDevAuthBypassEnabled.value)

const items = computed(() => [
  { label: 'Characters', to: '/' },
  { label: 'Create', to: '/create' },
  { label: 'Scenarios', to: '/library/scenarios' },
  { label: 'World Lore', to: '/library/world-lore' },
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
  <UApp class="story-shell">
    <UHeader class="backdrop-blur-sm bg-white/60 dark:bg-black/20 border-b border-white/60">
      <template #title>
        <SquareLibrary :size="26" class="text-primary" />
        <span class="story-headline text-lg">Storyline</span>
      </template>

      <SignedIn v-if="!authBypassEnabled">
        <UNavigationMenu :items="items" />
      </SignedIn>
      <UNavigationMenu v-if="authBypassEnabled" :items="items" />

      <template #right>
        <UColorModeButton class="cursor-pointer" />

        <SignedOut v-if="!authBypassEnabled">
          <SignInButton>
            <UButton variant="soft" icon="i-lucide-log-in" class="cursor-pointer"></UButton>
          </SignInButton>
        </SignedOut>
        <SignedIn v-if="!authBypassEnabled">
          <SettingsMenu />
          <UserButton :appearance="appearance" />
        </SignedIn>
        <template v-if="authBypassEnabled">
          <SettingsMenu />
          <UBadge color="primary" variant="soft">{{ devBypassUser.name }}</UBadge>
        </template>
      </template>

      <template #body>
        <SignedIn v-if="!authBypassEnabled">
          <UNavigationMenu :items="items" orientation="vertical" class="-mx-2.5" />
        </SignedIn>
        <UNavigationMenu v-if="authBypassEnabled" :items="items" orientation="vertical" class="-mx-2.5" />
      </template>
    </UHeader>
    <UContainer class="pt-8 pb-10">
      <SignedIn v-if="!authBypassEnabled">
        <router-view />
      </SignedIn>
      <template v-if="authBypassEnabled">
        <router-view />
      </template>
      <SignedOut v-if="!authBypassEnabled">
        <div class="max-w-xl mx-auto text-center space-y-6 story-panel p-8">
          <div class="inline-flex story-chip px-3 py-1 text-xs font-medium">
            Character-first storytelling workspace
          </div>
          <h2 class="text-4xl story-headline flex justify-center gap-2 items-center">
            <SquareLibrary :size="36" class="text-primary" />
            Storyline
          </h2>
          <p class="story-subtext">
            Build characters, craft scenarios, and run sessions with an AI assistant-driven flow.
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
