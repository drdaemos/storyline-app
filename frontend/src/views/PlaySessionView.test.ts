import { flushPromises, mount } from '@vue/test-utils'
import { ref } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import PlaySessionView from './PlaySessionView.vue'

const getSessionState = vi.fn()
const getSessionCharacters = vi.fn()

vi.mock('vue-router', () => ({
  useRoute: () => ({
    params: { sessionId: 'sess-42' },
  }),
}))

vi.mock('@/composables/usePipelineApi', () => ({
  usePipelineApi: () => ({
    getSessionState,
    getSessionCharacters,
  }),
}))

vi.mock('@/composables/useAuth', () => ({
  useAuth: () => ({
    getAuthToken: vi.fn().mockResolvedValue(null),
  }),
}))

vi.mock('@/composables/useLocalSettings', () => ({
  useLocalSettings: () => ({
    settings: ref({
      aiProcessor: 'google-flash',
      backupProcessor: 'gpt-5.2',
    }),
    updateSetting: vi.fn(),
  }),
}))

const uiStubs = {
  Badge: {
    template: '<span><slot /></span>',
  },
  Button: {
    template: '<button><slot /></button>',
  },
  Dialog: {
    template: '<div><slot /></div>',
  },
  DialogContent: {
    template: '<div><slot /></div>',
  },
  DialogDescription: {
    template: '<div><slot /></div>',
  },
  DialogFooter: {
    template: '<div><slot /></div>',
  },
  DialogHeader: {
    template: '<div><slot /></div>',
  },
  DialogTitle: {
    template: '<div><slot /></div>',
  },
  DialogTrigger: {
    template: '<div><slot /></div>',
  },
  Input: {
    props: ['modelValue'],
    emits: ['update:modelValue', 'keydown'],
    template:
      '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" @keydown="$emit(\'keydown\', $event)" />',
  },
  ScrollArea: {
    template: '<div><slot /></div>',
  },
  Select: {
    template: '<div><slot /></div>',
  },
  SelectContent: {
    template: '<div><slot /></div>',
  },
  SelectItem: {
    template: '<div><slot /></div>',
  },
  SelectTrigger: {
    template: '<div><slot /></div>',
  },
  SelectValue: {
    template: '<div><slot /></div>',
  },
  Separator: {
    template: '<hr />',
  },
}

describe('PlaySessionView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders loaded state with turns and state rail', async () => {
    getSessionState.mockResolvedValue({
      session_id: 'sess-42',
      world_state: {
        location: 'Dock Nine',
        time: '01:20',
        characters_present: ['Mara'],
      },
      turn_counter: 2,
      status: 'active',
      character_states: {},
      narration_history: ['Intro narration', 'Follow-up narration'],
    })

    getSessionCharacters.mockResolvedValue([
      {
        character_id: 'char-1',
        character_name: 'Mara',
        is_present: true,
        drives: {},
        active_intent_goal: 'Recover the ledger',
      },
    ])

    const wrapper = mount(PlaySessionView, {
      global: {
        stubs: uiStubs,
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('Turn Feed')
    expect(wrapper.text()).toContain('Session intro')
    expect(wrapper.text()).toContain('Turn 1')
    expect(wrapper.text()).toContain('Dock Nine')
    expect(wrapper.text()).toContain('Mara')
  })

  it('shows load error once when initial fetch fails', async () => {
    getSessionState.mockRejectedValue(new Error('boom'))
    getSessionCharacters.mockResolvedValue([])

    const wrapper = mount(PlaySessionView, {
      global: {
        stubs: uiStubs,
      },
    })

    await flushPromises()

    const matches = wrapper.text().match(/Failed to load play session\./g) ?? []
    expect(matches).toHaveLength(1)
  })
})
