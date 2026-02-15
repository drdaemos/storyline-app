import { flushPromises, mount } from '@vue/test-utils'
import { ref } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ScenarioDetailView from './ScenarioDetailView.vue'

const push = vi.fn()
const getScenarioDetail = vi.fn()
const listCharacters = vi.fn()
const listPersonas = vi.fn()
const listRulesets = vi.fn()
const listWorldLore = vi.fn()
const startSession = vi.fn()

vi.mock('vue-router', () => ({
  RouterLink: {
    template: '<a><slot /></a>',
  },
  useRoute: () => ({
    params: { scenarioId: 'sc-42' },
  }),
  useRouter: () => ({ push }),
}))

vi.mock('@/composables/useLocalSettings', () => ({
  useLocalSettings: () => ({
    settings: ref({
      aiProcessor: 'google-flash',
      backupProcessor: 'gpt-5.2',
    }),
  }),
}))

vi.mock('@/composables/usePipelineApi', () => ({
  usePipelineApi: () => ({
    getScenarioDetail,
    listCharacters,
    listPersonas,
    listRulesets,
    listWorldLore,
    startSession,
  }),
}))

describe('ScenarioDetailView', () => {
  beforeEach(() => {
    vi.clearAllMocks()

    getScenarioDetail.mockResolvedValue({
      summary: 'Night Shift Audit',
      intro_message: 'Rain rattles against the station glass.',
      character_ids: ['char-1'],
      persona_id: 'persona-1',
      ruleset_id: 'rules-1',
      lore_ids: ['lore-1'],
      location: 'Dock Nine',
      time_context: '02:10',
      atmosphere: 'Cold and tense',
      plot_hooks: ['A missing ledger resurfaces.'],
      stakes: 'Exposure of a citywide cover-up',
      character_goals: {},
      potential_directions: ['Track the courier'],
    })
    listCharacters.mockResolvedValue([{ id: 'char-1', name: 'Mara', tagline: 'Detective' }])
    listPersonas.mockResolvedValue([{ id: 'persona-1', name: 'You', tagline: 'Observer' }])
    listRulesets.mockResolvedValue([
      { id: 'rules-1', name: 'Noir Rules', drive_count: 0, skill_count: 0, created_at: '' },
    ])
    listWorldLore.mockResolvedValue([
      { id: 'lore-1', name: 'Dock District', tags: ['district'], content_preview: '...' },
    ])
    startSession.mockResolvedValue({ session_id: 'sess-99' })
  })

  it('renders scenario detail and starts a new session', async () => {
    const wrapper = mount(ScenarioDetailView, {
      global: {
        stubs: {
          RouterLink: {
            template: '<a><slot /></a>',
          },
        },
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('Night Shift Audit')
    expect(wrapper.text()).toContain('Dock Nine')
    expect(wrapper.text()).toContain('Noir Rules')
    expect(wrapper.text()).toContain('Mara')

    const startButton = wrapper
      .findAll('button')
      .find((button) => button.text().trim().startsWith('Start Session'))
    expect(startButton).toBeTruthy()

    await startButton?.trigger('click')
    await flushPromises()

    expect(startSession).toHaveBeenCalledWith(
      expect.objectContaining({
        scenario_id: 'sc-42',
      })
    )
    expect(push).toHaveBeenCalledWith('/play/sess-99')
  })
})
