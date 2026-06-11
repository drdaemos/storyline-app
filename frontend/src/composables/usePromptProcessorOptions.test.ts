import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const listPromptProcessors = vi.fn()

const loadComposable = async () => {
  vi.resetModules()
  vi.doMock('@/composables/usePipelineApi', () => ({
    usePipelineApi: () => ({
      listPromptProcessors,
    }),
  }))
  return import('./usePromptProcessorOptions')
}

describe('usePromptProcessorOptions', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-02-16T12:00:00Z'))
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('loads, normalizes, and merges options with current values', async () => {
    listPromptProcessors.mockResolvedValue({
      processor_types: ['google-flash', ' gpt-5.2 ', 'google-flash'],
      processor_options: [
        { id: 'google-flash', display_name: 'Gemini 3 Flash' },
        { id: ' gpt-5.2 ', display_name: ' GPT-5.2 Chat ' },
      ],
    })

    const { usePromptProcessorOptions } = await loadComposable()
    const options = usePromptProcessorOptions()

    await options.refresh()

    expect(options.processorOptions.value).toEqual([
      { id: 'google-flash', displayName: 'Gemini 3 Flash' },
      { id: 'gpt-5.2', displayName: 'GPT-5.2 Chat' },
    ])
    expect(options.processorIds.value).toEqual(['google-flash', 'gpt-5.2'])
    expect(options.getOptionsWithCurrentValues(['claude-sonnet', 'gpt-5.2'])).toEqual([
      { id: 'google-flash', displayName: 'Gemini 3 Flash' },
      { id: 'gpt-5.2', displayName: 'GPT-5.2 Chat' },
      { id: 'claude-sonnet', displayName: 'claude-sonnet' },
    ])
  })

  it('uses cache within TTL and refreshes after TTL expiry', async () => {
    listPromptProcessors.mockResolvedValue({
      processor_types: ['google-flash', 'gpt-5.2'],
      processor_options: [
        { id: 'google-flash', display_name: 'Gemini 3 Flash' },
        { id: 'gpt-5.2', display_name: 'GPT-5.2 Chat' },
      ],
    })

    const { usePromptProcessorOptions } = await loadComposable()
    const options = usePromptProcessorOptions()

    await options.refresh()
    expect(listPromptProcessors).toHaveBeenCalledTimes(1)

    vi.setSystemTime(new Date('2026-02-16T12:01:00Z'))
    await options.refresh()
    expect(listPromptProcessors).toHaveBeenCalledTimes(1)

    vi.setSystemTime(new Date('2026-02-16T12:03:00Z'))
    await options.refresh()
    expect(listPromptProcessors).toHaveBeenCalledTimes(2)
  })

  it('deduplicates concurrent refresh calls', async () => {
    let resolveRequest!: (value: {
      processor_types: string[]
      processor_options: Array<{ id: string; display_name: string }>
    }) => void
    listPromptProcessors.mockImplementation(
      () =>
        new Promise<{
          processor_types: string[]
          processor_options: Array<{ id: string; display_name: string }>
        }>((resolve) => {
          resolveRequest = resolve
        })
    )

    const { usePromptProcessorOptions } = await loadComposable()
    const options = usePromptProcessorOptions()

    const first = options.refresh()
    const second = options.refresh()
    expect(listPromptProcessors).toHaveBeenCalledTimes(1)

    resolveRequest({
      processor_types: ['google-flash'],
      processor_options: [{ id: 'google-flash', display_name: 'Gemini 3 Flash' }],
    })
    await Promise.all([first, second])
    expect(options.processorOptions.value).toEqual([
      { id: 'google-flash', displayName: 'Gemini 3 Flash' },
    ])
  })

  it('falls back to IDs when legacy payload has no display names', async () => {
    listPromptProcessors.mockResolvedValue({
      processor_types: ['google-flash'],
    })

    const { usePromptProcessorOptions } = await loadComposable()
    const options = usePromptProcessorOptions()

    await options.refresh()
    expect(options.processorOptions.value).toEqual([
      { id: 'google-flash', displayName: 'google-flash' },
    ])
  })
})
