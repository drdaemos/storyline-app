<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { createStory, describeError, listPresets, listStories } from '@/api/client'
import AccountButton from '@/auth/AccountButton.vue'
import type { PresetSummary } from '@/protocol/types'

const router = useRouter()

const stories = ref<string[]>([])
const active = ref<string | null>(null)
const loading = ref(true)
const loadError = ref<string | null>(null)

const name = ref('')
const creating = ref(false)
const createError = ref<string | null>(null)

/** The kinds of story on offer, default first. Empty if they could not be loaded: a default story still works. */
const presets = ref<PresetSummary[]>([])
const preset = ref<string | null>(null)

const COVERS = 5
/** The same name always gets the same cover. */
function coverOf(story: string): number {
  let hash = 0
  for (const char of story) hash = (hash * 31 + char.charCodeAt(0)) % 9973
  return (hash % COVERS) + 1
}

const ordered = computed(() => {
  const rest = stories.value.filter((story) => story !== active.value)
  return active.value && stories.value.includes(active.value) ? [active.value, ...rest] : rest
})

async function load(): Promise<void> {
  loading.value = true
  loadError.value = null
  try {
    const result = await listStories()
    stories.value = result.stories
    active.value = result.active
  } catch (error) {
    loadError.value = describeError(error)
  } finally {
    loading.value = false
  }
}

async function loadPresets(): Promise<void> {
  try {
    presets.value = (await listPresets()).presets
    preset.value = presets.value[0]?.id ?? null
  } catch {
    presets.value = []
    preset.value = null
  }
}

async function create(): Promise<void> {
  const wanted = name.value.trim()
  if (!wanted || creating.value) return
  creating.value = true
  createError.value = null
  try {
    const created = await createStory(wanted, presets.value.length > 1 ? preset.value : null)
    await router.push({ name: 'room', params: { name: created.name } })
  } catch (error) {
    createError.value = describeError(error)
  } finally {
    creating.value = false
  }
}

onMounted(() => {
  document.title = 'Storyline'
  void load()
  void loadPresets()
})
</script>

<template>
  <main class="shelf" :class="{ 'shelf--empty': !loading && !loadError && stories.length === 0 }">
    <header class="shelf__head">
      <h1 class="shelf__title">Storyline</h1>
      <AccountButton />
    </header>

    <p v-if="loading" class="shelf__quiet" role="status">Looking at the shelf…</p>
    <div v-else-if="loadError" class="shelf__quiet shelf__quiet--error" role="alert">
      <p>{{ loadError }}</p>
      <button type="button" class="button" @click="load">Try again</button>
    </div>

    <template v-else>
      <section v-if="stories.length > 0" class="books" aria-label="Your stories">
        <ul class="books__list">
          <li v-for="story in ordered" :key="story" class="slot">
            <RouterLink :to="{ name: 'room', params: { name: story } }" class="book" :class="`book--${coverOf(story)}`">
              <span class="book__title">{{ story }}</span>
              <span v-if="story === active" class="book__ribbon">
                <span class="sr-only">Last opened</span>
              </span>
            </RouterLink>
          </li>
        </ul>
      </section>

      <form class="new on-paper" @submit.prevent="create">
        <h2 class="new__title">{{ stories.length === 0 ? 'Begin your first story' : 'Start a new story' }}</h2>
        <p v-if="stories.length === 0" class="new__lead">
          Name it, and the writer will meet you in the room.
        </p>
        <label class="new__label" for="story-name">Story name</label>
        <div class="new__row">
          <input
            id="story-name"
            v-model="name"
            class="new__input"
            type="text"
            autocomplete="off"
            spellcheck="false"
            :aria-invalid="createError !== null"
            :aria-describedby="createError ? 'story-name-error' : undefined"
          />
          <button type="submit" class="button button--primary" :disabled="creating || name.trim() === ''">
            {{ creating ? 'Creating…' : 'Create story' }}
          </button>
        </div>
        <fieldset v-if="presets.length > 1" class="new__kinds">
          <legend class="new__label">Kind of story</legend>
          <label v-for="option in presets" :key="option.id" class="kind" :class="{ 'kind--chosen': preset === option.id }">
            <input v-model="preset" class="kind__radio" type="radio" name="story-preset" :value="option.id" />
            <span class="kind__title">{{ option.title }}</span>
            <span class="kind__description">{{ option.description }}</span>
          </label>
        </fieldset>
        <p v-if="createError" id="story-name-error" class="new__error" role="alert">{{ createError }}</p>
      </form>
    </template>
  </main>
</template>

<style scoped>
.shelf {
  display: flex;
  flex-direction: column;
  gap: 2.75rem;
  min-height: 100%;
  max-width: 68rem;
  margin: 0 auto;
  padding: 3rem 2rem 4rem;
}

.shelf--empty {
  justify-content: center;
}

.shelf__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}

.shelf__title {
  margin: 0;
  font-size: 3rem;
  line-height: 1.1;
  font-style: italic;
  font-weight: 400;
  text-shadow: var(--text-on-desk-shadow);
}

