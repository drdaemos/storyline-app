import { flushPromises, mount } from '@vue/test-utils'
import { effectScope, ref } from 'vue'
import * as client from '@/api/client'
import { useStoryFiles } from '@/room/useStoryFiles'
import BookPane from './BookPane.vue'

vi.mock('@/api/client', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/api/client')>()),
  readScript: vi.fn(),
  listLore: vi.fn(),
  readLore: vi.fn(),
}))

const OWN = { filename: 'ines.md', summary: 'Keeper', keywords: null, sealed: false }
const SEALED = { filename: 'sealed/vera.md', summary: 'Who she really is', keywords: null, sealed: true }

function mountBook() {
  const scope = effectScope()
  const files = scope.run(() =>
    useStoryFiles({ story: ref('tale'), activity: ref('idle'), scriptRevision: ref(1), loreRevision: ref(1) })
  )!
  return mount(BookPane, { props: { files, activity: 'idle' } })
}

beforeEach(() => {
  vi.mocked(client.readScript).mockReset().mockResolvedValue({ text: 'One.' })
  vi.mocked(client.listLore).mockReset().mockResolvedValue({ files: [OWN, SEALED] })
  vi.mocked(client.readLore)
    .mockReset()
    .mockResolvedValue({ filename: 'sealed/vera.md', text: '# vera\n\nShe is the ferryman.' })
})

describe('BookPane sealed lore', () => {
  it('lists only own lore on the lore page', async () => {
    const wrapper = mountBook()
    await flushPromises()
    const lore = wrapper.get('#panel-lore')
    expect(lore.text()).toContain('ines')
    expect(lore.text()).not.toContain('vera')
  })

  it('shows a sealed bookmark with the count when sealed files exist', async () => {
    const wrapper = mountBook()
    await flushPromises()
    expect(wrapper.get('#tab-sealed').text()).toBe('Sealed (1)')
  })

  it('has no sealed bookmark when nothing is sealed', async () => {
    vi.mocked(client.listLore).mockResolvedValue({ files: [OWN] })
    const wrapper = mountBook()
    await flushPromises()
    expect(wrapper.find('#tab-sealed').exists()).toBe(false)
  })

  it('warns first, and reads nothing until the user chooses to peek', async () => {
    const wrapper = mountBook()
    await flushPromises()
    await wrapper.get('#tab-sealed').trigger('click')
    const panel = wrapper.get('#panel-sealed')
    expect(panel.text()).toContain('spoil')
    expect(panel.text()).not.toContain('vera')
    expect(client.readLore).not.toHaveBeenCalled()

    await panel.get('.seal__peek').trigger('click')
    expect(panel.text()).toContain('vera')
    expect(client.readLore).not.toHaveBeenCalled()

    await panel.get('button.entry').trigger('click')
    await flushPromises()
    expect(client.readLore).toHaveBeenCalledWith('tale', 'sealed/vera.md')
    expect(panel.text()).toContain('She is the ferryman.')
  })

  it('closes the seal again when the user leaves the page', async () => {
    const wrapper = mountBook()
    await flushPromises()
    await wrapper.get('#tab-sealed').trigger('click')
    await wrapper.get('#panel-sealed .seal__peek').trigger('click')
    await wrapper.get('#tab-lore').trigger('click')
    await wrapper.get('#tab-sealed').trigger('click')
    expect(wrapper.find('#panel-sealed .seal__peek').exists()).toBe(true)
  })
})
