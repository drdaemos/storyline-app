<script setup lang="ts">
import { computed } from 'vue'
import type { ClockView } from '@/protocol/types'

const props = defineProps<{ clocks: readonly ClockView[]; hidden: number }>()

const visible = computed(() => props.clocks.length > 0 || props.hidden > 0)
const hiddenWords = computed(() => `${props.hidden} hidden`)

function isFull(clock: ClockView): boolean {
  return clock.segments > 0 && clock.filled >= clock.segments
}
</script>

<template>
  <section v-if="visible" class="clocks on-paper" aria-labelledby="clocks-title">
    <span class="clocks__pin" aria-hidden="true"></span>
    <h2 id="clocks-title" class="clocks__title">Clocks</h2>
    <ul class="clocks__list">
      <li v-for="clock in clocks" :key="clock.id" class="clock" :class="{ 'clock--full': isFull(clock) }">
        <span class="clock__name">{{ clock.name }}</span>
        <span class="sr-only">{{ clock.filled }} of {{ clock.segments }}{{ isFull(clock) ? ', full' : '' }}</span>
        <span class="clock__segments" aria-hidden="true">
          <span
            v-for="index in clock.segments"
            :key="index"
            class="clock__segment"
            :class="{ 'clock__segment--filled': index <= clock.filled }"
          ></span>
        </span>
        <span class="clock__count" aria-hidden="true">
          {{ clock.filled }}/{{ clock.segments }}<template v-if="isFull(clock)"> full</template>
        </span>
      </li>
    </ul>
    <p v-if="hidden > 0" class="clocks__hidden">{{ hiddenWords }}</p>
  </section>
</template>

<style scoped>
.clocks {
  position: relative;
  flex: none;
  max-height: 30%;
  min-height: 0;
  overflow-y: auto;
  padding: 0.9rem 1.2rem 0.6rem;
  background: var(--surface-card);
  color: var(--ink);
  box-shadow: var(--shadow-card);
  border-radius: var(--radius-paper);
}

.clocks__pin {
  position: absolute;
  top: -8px;
  left: calc(50% - 8px);
  width: 16px;
  height: 16px;
  border-radius: var(--radius-round);
  background: radial-gradient(circle at 35% 30%, var(--pin-top), var(--pin-bottom) 70%);
  box-shadow: var(--shadow-pin);
}

.clocks__title {
  margin: 0 0 0.3rem;
  padding-bottom: 0.3rem;
  font-size: 1.0625rem;
  font-weight: 500;
  font-variant: small-caps;
  letter-spacing: 0.16em;
  color: var(--accent);
  border-bottom: 1.5px solid var(--accent-soft);
}

.clocks__list {
  margin: 0;
  padding: 0;
  list-style: none;
  font-family: var(--font-list);
  font-size: var(--size-list);
}

.clock {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.3rem 0;
  line-height: 1.4;
  border-bottom: 1px solid var(--paper-rule);
}

.clock:last-child {
  border-bottom: 0;
}

.clock__name {
  flex: 1 1 auto;
  min-width: 0;
  overflow-wrap: anywhere;
}

.clock__segments {
  flex: none;
  display: flex;
  gap: 3px;
}

.clock__segment {
  width: 14px;
  height: 14px;
  background: var(--clock-empty);
  border: 1.5px solid var(--clock-edge);
  border-radius: var(--radius-stamp);
}

.clock__segment--filled {
  background: var(--clock-filled);
  border-color: var(--clock-filled);
}

.clock__count {
  flex: none;
  min-width: 3.2ch;
  font-family: var(--font-typewriter);
  font-size: var(--size-small);
  color: var(--ink-muted);
  text-align: right;
}

.clock--full .clock__name,
.clock--full .clock__count {
  color: var(--accent);
  font-weight: 600;
}

.clocks__hidden {
  margin: 0.3rem 0 0;
  font-family: var(--font-typewriter);
  font-size: var(--size-small);
  font-style: italic;
  color: var(--ink-muted);
}

@media (max-width: 760px) {
  .clocks {
    max-height: 25%;
    padding: 0.7rem 0.9rem 0.4rem;
  }

  .clock {
    flex-wrap: wrap;
    gap: 0.25rem 0.6rem;
  }

  .clock__segment {
    width: 12px;
    height: 12px;
  }
}
</style>
