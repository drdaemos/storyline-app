import { mount } from '@vue/test-utils'
import { computed } from 'vue'
import { describe, expect, it, vi } from 'vitest'
import StylePreviewView from './StylePreviewView.vue'

vi.mock('@/composables/usePromptProcessorOptions', () => ({
  usePromptProcessorOptions: () => ({
    refresh: vi.fn().mockResolvedValue(undefined),
    processorOptions: computed(() => [
      { id: 'google-flash', displayName: 'Gemini 3 Flash' },
      { id: 'gpt-5.2', displayName: 'GPT-5.2 Chat' },
    ]),
  }),
}))

describe('StylePreviewView', () => {
  it('renders feature-complete prototype tabs and sections', () => {
    const wrapper = mount(StylePreviewView, {
      global: {
        stubs: {
          Teleport: true,
        },
      },
    })

    const pageText = wrapper.text()
    expect(pageText).toContain('Storyline UI Prototypes')
    expect(pageText).toContain('Typography Lab')
    expect(pageText).toContain('Heading Font')
    expect(pageText).toContain('Narrative Font')
    expect(pageText).toContain('UI Font')
    expect(pageText).toContain('Home')
    expect(pageText).toContain('Hub')
    expect(pageText).toContain('Sessions')
    expect(pageText).toContain('Play')
    expect(pageText).toContain('Creation')
    expect(pageText).toContain('Continue Playing')
    expect(pageText).toContain('Micro-Interactions')
  })

  it('uses continuation options without type legends and avoids enterprise wording', () => {
    const wrapper = mount(StylePreviewView, {
      global: {
        stubs: {
          Teleport: true,
        },
      },
    })

    const pageText = wrapper.text()
    expect(pageText).toContain('Play')
    expect(pageText).not.toContain('Continuation Legend')
    expect(pageText).not.toContain('Workspace')
    expect(pageText).not.toContain('Settings')
    expect(pageText).not.toContain('New Session')
  })

  it('renders font selectors for heading, narrative, and UI text', () => {
    const wrapper = mount(StylePreviewView, {
      global: {
        stubs: {
          Teleport: true,
        },
      },
    })

    expect(wrapper.find('[data-testid="heading-font-select"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="narrative-font-select"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="ui-font-select"]').exists()).toBe(true)
  })
})
