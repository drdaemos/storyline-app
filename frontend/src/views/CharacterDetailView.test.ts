import { flushPromises, mount } from '@vue/test-utils'
import { ref } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import CharacterDetailView from './CharacterDetailView.vue'

const push = vi.fn()
const getCharacterDetail = vi.fn()
const listScenarios = vi.fn()
const listCharacterSessions = vi.fn()
const startSession = vi.fn()
const deleteScenario = vi.fn()

vi.mock('vue-router', () => ({
  RouterLink: {
    template: '<a><slot /></a>',
  },
  useRoute: () => ({
    params: { characterId: 'char-1' },
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
    getCharacterDetail,
    listScenarios,
    listCharacterSessions,
    startSession,
    deleteScenario,
  }),
}))

describe('CharacterDetailView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.spyOn(window, 'confirm').mockReturnValue(true)

    getCharacterDetail.mockResolvedValue({
      name: 'Mara',
      tagline: 'Night-shift detective',
      backstory: 'Former transit investigator turned fixer.',
      personality: 'Dry wit, disciplined, suspicious.',
      appearance: 'Long coat, old notebook, sharp gaze.',
      interests: ['records'],
      dislikes: ['bureaucrats'],
      desires: ['truth'],
      kinks: [],
      is_persona: false,
      starting_drives: { resolve: 0.9 },
      starting_skills: { inquiry: 0.8 },
      starting_emotional_state: { stress: 0.2 },
    })

    listScenarios.mockResolvedValue({
      scenarios: [
        {
          id: 'sc-1',
          summary: 'Midnight Ledger',
          character_ids: ['char-1', 'char-2'],
          ruleset_id: 'rules-1',
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        },
      ],
    })

    listCharacterSessions.mockResolvedValue([
      {
        session_id: 'sess-1',
        character_name: 'Session',
        message_count: 4,
        last_message_time: new Date().toISOString(),
        last_character_response: 'A clue appears under the rain.',
        scenario_name: 'Midnight Ledger',
        turn_count: 2,
      },
    ])

    startSession.mockResolvedValue({ session_id: 'sess-9' })
    deleteScenario.mockResolvedValue({ message: 'ok' })
  })

  it('renders character information section and related scenarios', async () => {
    const wrapper = mount(CharacterDetailView, {
      global: {
        stubs: {
          RouterLink: {
            template: '<a><slot /></a>',
          },
        },
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('Character Information')
    expect(wrapper.text()).toContain('Mara')
    expect(wrapper.text()).toContain('Former transit investigator turned fixer.')
    expect(wrapper.text()).toContain('Scenarios Featuring This Character')
    expect(wrapper.text()).toContain('Midnight Ledger')
    expect(wrapper.text()).toContain('Recent Sessions')
    expect(listCharacterSessions).toHaveBeenCalledWith('char-1', { limit: 20 })
  })

  it('starts session from scenario play action', async () => {
    const wrapper = mount(CharacterDetailView, {
      global: {
        stubs: {
          RouterLink: {
            template: '<a><slot /></a>',
          },
        },
      },
    })

    await flushPromises()

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
    expect(push).toHaveBeenCalledWith('/play/sess-9')
  })
})
