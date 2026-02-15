import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import WorldLoreCreateView from './WorldLoreCreateView.vue'

const push = vi.fn()
const createWorldLore = vi.fn()
const listWorldLoreTags = vi.fn()

vi.mock('vue-router', () => ({
  RouterLink: {
    template: '<a><slot /></a>',
  },
  useRouter: () => ({ push }),
}))

vi.mock('@/composables/usePipelineApi', () => ({
  usePipelineApi: () => ({
    createWorldLore,
    listWorldLoreTags,
  }),
}))

const uiStubs = {
  RouterLink: { template: '<a><slot /></a>' },
  Badge: { template: '<span><slot /></span>' },
  Button: {
    emits: ['click'],
    template: '<button @click="$emit(\'click\', $event)"><slot /></button>',
  },
  Input: {
    inheritAttrs: false,
    props: ['modelValue'],
    emits: ['update:modelValue', 'keydown'],
    template:
      '<input v-bind="$attrs" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" @keydown="$emit(\'keydown\', $event)" />',
  },
  Textarea: {
    inheritAttrs: false,
    props: ['modelValue'],
    emits: ['update:modelValue'],
    template:
      '<textarea v-bind="$attrs" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
  },
}

describe('WorldLoreCreateView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    listWorldLoreTags.mockResolvedValue(['district', 'faction'])
  })

  it('creates world lore with parsed tags and redirects', async () => {
    createWorldLore.mockResolvedValue({ id: 'lore-1', message: 'ok' })

    const wrapper = mount(WorldLoreCreateView, {
      global: {
        stubs: uiStubs,
      },
    })

    await flushPromises()

    await wrapper.get('#lore-name').setValue('Dock Archive')
    await wrapper.get('#lore-content').setValue('Union records are hidden under sealed floors.')
    await wrapper.get('#lore-tag-input').setValue('district')
    await wrapper.get('#lore-tag-input').trigger('keydown.enter')
    await wrapper.get('#lore-tag-input').setValue('union')
    await wrapper.get('#lore-tag-input').trigger('keydown.enter')
    await wrapper.get('[data-testid="save-lore"]').trigger('click')
    await flushPromises()

    expect(createWorldLore).toHaveBeenCalledWith({
      name: 'Dock Archive',
      content: 'Union records are hidden under sealed floors.',
      tags: ['district', 'union'],
    })
    expect(push).toHaveBeenCalledWith('/library/world-lore')
  })
})
