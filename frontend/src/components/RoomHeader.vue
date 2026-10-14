<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { useDismiss } from './useDismiss'

const props = defineProps<{
  story: string
  modelName: string
  /** Undo and clear need the writer to be idle. */
  working: boolean
}>()

const emit = defineEmits<{
  'change-model': [name: string]
  undo: []
  clear: []
}>()

// Model control
const modelOpen = ref(false)
const modelRoot = ref<HTMLElement | null>(null)
const modelButton = ref<HTMLButtonElement | null>(null)
const modelField = ref<HTMLInputElement | null>(null)
const modelDraft = ref(props.modelName)
useDismiss(modelOpen, modelRoot, modelButton)

watch(modelOpen, async (isOpen) => {
  if (!isOpen) return
  modelDraft.value = props.modelName
  await nextTick()
  modelField.value?.select()
})

function saveModel(): void {
  const name = modelDraft.value.trim()
  modelOpen.value = false
  if (name && name !== props.modelName) emit('change-model', name)
}

// Overflow menu
const menuOpen = ref(false)
const confirmingClear = ref(false)
const menuRoot = ref<HTMLElement | null>(null)
const menuButton = ref<HTMLButtonElement | null>(null)
useDismiss(menuOpen, menuRoot, menuButton)

watch(menuOpen, (isOpen) => {
  if (!isOpen) confirmingClear.value = false
})

function undo(): void {
  menuOpen.value = false
  emit('undo')
}

function clear(): void {
  menuOpen.value = false
  emit('clear')
}
</script>

<template>
  <header class="header">
    <RouterLink to="/" class="header__back">
      <span aria-hidden="true">‹</span><span class="header__back-words">The shelf</span>
    </RouterLink>
    <h1 class="header__title">{{ story }}</h1>

    <div ref="modelRoot" class="popover-anchor">
      <button
        ref="modelButton"
        type="button"
        class="header__model"
        :aria-expanded="modelOpen"
        aria-controls="model-popover"
        :title="`Model: ${modelName}. Change it.`"
        @click="modelOpen = !modelOpen"
      >
        <span class="sr-only">Model: </span>{{ modelName || 'model' }}
      </button>
      <form v-if="modelOpen" id="model-popover" class="popover on-paper" @submit.prevent="saveModel">
        <label class="popover__label" for="model-name">Model name</label>
        <input
          id="model-name"
          ref="modelField"
          v-model="modelDraft"
          class="popover__input"
          type="text"
          autocomplete="off"
          spellcheck="false"
        />
        <p class="popover__note">A turn that is running finishes on the previous model.</p>
        <div class="popover__actions">
          <button type="button" class="popover__button" @click="modelOpen = false">Cancel</button>
          <button type="submit" class="popover__button popover__button--primary">Use this model</button>
        </div>
      </form>
    </div>

    <div ref="menuRoot" class="popover-anchor">
      <button
        ref="menuButton"
        type="button"
        class="header__more"
        aria-label="More actions"
        :aria-expanded="menuOpen"
        aria-controls="more-popover"
        @click="menuOpen = !menuOpen"
      >
        <span aria-hidden="true">⋯</span>
      </button>
      <div v-if="menuOpen" id="more-popover" class="popover popover--menu on-paper">
        <template v-if="!confirmingClear">
          <button type="button" class="menu-item" :disabled="working" @click="undo">
            Undo last exchange
          </button>
          <button type="button" class="menu-item" :disabled="working" @click="confirmingClear = true">
            Clear conversation
          </button>
          <p v-if="working" class="popover__note">These wait until the writer is done.</p>
        </template>
        <template v-else>
          <p class="popover__note popover__note--strong" role="alert">
            Clear the whole conversation? The story's files stay.
          </p>
          <div class="popover__actions">
            <button type="button" class="popover__button" @click="confirmingClear = false">Keep it</button>
            <button type="button" class="popover__button popover__button--danger" @click="clear">
              Clear conversation
            </button>
          </div>
        </template>
      </div>
    </div>
  </header>
</template>

<style scoped>
.header {
  flex: none;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  grid-template-areas:
    'back more'
    'title title'
    'model model';
  align-items: center;
  column-gap: 0.5rem;
  padding: 0 0.15rem;
}

.header__back {
  grid-area: back;
  justify-self: start;
  display: inline-flex;
  align-items: center;
  min-height: 32px;
  font-size: var(--size-small);
  font-variant: small-caps;
  letter-spacing: 0.14em;
  text-decoration: none;
  color: var(--ink-on-desk-muted);
}

