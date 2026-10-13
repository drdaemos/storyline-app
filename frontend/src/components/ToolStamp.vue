<script setup lang="ts">
import { computed, ref, useId } from 'vue'
import type { ToolCallEntry } from '@/protocol/types'
import { outcomeTone, prettyJson } from '@/room/format'

const props = defineProps<{ entry: ToolCallEntry }>()

const open = ref(false)
const detailsId = useId()
const tone = computed(() => outcomeTone(props.entry.outcome))
const request = computed(() => prettyJson(props.entry.arguments))
</script>

<template>
  <div class="stamp on-paper" :class="`stamp--${tone}`" data-kind="tool_call">
    <button
      type="button"
      class="stamp__button"
      :aria-expanded="open"
      :aria-controls="detailsId"
      @click="open = !open"
    >
      <span class="stamp__name">{{ entry.tool_name }}</span>
      <span class="stamp__outcome">{{ entry.outcome }}</span>
      <span class="stamp__chevron" aria-hidden="true">{{ open ? '–' : '+' }}</span>
    </button>
    <div v-show="open" :id="detailsId" class="stamp__details">
      <h4 class="stamp__label">Request</h4>
      <pre class="stamp__text">{{ request }}</pre>
      <h4 class="stamp__label">Result</h4>
      <pre class="stamp__text">{{ entry.result ?? 'Waiting for a result.' }}</pre>
    </div>
  </div>
</template>

<style scoped>
/* A ticket stub: a coloured edge tells how the call went. */
.stamp {
  align-self: flex-start;
  max-width: 100%;
  background: var(--surface-ticket);
  color: var(--stamp-ink);
  border-left: 4px solid var(--stamp-edge);
  border-radius: var(--radius-stamp);
  box-shadow: var(--shadow-stamp);
}

.stamp--done {
  border-left-color: var(--stamp-edge-done);
}

.stamp--trouble {
  border-left-color: var(--stamp-edge-retry);
}

.stamp__button {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  min-height: 40px;
  padding: 0 0.8rem 0 0.7rem;
  background: transparent;
  border: 0;
  font-family: var(--font-typewriter);
  font-size: 0.8125rem;
  letter-spacing: 0.03em;
  text-align: left;
  color: inherit;
}

.stamp__button:hover .stamp__name {
  text-decoration: underline;
}

.stamp__name {
  font-weight: 700;
  overflow-wrap: anywhere;
}

.stamp__outcome {
  font-style: italic;
}

.stamp--trouble .stamp__outcome {
  color: var(--error);
}

.stamp--pending .stamp__outcome {
  color: var(--ink-muted);
}

.stamp__chevron {
  margin-left: auto;
  padding-left: 0.5rem;
}

.stamp__details {
  padding: 0 0.75rem 0.75rem;
  border-top: 1px dashed var(--stamp-edge);
  font-family: var(--font-typewriter);
  font-size: 0.8125rem;
}

.stamp__label {
  margin: 0.6rem 0 0.2rem;
  font-size: 0.75rem;
  font-weight: 400;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--ink-muted);
}

.stamp__text {
  margin: 0;
  max-height: 14rem;
  overflow: auto;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  color: var(--ink);
}
</style>
