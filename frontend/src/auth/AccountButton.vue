<script setup lang="ts">
import { UserButton } from '@clerk/vue'
import { clerkEnabled } from './clerk'
</script>

<template>
  <UserButton v-if="clerkEnabled" />
</template>
