import { flushPromises, mount } from '@vue/test-utils'
import * as client from '@/api/client'
import ShelfView from './ShelfView.vue'

const push = vi.fn()

vi.mock('vue-router', () => ({
  useRouter: () => ({ push }),
  RouterLink: { template: '<a><slot /></a>' },
}))

vi.mock('@/api/client', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/api/client')>()),
  listStories: vi.fn(),
  listPresets: vi.fn(),
  createStory: vi.fn(),
}))

vi.mock('@/auth/AccountButton.vue', () => ({ default: { template: '<span />' } }))

const STORY = { id: 'default', title: 'A story', description: 'Anything you can imagine.' }
const MYSTERY = { id: 'mystery', title: 'A mystery', description: 'Clues and a secret.' }

async function mountShelf() {
  const wrapper = mount(ShelfView)
  await flushPromises()
  return wrapper
}

async function submit(wrapper: Awaited<ReturnType<typeof mountShelf>>) {
  await wrapper.get('#story-name').setValue('Tale')
  await wrapper.get('form').trigger('submit')
  await flushPromises()
}

beforeEach(() => {
  push.mockReset()
  vi.mocked(client.listStories).mockReset().mockResolvedValue({ stories: [], active: null })
  vi.mocked(client.listPresets).mockReset().mockResolvedValue({ presets: [STORY, MYSTERY] })
  vi.mocked(client.createStory).mockReset().mockResolvedValue({ name: 'Tale' })
})

describe('ShelfView new story form', () => {
  it('offers each kind of story with its description when there are several, the default chosen', async () => {
    const wrapper = await mountShelf()
    const radios = wrapper.findAll('input[type="radio"]')
    expect(radios).toHaveLength(2)
    expect(wrapper.text()).toContain('Clues and a secret.')
    expect((radios[0]!.element as HTMLInputElement).checked).toBe(true)
  })

  it('sends the kind the user chose', async () => {
    const wrapper = await mountShelf()
    await wrapper.findAll('input[type="radio"]')[1]!.setValue(true)
    await submit(wrapper)
    expect(client.createStory).toHaveBeenCalledWith('Tale', 'mystery')
    expect(push).toHaveBeenCalled()
  })

  it('sends the default kind when the user changes nothing', async () => {
    const wrapper = await mountShelf()
    await submit(wrapper)
    expect(client.createStory).toHaveBeenCalledWith('Tale', 'default')
  })

  it('shows no picker with one kind, and creates a default story', async () => {
    vi.mocked(client.listPresets).mockResolvedValue({ presets: [STORY] })
    const wrapper = await mountShelf()
    expect(wrapper.find('input[type="radio"]').exists()).toBe(false)
    await submit(wrapper)
    expect(client.createStory).toHaveBeenCalledWith('Tale', null)
  })

  it('still creates a default story when the kinds cannot be loaded', async () => {
    vi.mocked(client.listPresets).mockRejectedValue(new client.ApiError(500, 'Broken.'))
    const wrapper = await mountShelf()
    expect(wrapper.find('input[type="radio"]').exists()).toBe(false)
    await submit(wrapper)
    expect(client.createStory).toHaveBeenCalledWith('Tale', null)
  })
})
