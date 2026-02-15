import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import CharacterLibraryView from './CharacterLibraryView.vue'

const listCharacters = vi.fn()
const listPersonas = vi.fn()

vi.mock('vue-router', () => ({
  RouterLink: {
    template: '<a><slot /></a>',
  },
  useRoute: () => ({
    query: {},
    path: '/library/personas',
  }),
}))

vi.mock('@/composables/usePipelineApi', () => ({
  usePipelineApi: () => ({
    listCharacters,
    listPersonas,
  }),
}))

describe('CharacterLibraryView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    listCharacters.mockResolvedValue([{ id: 'char-1', name: 'Mara', tagline: 'Detective' }])
    listPersonas.mockResolvedValue([{ id: 'persona-1', name: 'You', tagline: 'Observer' }])
  })

  it('supports persona library mode through route props', async () => {
    const wrapper = mount(CharacterLibraryView, {
      props: {
        initialFilter: 'personas',
      },
      global: {
        stubs: {
          RouterLink: {
            template: '<a><slot /></a>',
          },
        },
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('Persona Library')
    expect(wrapper.text()).toContain('You')
    expect(wrapper.text()).not.toContain('Mara')
  })
})
