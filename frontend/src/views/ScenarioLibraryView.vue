<template>
  <section class="space-y-6">
    <div class="story-panel p-6 md:p-8 flex flex-wrap gap-4 items-end justify-between">
      <div class="space-y-2">
        <span class="story-chip px-3 py-1 text-xs font-medium inline-flex">Scenario Library</span>
        <h1 class="story-headline text-3xl md:text-4xl">Global Scenarios</h1>
        <p class="story-subtext">Multi-character scenarios and world-linked story seeds.</p>
      </div>
      <UButton color="primary" icon="i-lucide-plus" @click="router.push({ name: 'create-scenario-global' })">
        New Scenario
      </UButton>
    </div>

    <UAlert
      v-if="error"
      color="error"
      variant="soft"
      icon="i-lucide-alert-triangle"
      title="Failed to load scenarios"
      :description="error.message"
    />

    <div v-if="loading" class="grid md:grid-cols-2 xl:grid-cols-3 gap-4">
      <UCard v-for="i in 3" :key="i" class="story-panel-muted">
        <USkeleton class="h-5 w-48 mb-3" />
        <USkeleton class="h-4 w-36 mb-2" />
        <USkeleton class="h-4 w-24" />
      </UCard>
    </div>

    <div v-else-if="scenarios.length === 0" class="story-panel-muted p-8 text-center">
      <h2 class="text-xl story-headline mb-2">No scenarios yet</h2>
      <p class="story-subtext mb-4">Create your first multi-character scenario from the creation hub.</p>
      <UButton color="primary" @click="router.push({ name: 'create-scenario-global' })">Create Scenario</UButton>
    </div>

    <div v-else class="grid md:grid-cols-2 xl:grid-cols-3 gap-4">
      <UCard v-for="scenario in scenarios" :key="scenario.id" class="story-panel-muted story-card-hover">
        <div class="space-y-3">
          <div class="flex items-start justify-between gap-3">
            <h3 class="story-headline text-lg line-clamp-2">{{ scenario.summary }}</h3>
            <UButton
              color="neutral"
              variant="ghost"
              icon="i-lucide-trash-2"
              size="xs"
              @click="deleteScenarioById(scenario.id)"
            />
          </div>
          <div class="flex flex-wrap gap-2">
            <UBadge v-if="scenario.narrative_category" color="primary" variant="soft">{{ scenario.narrative_category }}</UBadge>
            <UBadge v-if="scenario.world_lore_id" color="neutral" variant="soft">
              {{ worldLoreMap[scenario.world_lore_id] || scenario.world_lore_id }}
            </UBadge>
          </div>
          <p class="text-sm story-subtext">
            Characters: {{ formatCharacterNames(scenario.character_ids, scenario.character_id) }}
          </p>
          <div class="pt-2">
            <UButton
              color="primary"
              variant="soft"
              size="sm"
              :disabled="!scenario.character_id"
              @click="startSession(scenario)"
            >
              Start Session
            </UButton>
          </div>
        </div>
      </UCard>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useApi } from '@/composables/useApi'
import { useLocalSettings } from '@/composables/useLocalSettings'
import type { ScenarioSummary } from '@/types'

const router = useRouter()
const { settings } = useLocalSettings()
const { listAllScenarios, getCharacters, listWorldLore, deleteScenario, startSessionWithScenario, loading, error } = useApi()

const scenarios = ref<ScenarioSummary[]>([])
const characterMap = ref<Record<string, string>>({})
const worldLoreMap = ref<Record<string, string>>({})

const loadData = async () => {
  const [scenarioResponse, characterList, loreList] = await Promise.all([
    listAllScenarios(),
    getCharacters(),
    listWorldLore().catch(() => []),
  ])
  scenarios.value = scenarioResponse.scenarios || []
  characterMap.value = Object.fromEntries(characterList.map(character => [character.id, character.name]))
  worldLoreMap.value = Object.fromEntries(loreList.map(item => [item.id, item.name]))
}

const formatCharacterNames = (characterIds: string[] | undefined, primaryCharacter: string): string => {
  const ids = (characterIds && characterIds.length > 0 ? characterIds : [primaryCharacter]).filter(Boolean)
  return ids.map(id => characterMap.value[id] || id).join(', ')
}

const startSession = async (scenario: ScenarioSummary) => {
  const response = await startSessionWithScenario({
    scenario_id: scenario.id,
    small_model_key: settings.value.smallModelKey,
    large_model_key: settings.value.largeModelKey,
  })
  router.push({ name: 'chat', params: { characterId: scenario.character_id, sessionId: response.session_id } })
}

const deleteScenarioById = async (scenarioId: string) => {
  if (!confirm('Delete this scenario?')) {
    return
  }
  await deleteScenario(scenarioId)
  scenarios.value = scenarios.value.filter(scenario => scenario.id !== scenarioId)
}

onMounted(() => {
  loadData()
})
</script>
