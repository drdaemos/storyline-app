<template>
  <div v-if="pending" class="space-y-2">
    <p class="font-medium text-lg">{{ pending.prompt }}</p>

    <template v-if="pending.kind === 'choice'">
      <button
        v-for="option in pending.options"
        :key="option.index"
        type="button"
        class="vn-option block w-full text-left px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-700 hover:bg-primary-50 dark:hover:bg-primary-900 transition-colors"
        :disabled="disabled"
        @click="$emit('choose', option.index)"
      >
        {{ option.intent }}
      </button>
    </template>

    <template v-else>
      <div class="flex gap-2">
        <button
          type="button"
          class="vn-deeper px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-700 hover:bg-primary-50 dark:hover:bg-primary-900 transition-colors"
          :disabled="disabled"
          @click="$emit('goDeeper')"
        >
          Look closer
        </button>
        <button
          type="button"
          class="vn-proceed px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-700 hover:bg-primary-50 dark:hover:bg-primary-900 transition-colors"
          :disabled="disabled"
          @click="$emit('proceed')"
        >
          Continue
        </button>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import type { VNPending } from '@/types/vn'

defineProps<{
  pending: VNPending | null
  disabled?: boolean
}>()

defineEmits<{
  choose: [index: number]
  goDeeper: []
  proceed: []
}>()
</script>
