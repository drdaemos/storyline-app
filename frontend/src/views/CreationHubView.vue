<template>
  <section class="space-y-8">
    <div class="story-panel p-6 md:p-8">
      <div class="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div class="space-y-2">
          <span class="story-chip px-3 py-1 text-xs font-medium inline-flex">
            Creation Hub
          </span>
          <h1 class="story-headline text-3xl md:text-4xl">Build New Story Assets</h1>
          <p class="story-subtext max-w-2xl">
            Start a character, prepare a scenario, or move toward ruleset-first workflows.
          </p>
        </div>
      </div>
    </div>

    <div class="grid gap-5 lg:grid-cols-3">
      <UCard class="story-card-hover story-panel-muted">
        <template #header>
          <div class="flex items-center gap-2">
            <UIcon name="i-lucide-user-round-plus" class="w-5 h-5 text-primary" />
            <h2 class="story-headline text-xl">Character</h2>
          </div>
        </template>
        <p class="story-subtext text-sm mb-4">
          Use the assistant + structured card workflow to define a new character or persona.
        </p>
        <UButton color="primary" icon="i-lucide-sparkles" @click="router.push({ name: 'create-character' })">
          Create Character
        </UButton>
      </UCard>

      <UCard class="story-card-hover story-panel-muted">
        <template #header>
          <div class="flex items-center gap-2">
            <UIcon name="i-lucide-clapperboard" class="w-5 h-5 text-primary" />
            <h2 class="story-headline text-xl">Scenario</h2>
          </div>
        </template>
        <p class="story-subtext text-sm mb-4">
          Build scenarios by cast tags and world-lore tags.
        </p>
        <div class="flex gap-2">
          <UButton color="primary" icon="i-lucide-arrow-right" @click="openScenarioCreation">
            Create Scenario
          </UButton>
          <UButton
            color="neutral"
            variant="soft"
            icon="i-lucide-library"
            @click="router.push({ name: 'library-scenarios' })"
          >
            Library
          </UButton>
        </div>
      </UCard>

      <UCard class="story-card-hover story-panel-muted">
        <template #header>
          <div class="flex items-center gap-2">
            <UIcon name="i-lucide-book-marked" class="w-5 h-5 text-primary" />
            <h2 class="story-headline text-xl">World Lore</h2>
          </div>
        </template>
        <p class="story-subtext text-sm mb-4">
          Create reusable world context assets and attach them across scenarios.
        </p>
        <div class="flex gap-2">
          <UButton color="primary" icon="i-lucide-book-plus" @click="router.push({ name: 'create-world-lore' })">
            Create World Lore
          </UButton>
          <UButton color="neutral" variant="soft" icon="i-lucide-library" @click="router.push({ name: 'library-world-lore' })">
            Library
          </UButton>
        </div>
      </UCard>
    </div>
  </section>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()

const openScenarioCreation = () => {
  router.push({ name: 'create-scenario-global' })
}
</script>
