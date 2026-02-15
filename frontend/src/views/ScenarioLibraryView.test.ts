import { flushPromises, mount } from '@vue/test-utils'
import { ref } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ScenarioLibraryView from './ScenarioLibraryView.vue'

const push = vi.fn()
const listScenarios = vi.fn()
const listCharacters = vi.fn()
const listPersonas = vi.fn()
const listRulesets = vi.fn()
const startSession = vi.fn()

vi.mock('vue-router', () => ({
  RouterLink: {
    template: '<a><slot /></a>',
  },
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
    listScenarios,
    listCharacters,
    listPersonas,
    listRulesets,
    startSession,
  }),
}))

describe('ScenarioLibraryView', () => {
  beforeEach(() => {
    vi.clearAllMocks()

    listScenarios.mockResolvedValue({
      scenarios: [
        {
          id: 'sc-1',
          summary: 'Midnight Ledger',
          character_ids: ['char-1'],
          ruleset_id: 'rules-1',
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        },
      ],
    })
    listCharacters.mockResolvedValue([{ id: 'char-1', name: 'Mara', tagline: 'Detective' }])
    listPersonas.mockResolvedValue([])
    listRulesets.mockResolvedValue([
      { id: 'rules-1', name: 'Noir Rules', drive_count: 2, skill_count: 3, created_at: '' },
    ])
    startSession.mockResolvedValue({ session_id: 'sess-7' })
  })

  it('renders scenarios and starts a session from selected scenario', async () => {
    const wrapper = mount(ScenarioLibraryView, {
      global: {
        stubs: {
          RouterLink: {
            template: '<a><slot /></a>',
          },
        },
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('Scenario Library')
    expect(wrapper.text()).toContain('Midnight Ledger')
    expect(wrapper.text()).toContain('Noir Rules')

    const playButton = wrapper
      .findAll('button')
      .find((button) => button.text().trim().startsWith('Play'))
    expect(playButton).toBeTruthy()

    await playButton?.trigger('click')
    await flushPromises()

    expect(startSession).toHaveBeenCalledWith(
      expect.objectContaining({
        scenario_id: 'sc-1',
      })
    )
    expect(push).toHaveBeenCalledWith('/play/sess-7')
  })
})
