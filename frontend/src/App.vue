<script setup lang="ts">
import { RouterView } from 'vue-router'
import AuthGate from '@/auth/AuthGate.vue'
</script>

<template>
  <AuthGate>
    <RouterView />
  </AuthGate>
</template>
