<script setup lang="ts">
import { SquareLibrary } from 'lucide-vue-next'
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { SignedIn, SignedOut, SignInButton, UserButton } from '@clerk/vue'
import ModernAppShell from './components/app/ModernAppShell.vue'
import SettingsMenu from './components/SettingsMenu.vue'

const globalError = ref<string | null>(null)
const route = useRoute()

const authBypass = ['true', '1', 'yes'].includes(
  String(import.meta.env.VITE_AUTH_BYPASS || '').toLowerCase()
)

const legacyItems = computed(() => [
  { label: 'Legacy Characters', to: '/legacy/characters' },
  { label: 'Create', to: '/create' },
  { label: 'Style Lab', to: '/style-lab' },
])

const currentLayout = computed(() => {
  return String(route.meta.layout || 'legacy') as 'modern' | 'legacy' | 'bare'
})

const clearGlobalError = () => {
  globalError.value = null
}

const handleUnhandledRejection = () => {
  globalError.value = 'Something went wrong. Please try again.'
}

const handleWindowError = () => {
  globalError.value = 'Something went wrong. Please try again.'
}

onMounted(() => {
  window.addEventListener('unhandledrejection', handleUnhandledRejection)
  window.addEventListener('error', handleWindowError)
})

onBeforeUnmount(() => {
  window.removeEventListener('unhandledrejection', handleUnhandledRejection)
  window.removeEventListener('error', handleWindowError)
})

const appearance = {
  elements: {
    userButtonBox: 'rounded-md p-0.5',
  },
}
</script>

<template>
  <UApp>
    <template v-if="currentLayout === 'modern'">
      <template v-if="authBypass">
        <ModernAppShell :auth-bypass="true">
          <router-view />
        </ModernAppShell>
      </template>
      <template v-else>
        <SignedIn>
          <ModernAppShell :auth-bypass="false">
            <router-view />
          </ModernAppShell>
        </SignedIn>
        <SignedOut>
          <div class="mx-auto mt-10 max-w-md space-y-6 text-center">
            <h2 class="flex items-center justify-center gap-1 text-3xl font-bold">
              Welcome to
              <SquareLibrary :size="32" class="drop-shadow-sm drop-shadow-primary" />
              <span class="font-serif text-shadow-sm text-shadow-primary/50">Storyline</span>
            </h2>
            <p>Sign in to access Home, Hub, Sessions, and Play.</p>
            <SignInButton>
              <UButton color="primary" variant="solid" icon="i-lucide-log-in" class="cursor-pointer">
                Sign In
              </UButton>
            </SignInButton>
          </div>
        </SignedOut>
      </template>
    </template>

    <template v-else-if="currentLayout === 'bare'">
      <template v-if="authBypass">
        <router-view />
      </template>
      <template v-else>
        <SignedIn>
          <router-view />
        </SignedIn>
        <SignedOut>
          <div class="mx-auto mt-10 max-w-md space-y-6 text-center">
            <h2 class="flex items-center justify-center gap-1 text-3xl font-bold">
              Welcome to
              <SquareLibrary :size="32" class="drop-shadow-sm drop-shadow-primary" />
              <span class="font-serif text-shadow-sm text-shadow-primary/50">Storyline</span>
            </h2>
            <p>Sign in to continue.</p>
            <SignInButton>
              <UButton color="primary" variant="solid" icon="i-lucide-log-in" class="cursor-pointer">
                Sign In
              </UButton>
            </SignInButton>
          </div>
        </SignedOut>
      </template>
    </template>

    <template v-else>
      <UHeader>
        <template #title>
          <SquareLibrary :size="28" class="drop-shadow-sm drop-shadow-primary" />
          <span class="font-display font-light text-shadow-sm text-shadow-primary/50">Storyline</span>
        </template>

        <template v-if="authBypass">
          <UNavigationMenu :items="legacyItems" />
        </template>
        <SignedIn v-else>
          <UNavigationMenu :items="legacyItems" />
        </SignedIn>

        <template #right>
          <UColorModeButton class="cursor-pointer" />

          <template v-if="authBypass">
            <UBadge color="warning" variant="soft"> Auth Bypass </UBadge>
          </template>
          <template v-else>
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
        </template>

        <template #body>
          <template v-if="authBypass">
            <UNavigationMenu :items="legacyItems" orientation="vertical" class="-mx-2.5" />
          </template>
          <SignedIn v-else>
            <UNavigationMenu :items="legacyItems" orientation="vertical" class="-mx-2.5" />
          </SignedIn>
        </template>
      </UHeader>

      <UContainer class="pt-8">
        <template v-if="authBypass">
          <router-view />
        </template>
        <SignedIn v-else>
          <router-view />
        </SignedIn>
        <SignedOut v-if="!authBypass">
          <div class="mx-auto max-w-md space-y-6 text-center">
            <h2 class="flex items-center justify-center gap-1 text-3xl font-bold">
              Welcome to
              <SquareLibrary :size="32" class="drop-shadow-sm drop-shadow-primary" />
              <span class="font-serif text-shadow-sm text-shadow-primary/50">Storyline</span>
            </h2>
            <p>Create and chat with AI-powered characters. Sign in to get started.</p>
            <SignInButton>
              <UButton color="primary" variant="solid" icon="i-lucide-log-in" class="cursor-pointer">
                Sign In
              </UButton>
            </SignInButton>
          </div>
        </SignedOut>
      </UContainer>
    </template>

    <UAlert v-if="globalError" @close="clearGlobalError">
      <template #title>Error</template>
      <template #description>
        {{ globalError }}
      </template>
    </UAlert>

    <UNotifications />
  </UApp>
</template>
