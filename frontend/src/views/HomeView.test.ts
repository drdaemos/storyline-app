import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import HomeView from './HomeView.vue'

vi.mock('@/composables/usePipelineApi', () => ({
  usePipelineApi: () => ({
    listSessions: vi.fn().mockResolvedValue([
      {
        session_id: 'sess-1',
        character_name: 'Session',
        message_count: 12,
        last_message_time: new Date().toISOString(),
        last_character_response: 'The rain starts over the rail yard.',
        scenario_name: 'Nightfall Ledger',
        turn_count: 4,
      },
    ]),
    listCharacters: vi.fn().mockResolvedValue([{ id: 'c1', name: 'Mara', tagline: 'Detective' }]),
    listPersonas: vi.fn().mockResolvedValue([{ id: 'p1', name: 'You', tagline: 'Investigator' }]),
    listRulesets: vi
      .fn()
      .mockResolvedValue([
        { id: 'r1', name: 'Noir', drive_count: 2, skill_count: 3, created_at: '' },
      ]),
    listWorldLore: vi
      .fn()
      .mockResolvedValue([
        { id: 'l1', name: 'Dock Nine', tags: ['district'], content_preview: '...' },
      ]),
    listScenarios: vi.fn().mockResolvedValue({ scenarios: [{ id: 's1' }] }),
  }),
}))

describe('HomeView', () => {
  it('renders dashboard sections with loaded data', async () => {
    const wrapper = mount(HomeView, {
      global: {
        stubs: {
          RouterLink: {
            template: '<a><slot /></a>',
          },
        },
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('Story Dashboard')
    expect(wrapper.text()).toContain('Continue Playing')
    expect(wrapper.text()).toContain('Nightfall Ledger')
    expect(wrapper.text()).toContain('Recent Assets')
  })
})
