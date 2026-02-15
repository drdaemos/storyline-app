import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import StylePreviewView from './StylePreviewView.vue'

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
})
