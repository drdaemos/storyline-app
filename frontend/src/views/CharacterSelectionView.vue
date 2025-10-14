<template>
  <!-- Header -->
  <div class="mb-8">
    <div>
      <h2 class="text-3xl font-bold font-serif">Choose a Character</h2>
    </div>
  </div>

  <!-- Loading state -->
  <UPageGrid v-if="!characters.length && loading">
    <UCard class="min-h-48 flex items-end-safe">
      <template #footer>
        <USkeleton class="h-4 w-40 mb-2"></USkeleton>
        <USkeleton class="h-4 w-60"></USkeleton>
      </template>
    </UCard>
  </UPageGrid>

  <!-- Error state -->
  <UAlert
    v-else-if="error"
    color="error"
    variant="soft"
    icon="i-lucide-alert-triangle"
    title="Failed to load characters"
    :description="error.message"
  >
    <template #actions>
      <UButton color="error" variant="solid" @click="loadCharacters">
        Try Again
      </UButton>
    </template>
  </UAlert>

  <!-- Character Grid -->
  <UPageGrid v-else>
    <CharacterCard
      v-for="character in characters"
      :key="character.id"
      :character-summary="character"
      @select="selectCharacter"
    />

    <CharacterCard
      :is-create-new="true"
      @create="navigateToCreate"
    />
  </UPageGrid>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useApi } from '@/composables/useApi'
import { useLocalSettings } from '@/composables/useLocalSettings'
import CharacterCard from '@/components/CharacterCard.vue'
import type { CharacterSummary } from '@/types'

const router = useRouter()
const { getCharacters, loading, error } = useApi()
const { updateSetting } = useLocalSettings()

const characters = ref<CharacterSummary[]>([])

const loadCharacters = async () => {
  try {
    characters.value = await getCharacters()
  } catch (err) {
    console.error('Failed to load characters:', err)
  }
}

const selectCharacter = (characterId: string) => {
  updateSetting('lastSelectedCharacter', characterId)
  router.push({
    name: 'character',
    params: { characterId }
  })
}

const navigateToCreate = () => {
  router.push({ name: 'create' })
}

onMounted(() => {
  loadCharacters()
})
</script>
