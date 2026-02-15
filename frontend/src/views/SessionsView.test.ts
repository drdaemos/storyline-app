import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import SessionsView from './SessionsView.vue'

vi.mock('@/composables/usePipelineApi', () => ({
  usePipelineApi: () => ({
    listSessions: vi.fn().mockResolvedValue([
      {
        session_id: 'sess-1',
        character_name: 'Session',
        message_count: 12,
        last_message_time: new Date().toISOString(),
        last_character_response: 'A clue appears in the ledger.',
        scenario_name: 'Nightfall Ledger',
        turn_count: 4,
      },
    ]),
    deleteSession: vi.fn().mockResolvedValue({ message: 'ok' }),
  }),
}))

describe('SessionsView', () => {
  it('renders session cards and play entrypoint actions', async () => {
    const wrapper = mount(SessionsView, {
      global: {
        stubs: {
          RouterLink: {
            template: '<a><slot /></a>',
          },
          Teleport: true,
        },
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('Session Library')
    expect(wrapper.text()).toContain('Nightfall Ledger')
    expect(wrapper.text()).toContain('Resume')
    expect(wrapper.text()).toContain('Details')
  })
})
