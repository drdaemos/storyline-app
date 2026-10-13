<script setup lang="ts">
import { computed, ref } from 'vue'
import type { Activity } from '@/protocol/types'
import { ROLE_FILES } from '@/room/useStoryFiles'
import type { StoryFiles } from '@/room/useStoryFiles'
import LorePage from './LorePage.vue'
import RoleFilePage from './RoleFilePage.vue'
import ScriptPage from './ScriptPage.vue'

const props = defineProps<{ files: StoryFiles; activity: Activity }>()

const TABS = [
  { id: 'script', label: 'Script' },
  { id: 'lore', label: 'Lore' },
  { id: 'plan', label: 'Plan' },
  { id: 'style', label: 'Style' },
  { id: 'agreement', label: 'Agreement' },
] as const

type TabId = (typeof TABS)[number]['id']

const ROLE_PAGES = [
  { id: 'plan', title: 'Plan', filename: ROLE_FILES.plan, empty: 'No plan has been written yet.' },
  { id: 'style', title: 'Style', filename: ROLE_FILES.style, empty: 'No style notes have been written yet.' },
  {
    id: 'agreement',
    title: 'Working agreement',
    filename: ROLE_FILES.agreement,
    empty: 'No working agreement has been written yet.',
  },
] as const

const active = ref<TabId>('script')
const tabButtons = ref<HTMLButtonElement[]>([])
const writing = computed(() => props.activity === 'writing')

function select(id: TabId, focus = false): void {
  active.value = id
  if (focus) tabButtons.value[TABS.findIndex((tab) => tab.id === id)]?.focus()
}

function onTabKeydown(event: KeyboardEvent, index: number): void {
  const last = TABS.length - 1
  const target: Record<string, number> = {
    ArrowRight: index === last ? 0 : index + 1,
    ArrowLeft: index === 0 ? last : index - 1,
    Home: 0,
    End: last,
  }
  const next = target[event.key]
  if (next === undefined) return
  event.preventDefault()
  select(TABS[next]!.id, true)
}
</script>

<template>
  <section class="book" aria-label="The book">
    <div class="bookmarks" role="tablist" aria-label="Book sections">
      <button
        v-for="(tab, index) in TABS"
        :id="`tab-${tab.id}`"
        :key="tab.id"
        :ref="(element) => { if (element) tabButtons[index] = element as HTMLButtonElement }"
        type="button"
        role="tab"
        class="bookmark"
        :class="[`bookmark--${tab.id}`, { 'bookmark--active': active === tab.id }]"
        :aria-selected="active === tab.id"
        :aria-controls="`panel-${tab.id}`"
        :tabindex="active === tab.id ? 0 : -1"
        @click="select(tab.id)"
        @keydown="onTabKeydown($event, index)"
      >
        {{ tab.label }}
      </button>
    </div>

    <div class="cover">
      <div class="page on-paper">
        <div
          id="panel-script"
          class="panel"
          :class="{ 'panel--hidden': active !== 'script' }"
          role="tabpanel"
          aria-labelledby="tab-script"
        >
          <ScriptPage :script="files.script.value" :baseline="files.scriptBaseline.value" :writing="writing" />
        </div>

        <div
          id="panel-lore"
          class="panel panel--lore"
          :class="{ 'panel--hidden': active !== 'lore' }"
          role="tabpanel"
          aria-labelledby="tab-lore"
        >
          <LorePage :index="files.loreIndex.value" :files="files.loreFiles" @want="files.want" />
        </div>

        <div
          v-for="page in ROLE_PAGES"
          :id="`panel-${page.id}`"
          :key="page.id"
          class="panel"
          :class="[`panel--${page.id}`, { 'panel--hidden': active !== page.id }]"
          role="tabpanel"
          :aria-labelledby="`tab-${page.id}`"
        >
          <RoleFilePage
            :title="page.title"
            :filename="page.filename"
            :empty-text="page.empty"
            :file="files.loreFiles[page.filename]"
            :shown="active === page.id"
            @want="files.want"
          />
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.book {
  position: relative;
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
}

/* Cloth bookmarks tucked between the pages: their lower ends disappear under the page block. */
.bookmarks {
  position: relative;
  z-index: 1;
  flex: none;
  display: flex;
  align-items: flex-end;
  gap: 0.5rem;
  height: 5.1rem;
  margin: 0 2.5rem -2.75rem 2.75rem;
}

.bookmark {
  flex: 0 1 6.25rem;
  min-width: 0;
  height: 4.1rem;
  padding: 0.45rem 0.25rem 0;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  background: var(--bookmark-shade), var(--texture-weave), var(--tab-color);
  color: var(--bookmark-ink);
  border: 0;
  border-radius: var(--radius-bookmark);
  box-shadow: var(--shadow-bookmark);
  font-size: var(--size-bookmark);
  font-variant: small-caps;
  letter-spacing: 0.08em;
  line-height: 1.2;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  filter: brightness(0.8) saturate(0.9);
  transition:
    height 140ms ease,
    filter 140ms ease;
}

.bookmark--script {
  --tab-color: var(--bookmark-script);
}

.bookmark--lore {
  --tab-color: var(--bookmark-lore);
}

.bookmark--plan {
  --tab-color: var(--bookmark-plan);
}

.bookmark--style {
  --tab-color: var(--bookmark-style);
}

.bookmark--agreement {
  --tab-color: var(--bookmark-agreement);
}

.bookmark:hover {
  height: 4.5rem;
  filter: brightness(0.95);
}

.bookmark--active,
.bookmark--active:hover {
  height: 5.1rem;
  font-weight: 600;
  filter: none;
}

@media (prefers-reduced-motion: reduce) {
  .bookmark {
    transition: none;
  }
}

.bookmark:focus-visible {
  outline-offset: 1px;
  z-index: 3;
}

.cover {
  position: relative;
  flex: 1 1 0;
  min-height: 0;
  padding: 0.95rem 1.5rem 1.45rem 0.7rem;
  background: var(--surface-leather);
  border-radius: var(--radius-leather);
  box-shadow: var(--shadow-book);
}

/* Stitching along the cover's edge. */
.cover::before {
  content: '';
  position: absolute;
  inset: 5px;
  border: 1px dashed var(--leather-stitch);
  border-radius: calc(var(--radius-leather) - 2px);
  pointer-events: none;
}

.page {
  position: relative;
  z-index: 2;
  height: 100%;
  background: var(--page-surface);
  border-radius: 2px var(--radius-paper) var(--radius-paper) 2px;
  box-shadow: var(--page-stack);
}

.panel {
  position: absolute;
  inset: 0 0.75rem 0 2.25rem;
}

.panel--hidden {
  visibility: hidden;
  pointer-events: none;
}

.panel--lore {
  --tab-color: var(--bookmark-lore);
}

.panel--plan {
  --tab-color: var(--bookmark-plan);
}

.panel--style {
  --tab-color: var(--bookmark-style);
}

.panel--agreement {
  --tab-color: var(--bookmark-agreement);
}

@media (max-width: 760px) {
  .bookmarks {
    margin-inline: 0.5rem;
    gap: 0.25rem;
  }

  .bookmark {
    flex-basis: 0;
    flex-grow: 1;
    padding-inline: 0.1rem;
    font-size: 0.75rem;
    letter-spacing: 0;
  }

  .bookmarks {
    margin: 0 0.75rem -2.75rem 1rem;
  }

  .cover {
    padding: 0.8rem 0.9rem 1rem 0.45rem;
  }

  .panel {
    inset: 0 0.25rem 0 1rem;
  }
}
</style>
