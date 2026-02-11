<template>
  <UCard
    v-if="!isCreateNew"
    :class="[
      'min-h-40 cursor-pointer story-card-hover story-panel-muted',
      selected && 'ring-2 ring-primary'
    ]"
    @click="handleClick"
  >
    <template #header>
      <div class="h-12 rounded-lg bg-gradient-to-br from-cyan-100 to-emerald-50 border border-white/70"></div>
    </template>
    <template #footer>
      <div class="space-y-1 w-full">
        <p class="text-lg story-headline">{{ characterSummary?.name }}</p>
        <p v-if="characterSummary?.tagline" class="text-sm story-subtext line-clamp-2">
          {{ characterSummary.tagline }}
        </p>
      </div>
    </template>
  </UCard>

  <UCard
    v-else
    class="min-h-40 cursor-pointer border-dashed story-card-hover story-panel-muted"
    @click="handleClick"
  >
    <div class="h-full flex flex-col justify-between gap-3">
      <div class="w-11 h-11 rounded-full bg-primary/10 flex items-center justify-center">
        <UIcon name="i-lucide-user-round-plus" class="w-5 h-5 text-primary" />
      </div>
      <div>
        <p class="text-lg story-headline">Create New Character</p>
        <p class="text-sm story-subtext">Open the creation hub and launch a fresh profile.</p>
      </div>
    </div>
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
  isCreateNew: false,
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
