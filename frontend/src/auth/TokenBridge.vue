<script setup lang="ts">
import { useAuth } from '@clerk/vue'
import { onBeforeUnmount } from 'vue'
import { setTokenProvider } from '@/api/auth'

// The API client asks for a fresh session token on every request. Children render after this setup runs.
const { getToken } = useAuth()
setTokenProvider(() => getToken.value())
onBeforeUnmount(() => setTokenProvider(null))
</script>

<template>
  <slot />
</template>
