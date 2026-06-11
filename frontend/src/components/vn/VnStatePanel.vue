<template>
  <div class="text-sm space-y-2">
    <div>
      <p class="font-semibold mb-1">State</p>
      <ul class="space-y-0.5">
        <li v-for="(value, name) in vars" :key="name" class="flex justify-between gap-4">
          <span class="text-gray-500">{{ name }}</span>
          <span class="font-mono">{{ value }}</span>
        </li>
      </ul>
      <p v-if="!Object.keys(vars).length" class="text-gray-500">(no state vars)</p>
    </div>
    <div>
      <p class="font-semibold mb-1">Visited</p>
      <p class="font-mono text-xs text-gray-500 break-words">{{ visited.join(', ') || '(nothing yet)' }}</p>
    </div>
    <div>
      <p class="font-semibold mb-1">Position</p>
      <p class="font-mono text-xs text-gray-500">{{ sceneId }} / {{ beatId }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { VNStateValue } from '@/types/vn'

defineProps<{
  vars: Record<string, VNStateValue>
  visited: string[]
  sceneId: string
  beatId: string
}>()
</script>
