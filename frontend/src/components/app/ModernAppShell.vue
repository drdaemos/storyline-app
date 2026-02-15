<script setup lang="ts">
import { Moon, Sun, SquareLibrary } from 'lucide-vue-next'
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { SignedIn, SignedOut, SignInButton, UserButton } from '@clerk/vue'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'

interface NavItem {
  label: string
  to: string
}

interface Props {
  authBypass: boolean
}

defineProps<Props>()

const route = useRoute()

const navItems: NavItem[] = [
  { label: 'Home', to: '/' },
  { label: 'Hub', to: '/hub' },
  { label: 'Sessions', to: '/sessions' },
]

const isDark = ref(false)

const appearance = {
  elements: {
    userButtonBox: 'rounded-md p-0.5',
  },
}

const showStyleLab = computed(() => import.meta.env.DEV)

const isActive = (to: string) => {
  if (to === '/') {
    return route.path === '/'
  }
  return route.path === to || route.path.startsWith(`${to}/`)
}

const syncThemeState = () => {
  isDark.value = document.documentElement.classList.contains('dark')
}

const toggleTheme = () => {
  document.documentElement.classList.toggle('dark')
  isDark.value = document.documentElement.classList.contains('dark')

  const nextTheme = isDark.value ? 'dark' : 'light'
  localStorage.setItem('storyline_theme', nextTheme)
}

onMounted(() => {
  const storedTheme = localStorage.getItem('storyline_theme')
  if (storedTheme === 'dark') {
    document.documentElement.classList.add('dark')
  } else if (storedTheme === 'light') {
    document.documentElement.classList.remove('dark')
  }

  syncThemeState()
})
</script>

<template>
  <div class="min-h-screen">
    <header class="sticky top-0 z-20 border-b border-border/70 bg-background/85 backdrop-blur">
      <div class="mx-auto flex w-full max-w-7xl items-center justify-between gap-3 px-4 py-3 sm:px-6 lg:px-8">
        <RouterLink to="/" class="inline-flex items-center gap-2">
          <SquareLibrary class="size-5" />
          <span class="display-heading text-lg">Storyline</span>
        </RouterLink>

        <nav class="hidden items-center gap-1 md:flex">
          <Button
            v-for="item in navItems"
            :key="item.to"
            size="sm"
            :variant="isActive(item.to) ? 'default' : 'ghost'"
            as-child
          >
            <RouterLink :to="item.to">{{ item.label }}</RouterLink>
          </Button>

          <Button v-if="showStyleLab" size="sm" variant="ghost" as-child>
            <RouterLink to="/style-lab">Style Lab</RouterLink>
          </Button>
        </nav>

        <div class="flex items-center gap-2">
          <Button size="icon" variant="outline" aria-label="Toggle theme" @click="toggleTheme">
            <Sun v-if="isDark" class="size-4" />
            <Moon v-else class="size-4" />
          </Button>

          <template v-if="authBypass">
            <Badge variant="outline">Auth Bypass</Badge>
          </template>
          <template v-else>
            <SignedOut>
              <SignInButton>
                <Button size="sm">Sign In</Button>
              </SignInButton>
            </SignedOut>
            <SignedIn>
              <UserButton :appearance="appearance" />
            </SignedIn>
          </template>
        </div>
      </div>
    </header>

    <slot />
  </div>
</template>