.shelf__quiet {
  margin: 0;
  color: var(--ink-on-desk-muted);
  font-style: italic;
}

.shelf__quiet--error {
  color: var(--ink-on-desk);
}

/* Closed books laid out on the desk. */
.books__list {
  display: flex;
  flex-wrap: wrap;
  gap: 2.75rem 2.5rem;
  margin: 0;
  padding: 0;
  list-style: none;
}

.slot {
  position: relative;
}

.book {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 11.5rem;
  height: 16rem;
  padding: 1.5rem 1.25rem 1.5rem 2rem;
  color: var(--cover-gilt);
  border-radius: 3px 7px 7px 3px;
  box-shadow: var(--shadow-cover);
  text-align: center;
  text-decoration: none;
  background: var(--cover-shade), var(--cover);
  transition:
    transform 160ms ease-out,
    box-shadow 160ms ease-out;
}

/* A gilt frame tooled into the cover. */
.book::before {
  content: '';
  position: absolute;
  inset: 0.8rem 0.75rem 0.8rem 1.45rem;
  border: 1px solid var(--cover-tooling);
  border-radius: 2px;
  outline: 1px solid var(--cover-tooling);
  outline-offset: -5px;
  pointer-events: none;
}

.book:hover {
  color: var(--cover-gilt);
  transform: translateY(-6px);
  box-shadow: var(--shadow-cover-raised);
}

.book--1 {
  --cover: var(--cover-1);
}

.book--2 {
  --cover: var(--cover-2);
}

.book--3 {
  --cover: var(--cover-3);
}

.book--4 {
  --cover: var(--cover-4);
}

.book--5 {
  --cover: var(--cover-5);
}

.book__title {
  display: -webkit-box;
  -webkit-line-clamp: 5;
  line-clamp: 5;
  -webkit-box-orient: vertical;
  overflow: hidden;
  font-size: 1.4375rem;
  font-style: italic;
  line-height: 1.25;
  overflow-wrap: anywhere;
  text-shadow: var(--text-emboss);
}

.book__ribbon {
  position: absolute;
  top: 0;
  right: 1.4rem;
  width: 0.85rem;
  height: 2.6rem;
  background: var(--texture-weave), var(--accent-soft);
  clip-path: polygon(0 0, 100% 0, 100% 100%, 50% 80%, 0 100%);
}

.new {
  max-width: 34rem;
  padding: 1.4rem 1.6rem 1.6rem;
  background: var(--surface-card);
  color: var(--ink);
  border-radius: var(--radius-paper);
  box-shadow: var(--shadow-card);
}

.shelf--empty .new {
  align-self: center;
  width: 100%;
  padding: 2rem;
}

.new__title {
  margin: 0 0 0.4rem;
  font-size: var(--size-heading);
  font-style: italic;
  font-weight: 400;
}

.new__lead {
  margin: 0 0 0.75rem;
  color: var(--ink-muted);
}

.new__label {
  display: block;
  margin-bottom: 0.25rem;
  font-size: var(--size-small);
  color: var(--ink-muted);
}

.new__row {
  display: flex;
  gap: 0.6rem;
  flex-wrap: wrap;
}

.new__input {
  flex: 1 1 12rem;
  min-width: 0;
  min-height: 44px;
  padding: 0 0.8rem;
  background: var(--field);
  color: var(--ink);
  border: 1.5px solid var(--field-edge);
  border-radius: var(--radius-paper);
  font-size: 1.125rem;
}

.new__input[aria-invalid='true'] {
  border-color: var(--error);
}

.new__kinds {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  margin: 0.9rem 0 0;
  padding: 0;
  border: 0;
}

.kind {
  display: grid;
  grid-template-columns: auto 1fr;
  column-gap: 0.6rem;
  align-items: baseline;
  min-height: 44px;
  padding: 0.5rem 0.75rem;
  border: 1.5px solid var(--field-edge);
  border-radius: var(--radius-paper);
}

.kind--chosen {
  border-color: var(--accent);
  background: var(--field);
}

.kind__title {
  font-weight: 600;
}

.kind__description {
  grid-column: 2;
  font-size: var(--size-small);
  color: var(--ink-muted);
}

.new__error {
  margin: 0.6rem 0 0;
  color: var(--error);
}

.button {
  min-height: 44px;
  padding: 0 1.2rem;
  background: var(--button-ground);
  color: var(--button-ink);
  border: 1.5px solid var(--button-edge);
  border-radius: var(--radius-button);
}

.button--primary {
  background: var(--surface-brass);
  border: 0;
  color: var(--brass-ink);
  box-shadow: var(--shadow-button);
  font-variant: small-caps;
  font-weight: 600;
  font-size: 1.0625rem;
  letter-spacing: 0.1em;
}

.button--primary:hover:not(:disabled) {
  background: var(--surface-brass-hover);
}

.button:disabled {
  background: var(--surface-dull);
  color: var(--dull-ink);
  box-shadow: none;
  opacity: 0.6;
}

@media (prefers-reduced-motion: reduce) {
  .book {
    transition: none;
  }
}
</style>
