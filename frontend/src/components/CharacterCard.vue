<template>
  <UCard
    v-if="!isCreateNew"
    :class="[
      'min-h-48 flex items-end-safe cursor-pointer transition-all hover:shadow-md shadow-primary/20',
      selected && 'ring-2 ring-primary'
    ]"
    @click="handleClick"
  >
    <template #footer>
      <div class="space-y-1 w-full">
        <p class="text-md font-semibold">{{ characterSummary?.name }}</p>
        <p v-if="characterSummary?.role" class="text-sm text-gray-600 dark:text-gray-400">
          {{ characterSummary.role }}
        </p>
      </div>
    </template>
  </UCard>

  <UCard
    v-else
    variant="subtle"
    class="min-h-32 flex items-end-safe cursor-pointer border-dashed hover:shadow-md shadow-indigo-500/20 transition-all"
    @click="handleClick"
  >
    <p class="text-md font-semibold">
      Create New Character
    </p>
  </UCard>
</template>

<script setup lang="ts">
import type { CharacterSummary } from '@/types'

interface Props {
  characterSummary?: CharacterSummary
  selected?: boolean
  isCreateNew?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  selected: false,
  isCreateNew: false
})

const emit = defineEmits<{
  select: [characterName: string]
  create: []
}>()

const handleClick = () => {
  if (props.isCreateNew) {
    emit('create')
  } else if (props.characterSummary) {
    emit('select', props.characterSummary.id)
  }
}
</script>