.header__back:hover {
  color: var(--link-on-desk-hover);
  text-decoration: underline;
}

.header__back-words {
  margin-left: 0.3em;
}

.header__title {
  grid-area: title;
  min-width: 0;
  margin: -0.1rem 0 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 1.9rem;
  line-height: 1.2;
  font-style: italic;
  font-weight: 400;
  color: var(--ink-on-desk);
}

.header > .popover-anchor:first-of-type {
  grid-area: model;
  justify-self: start;
  max-width: 100%;
}

.header > .popover-anchor:last-of-type {
  grid-area: more;
}

.header__model,
.header__more {
  background: transparent;
  color: var(--ink-on-desk-muted);
  border: 0;
  border-radius: var(--radius-button);
}

.header__model {
  max-width: 100%;
  min-height: 28px;
  margin-left: -0.35rem;
  padding: 0 0.35rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: var(--font-typewriter);
  font-size: 0.8125rem;
  text-decoration: underline dotted;
  text-underline-offset: 3px;
}

.header__more {
  min-width: 36px;
  min-height: 32px;
  font-size: 1.35rem;
  line-height: 1;
}

.header__model:hover,
.header__more:hover {
  background: var(--desk-hover);
  color: var(--link-on-desk-hover);
}

.header > .popover-anchor:first-of-type .popover {
  right: auto;
  left: 0;
}

.popover-anchor {
  position: relative;
  flex: none;
}

.popover {
  position: absolute;
  z-index: 20;
  top: calc(100% + 0.4rem);
  right: 0;
  width: min(20rem, 78vw);
  padding: 0.9rem;
  background: var(--menu-ground);
  color: var(--ink);
  border-radius: var(--radius-paper);
  box-shadow: var(--shadow-popover);
}

.popover--menu {
  width: min(16rem, 78vw);
  padding: 0.4rem;
}

.popover__label {
  display: block;
  margin-bottom: 0.3rem;
  font-size: var(--size-small);
  color: var(--ink-muted);
}

.popover__input {
  width: 100%;
  min-height: 40px;
  padding: 0 0.6rem;
  background: var(--field);
  color: var(--ink);
  border: 1.5px solid var(--field-edge);
  border-radius: var(--radius-paper);
  font-family: var(--font-typewriter);
  font-size: 0.875rem;
}

.popover__note {
  margin: 0.5rem 0 0;
  font-size: var(--size-small);
  color: var(--ink-muted);
}

.popover__note--strong {
  margin: 0.4rem 0.5rem 0.2rem;
  color: var(--ink);
}

.popover__actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
  margin-top: 0.7rem;
}

.popover__button,
.menu-item {
  min-height: 40px;
  padding: 0 0.9rem;
  background: var(--button-ground);
  color: var(--button-ink);
  border: 1.5px solid var(--button-edge);
  border-radius: var(--radius-button);
}

.popover__button:hover,
.menu-item:hover:not(:disabled) {
  background: var(--button-ground-hover);
}

.popover__button--primary {
  background: var(--send-bottom);
  border-color: var(--send-bottom);
  color: var(--send-ink);
}

.popover__button--primary:hover {
  background: var(--send-top);
}

.popover__button--danger {
  background: var(--stop-bottom);
  border-color: var(--stop-bottom);
  color: var(--stop-ink);
}

.popover__button--danger:hover {
  background: var(--stop-top);
}

.menu-item {
  display: block;
  width: 100%;
  text-align: left;
  background: transparent;
  border-color: transparent;
}

.menu-item:hover:not(:disabled) {
  background: var(--menu-hover);
}

.menu-item:disabled {
  color: var(--disabled-ink);
}

/* A narrow screen puts the header on one row: the back arrow, the title over its model, the menu. */
@media (max-width: 760px) {
  .header {
    grid-template-columns: auto minmax(0, 1fr) auto;
    grid-template-areas:
      'back title more'
      'back model more';
    column-gap: 0.15rem;
    padding: 0;
  }

  .header__back {
    justify-content: center;
    min-width: 40px;
    min-height: 44px;
    margin-left: -0.35rem;
    font-size: 1.75rem;
    line-height: 1;
  }

  .header__back:hover {
    text-decoration: none;
  }

  .header__back-words {
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    white-space: nowrap;
  }

  .header__title {
    margin: 0;
    font-size: 1.375rem;
    line-height: 1.15;
  }

  .header__model {
    min-height: 24px;
    font-size: 0.75rem;
  }

  .header__more {
    min-width: 44px;
    min-height: 44px;
  }
}
</style>
