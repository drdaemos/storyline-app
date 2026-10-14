<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { NARROW_SCREEN, TOUCH_SCREEN, useMediaQuery } from './useMediaQuery'

const props = defineProps<{
  /** The text in the input. */
  draft: string
  /** True while the writer works: Enter then queues the prompt and Stop is offered. */
  working: boolean
  /** Prompts the writer has not read yet. */
  queue: readonly string[]
  disabled?: boolean
}>()

const emit = defineEmits<{
  'update:draft': [text: string]
  send: []
  stop: []
}>()

const field = ref<HTMLTextAreaElement | null>(null)
const canSend = computed(() => !props.disabled && props.draft.trim() !== '')
/** A soft keyboard has no Shift+Enter, so on a touch screen Enter starts a new line and the button sends. */
const touch = useMediaQuery(TOUCH_SCREEN)
/** A narrow input fits a shorter placeholder on one line, beside Stop and Queue. */
const narrow = useMediaQuery(NARROW_SCREEN)
const placeholder = computed(() => (narrow.value ? 'Message the writer' : 'Tell the writer what you want'))

function onKeydown(event: KeyboardEvent): void {
  if (touch.value || event.key !== 'Enter' || event.shiftKey || event.isComposing) return
  event.preventDefault()
  if (canSend.value) emit('send')
}

function resize(): void {
  const element = field.value
  if (!element) return
  element.style.height = 'auto'
  element.style.height = `${element.scrollHeight}px`
}

onMounted(resize)
watch(
  () => props.draft,
  async () => {
    await nextTick()
    resize()
  }
)

function focus(): void {
  field.value?.focus()
}

defineExpose({ focus })
</script>

<template>
  <form class="composer" @submit.prevent="canSend && emit('send')">
    <section v-if="queue.length > 0" class="queue on-paper" aria-labelledby="queue-title">
      <h3 id="queue-title" class="queue__title">Queued, not read yet</h3>
      <ul class="queue__list">
        <li v-for="(prompt, index) in queue" :key="index" class="queue__item">{{ prompt }}</li>
      </ul>
    </section>
    <div class="composer__field on-paper">
      <label class="sr-only" for="prompt-input">Message the writer</label>
      <textarea
        id="prompt-input"
        ref="field"
        class="composer__input"
        rows="1"
        :value="draft"
        :disabled="disabled"
        :placeholder="placeholder"
        :enterkeyhint="touch ? 'enter' : 'send'"
        @input="emit('update:draft', ($event.target as HTMLTextAreaElement).value)"
        @keydown="onKeydown"
      ></textarea>
      <div class="composer__row">
        <p class="composer__hint">
          <template v-if="!touch">Enter sends. Shift+Enter starts a new line.</template>
        </p>
        <button v-if="working" type="button" class="button button--stop" @click="emit('stop')">
          Stop
        </button>
        <button type="submit" class="button button--send" :disabled="!canSend">
          {{ working ? 'Queue' : 'Send' }}
        </button>
      </div>
    </div>
  </form>
</template>

<style scoped>
.composer {
  flex: none;
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.queue {
  padding: 0.5rem 0.9rem;
  background: var(--surface-ticket);
  color: var(--ink);
  border-radius: var(--radius-paper);
  box-shadow: var(--shadow-stamp);
  max-height: 7.5rem;
  overflow-y: auto;
}

.queue__title {
  margin: 0 0 0.2rem;
  font-size: 0.75rem;
  font-weight: 400;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--ink-muted);
}

.queue__list {
  margin: 0;
  padding: 0;
  list-style: none;
  font-family: var(--font-typewriter);
  font-size: var(--size-small);
}

.queue__item {
  padding: 0.15rem 0;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.composer__field {
  background: var(--surface-sheet);
  border-radius: var(--radius-paper);
  box-shadow: var(--shadow-field);
}

.composer__field:focus-within {
  outline: 2px solid var(--focus-ring-on-desk);
  outline-offset: 2px;
}

.composer__input:focus-visible {
  outline: none;
}

.composer__input {
  display: block;
  width: 100%;
  min-height: 3.5rem;
  max-height: 10rem;
  padding: 0.9rem 1.1rem 0.4rem;
  resize: none;
  background: transparent;
  color: var(--ink);
  border: 0;
  border-radius: var(--radius-paper);
  font-family: var(--font-manuscript);
  font-size: 1.1875rem;
  line-height: 1.4;
}

.composer__input::placeholder {
  color: var(--field-placeholder);
}

.composer__row {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.35rem 0.6rem 0.6rem 1.1rem;
}

.composer__hint {
  flex: 1 1 0;
  min-width: 0;
  margin: 0;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
  font-size: var(--size-small);
  font-style: italic;
  color: var(--ink-faint);
}

.button {
  min-width: 5.25rem;
  min-height: 40px;
  padding: 0 1.1rem;
  border: 0;
  border-radius: var(--radius-button);
  box-shadow: var(--shadow-button);
  font-size: 1.0625rem;
  font-weight: 600;
  font-variant: small-caps;
  letter-spacing: 0.1em;
}

.button--send {
  background: var(--surface-brass);
  color: var(--brass-ink);
}

.button--send:hover:not(:disabled) {
  background: var(--surface-brass-hover);
}

.button--stop {
  background: var(--surface-wax);
  color: var(--stop-ink);
}

.button--stop:hover {
  background: var(--surface-wax-hover);
}

.button:active:not(:disabled) {
  transform: translateY(1px);
}

.button:disabled {
  background: var(--surface-dull);
  color: var(--dull-ink);
  box-shadow: none;
  opacity: 0.55;
}

/* A narrow screen puts the buttons beside the input, so the conversation keeps the height. */
@media (max-width: 760px) {
  .composer {
    gap: 0.4rem;
  }

  .queue {
    max-height: 4.5rem;
    padding: 0.35rem 0.75rem;
  }

  .composer__field {
    display: flex;
    align-items: flex-end;
  }

  .composer__input {
    flex: 1 1 auto;
    min-width: 0;
    min-height: 2.9rem;
    max-height: 35vh;
    padding: 0.7rem 0.5rem 0.6rem 0.85rem;
    font-size: 1.0625rem;
  }

  .composer__row {
    flex: none;
    gap: 0.35rem;
    padding: 0.35rem;
  }

  .composer__hint {
    display: none;
  }

  .button {
    min-width: 0;
    min-height: 44px;
    padding: 0 0.75rem;
    font-size: 1rem;
    letter-spacing: 0.06em;
  }
}
</style>
