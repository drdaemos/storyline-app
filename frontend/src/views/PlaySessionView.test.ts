import { flushPromises, mount } from '@vue/test-utils'
import { ref } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import PlaySessionView from './PlaySessionView.vue'

const getSessionState = vi.fn()
const getSessionCharacters = vi.fn()
const getSessionDetails = vi.fn()
const listPromptProcessors = vi.fn()
const settingsRef = ref({
  aiProcessor: 'google-flash',
  backupProcessor: 'gpt-5.2',
})
const updateSetting = vi.fn()

vi.mock('vue-router', () => ({
  useRoute: () => ({
    params: { sessionId: 'sess-42' },
  }),
}))

vi.mock('@/composables/usePipelineApi', () => ({
  usePipelineApi: () => ({
    getSessionState,
    getSessionCharacters,
    getSessionDetails,
    listPromptProcessors,
  }),
}))

vi.mock('@/composables/useAuth', () => ({
  useAuth: () => ({
    getAuthToken: vi.fn().mockResolvedValue(null),
  }),
}))

vi.mock('@/composables/useLocalSettings', () => ({
  useLocalSettings: () => ({
    settings: settingsRef,
    updateSetting,
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
  DialogClose: {
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
    settingsRef.value = {
      aiProcessor: 'google-flash',
      backupProcessor: 'gpt-5.2',
    }
    listPromptProcessors.mockResolvedValue({
      processor_types: ['google-flash', 'gpt-5.2', 'claude-sonnet', 'deepseek-v32'],
    })
    getSessionDetails.mockResolvedValue({
      session_id: 'sess-42',
      character_name: 'Session',
      message_count: 1,
      last_messages: [{ role: 'narration', content: 'Intro narration', created_at: '2026-02-16T12:00:00Z' }],
      last_message_time: '2026-02-16T12:00:00Z',
    })
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

  it('maps persisted user actions to narration history after reload', async () => {
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
      narration_history: ['Intro narration', 'Mara nods.'],
    })
    getSessionCharacters.mockResolvedValue([])
    getSessionDetails.mockResolvedValue({
      session_id: 'sess-42',
      character_name: 'Session',
      message_count: 2,
      last_messages: [
        { role: 'narration', content: 'Intro narration', created_at: '2026-02-16T12:00:00Z' },
        { role: 'user', content: 'I step closer to Mara.', created_at: '2026-02-16T12:01:00Z' },
      ],
      last_message_time: '2026-02-16T12:01:00Z',
    })

    const wrapper = mount(PlaySessionView, {
      global: { stubs: uiStubs },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('I step closer to Mara.')
    expect(wrapper.text()).toContain('Mara nods.')
  })

  it('maps first persisted narration to user input when no intro exists', async () => {
    getSessionState.mockResolvedValue({
      session_id: 'sess-42',
      world_state: {
        location: 'Dock Nine',
        time: '01:20',
        characters_present: ['Mara'],
      },
      turn_counter: 1,
      status: 'active',
      character_states: {},
      narration_history: ['Mara watches the torchlight flicker.'],
    })
    getSessionCharacters.mockResolvedValue([])
    getSessionDetails.mockResolvedValue({
      session_id: 'sess-42',
      character_name: 'Session',
      message_count: 1,
      last_messages: [
        { role: 'user', content: 'I light a torch.', created_at: '2026-02-16T12:01:00Z' },
      ],
      last_message_time: '2026-02-16T12:01:00Z',
    })

    const wrapper = mount(PlaySessionView, {
      global: { stubs: uiStubs },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('I light a torch.')
    expect(wrapper.text()).not.toContain('Session intro')
  })

  it('renders narration with assistant markdown formatting', async () => {
    getSessionState.mockResolvedValue({
      session_id: 'sess-42',
      world_state: {
        location: 'Dock Nine',
        time: '01:20',
        characters_present: ['Mara'],
      },
      turn_counter: 1,
      status: 'active',
      character_states: {},
      narration_history: ['A **bold** move.\n`quiet` signal.'],
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

    expect(wrapper.html()).toContain('<strong>bold</strong>')
    expect(wrapper.html()).toContain('<code')
    expect(wrapper.html()).toContain('<br>')
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

  it('uses updated processor settings on subsequent turns', async () => {
    const encoder = new TextEncoder()
    const buildSseResponse = (events: unknown[]) => {
      const stream = new ReadableStream<Uint8Array>({
        start(controller) {
          for (const event of events) {
            controller.enqueue(encoder.encode(`data: ${JSON.stringify(event)}\n\n`))
          }
          controller.close()
        },
      })
      return new Response(stream, {
        status: 200,
        headers: { 'Content-Type': 'text/event-stream' },
      })
    }

    getSessionState.mockResolvedValue({
      session_id: 'sess-42',
      world_state: { location: 'Dock Nine', time: '01:20', characters_present: [] },
      turn_counter: 0,
      status: 'active',
      character_states: {},
      narration_history: [],
    })
    getSessionCharacters.mockResolvedValue([])

    const fetchMock = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValue(buildSseResponse([{ type: 'narration_complete', text: 'Turn complete' }]))

    const wrapper = mount(PlaySessionView, {
      global: {
        stubs: uiStubs,
      },
    })

    await flushPromises()

    const input = wrapper.find('input#play-input')
    const actButton = wrapper
      .findAll('button')
      .find((button) => button.text().trim().startsWith('Act'))
    expect(actButton).toBeTruthy()

    await input.setValue('First action')
    await actButton?.trigger('click')
    await flushPromises()

    const firstPayload = JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body))
    expect(firstPayload.processor_type).toBe('google-flash')
    expect(firstPayload.mini_processor_type).toBe('gpt-5.2')

    settingsRef.value.aiProcessor = 'claude-sonnet'
    settingsRef.value.backupProcessor = 'deepseek-v32'

    await input.setValue('Second action')
    await actButton?.trigger('click')
    await flushPromises()

    const secondPayload = JSON.parse(String(fetchMock.mock.calls[1]?.[1]?.body))
    expect(secondPayload.processor_type).toBe('claude-sonnet')
    expect(secondPayload.mini_processor_type).toBe('deepseek-v32')

    fetchMock.mockRestore()
  })

  it('renders streamed narration from CRLF SSE lines', async () => {
    const encoder = new TextEncoder()
    const buildCrLfSseResponse = (events: unknown[]) => {
      const stream = new ReadableStream<Uint8Array>({
        start(controller) {
          for (const event of events) {
            controller.enqueue(encoder.encode(`data: ${JSON.stringify(event)}\r\n`))
          }
          controller.close()
        },
      })
      return new Response(stream, {
        status: 200,
        headers: { 'Content-Type': 'text/event-stream' },
      })
    }

    getSessionState
      .mockResolvedValueOnce({
        session_id: 'sess-42',
        world_state: { location: 'Dock Nine', time: '01:20', characters_present: [] },
        turn_counter: 0,
        status: 'active',
        character_states: {},
        narration_history: [],
      })
      .mockRejectedValueOnce(new Error('refresh failed'))
    getSessionCharacters
      .mockResolvedValueOnce([])
      .mockRejectedValueOnce(new Error('refresh failed'))
    getSessionDetails
      .mockResolvedValueOnce({
        session_id: 'sess-42',
        character_name: 'Session',
        message_count: 1,
        last_messages: [{ role: 'narration', content: 'Intro narration', created_at: '2026-02-16T12:00:00Z' }],
        last_message_time: '2026-02-16T12:00:00Z',
      })
      .mockRejectedValueOnce(new Error('refresh failed'))

    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      buildCrLfSseResponse([
        { type: 'narration_chunk', text: 'Turn ' },
        { type: 'narration_chunk', text: 'complete' },
        { type: 'narration_complete', text: 'Turn complete' },
      ])
    )

    const wrapper = mount(PlaySessionView, { global: { stubs: uiStubs } })
    await flushPromises()

    const input = wrapper.find('input#play-input')
    const actButton = wrapper
      .findAll('button')
      .find((button) => button.text().trim().startsWith('Act'))
    expect(actButton).toBeTruthy()

    await input.setValue('Test action')
    await actButton?.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Turn complete')
    fetchMock.mockRestore()
  })

  it('processes SSE events delivered in final done chunk', async () => {
    const encoder = new TextEncoder()
    getSessionState
      .mockResolvedValueOnce({
        session_id: 'sess-42',
        world_state: { location: 'Dock Nine', time: '01:20', characters_present: [] },
        turn_counter: 0,
        status: 'active',
        character_states: {},
        narration_history: [],
      })
      .mockRejectedValueOnce(new Error('refresh failed'))
    getSessionCharacters
      .mockResolvedValueOnce([])
      .mockRejectedValueOnce(new Error('refresh failed'))
    getSessionDetails
      .mockResolvedValueOnce({
        session_id: 'sess-42',
        character_name: 'Session',
        message_count: 1,
        last_messages: [{ role: 'narration', content: 'Intro narration', created_at: '2026-02-16T12:00:00Z' }],
        last_message_time: '2026-02-16T12:00:00Z',
      })
      .mockRejectedValueOnce(new Error('refresh failed'))

    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      body: {
        getReader: () => ({
          read: vi.fn().mockResolvedValueOnce({
            done: true,
            value: encoder.encode(
              [
                `data: ${JSON.stringify({ type: 'narration_chunk', text: 'Final ' })}`,
                `data: ${JSON.stringify({ type: 'narration_complete', text: 'Final turn' })}`,
                '',
              ].join('\n')
            ),
          }),
        }),
      },
    } as unknown as Response)

    const wrapper = mount(PlaySessionView, { global: { stubs: uiStubs } })
    await flushPromises()

    const input = wrapper.find('input#play-input')
    const actButton = wrapper
      .findAll('button')
      .find((button) => button.text().trim().startsWith('Act'))
    expect(actButton).toBeTruthy()

    await input.setValue('Test action')
    await actButton?.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Final turn')
    fetchMock.mockRestore()
  })
})
