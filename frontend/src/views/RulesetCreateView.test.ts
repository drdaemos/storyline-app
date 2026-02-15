import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import RulesetCreateView from './RulesetCreateView.vue'

const push = vi.fn()
const createRuleset = vi.fn()

vi.mock('vue-router', () => ({
  RouterLink: {
    template: '<a><slot /></a>',
  },
  useRouter: () => ({ push }),
}))

vi.mock('@/composables/usePipelineApi', () => ({
  usePipelineApi: () => ({
    createRuleset,
  }),
}))

const uiStubs = {
  RouterLink: { template: '<a><slot /></a>' },
  Badge: { template: '<span><slot /></span>' },
  Button: {
    emits: ['click'],
    template: '<button @click="$emit(\'click\', $event)"><slot /></button>',
  },
  Input: {
    inheritAttrs: false,
    props: ['modelValue'],
    emits: ['update:modelValue'],
    template:
      '<input v-bind="$attrs" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
  },
  Textarea: {
    inheritAttrs: false,
    props: ['modelValue'],
    emits: ['update:modelValue'],
    template:
      '<textarea v-bind="$attrs" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
  },
}

describe('RulesetCreateView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('creates ruleset and redirects to ruleset library', async () => {
    createRuleset.mockResolvedValue({ id: 'rules-1', message: 'ok' })

    const wrapper = mount(RulesetCreateView, {
      global: {
        stubs: uiStubs,
      },
    })

    await wrapper.get('#ruleset-name').setValue('Noir Protocol')
    await wrapper.get('#ruleset-text').setValue('Drives:\n- Curiosity: 50')
    await wrapper.get('[data-testid="save-ruleset"]').trigger('click')
    await flushPromises()

    expect(createRuleset).toHaveBeenCalledWith({
      name: 'Noir Protocol',
      rules_text: 'Drives:\n- Curiosity: 50',
    })
    expect(push).toHaveBeenCalledWith('/library/rulesets')
  })

  it('creates ruleset from JSON mode payload', async () => {
    createRuleset.mockResolvedValue({ id: 'rules-2', message: 'ok' })

    const wrapper = mount(RulesetCreateView, {
      global: {
        stubs: uiStubs,
      },
    })

    await wrapper.get('[data-testid="ruleset-mode-json"]').trigger('click')
    await wrapper.get('[data-testid="ruleset-json"]').setValue(`{
  "ruleset": {
    "name": "Seven Minutes in Heaven",
    "rules_text": "Consent-first social scene.",
    "state_schemas": {
      "drives": [{ "name": "minutes_remaining", "range_min": 0, "range_max": 7, "default": 7, "decay_rate": 1 }],
      "skills": [{ "name": "empathy", "range_min": 0, "range_max": 20 }],
      "emotional_state": { "global_dims": [], "per_relationship": [] }
    },
    "config": {
      "time_per_turn": "1 minute"
    }
  }
}`)

    await wrapper.get('[data-testid="save-ruleset"]').trigger('click')
    await flushPromises()

    expect(createRuleset).toHaveBeenCalledWith({
      name: 'Seven Minutes in Heaven',
      rules_text: 'Consent-first social scene.',
      state_schemas: {
        drives: [{ name: 'minutes_remaining', range_min: 0, range_max: 7, default: 7, decay_rate: 1 }],
        skills: [{ name: 'empathy', range_min: 0, range_max: 20 }],
        emotional_state: { global_dims: [], per_relationship: [] },
      },
      config: {
        time_per_turn: '1 minute',
      },
    })
    expect(push).toHaveBeenCalledWith('/library/rulesets')
  })

  it('shows validation error for invalid JSON payload', async () => {
    const wrapper = mount(RulesetCreateView, {
      global: {
        stubs: uiStubs,
      },
    })

    await wrapper.get('[data-testid="ruleset-mode-json"]').trigger('click')
    await wrapper.get('[data-testid="ruleset-json"]').setValue('{ invalid json }')
    await wrapper.get('[data-testid="save-ruleset"]').trigger('click')
    await flushPromises()

    expect(createRuleset).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('Ruleset JSON is invalid.')
  })
})
