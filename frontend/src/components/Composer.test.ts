import { mount } from '@vue/test-utils'
import Composer from './Composer.vue'
import { TOUCH_SCREEN } from './useMediaQuery'

function mountComposer(props: Partial<InstanceType<typeof Composer>['$props']> = {}) {
  return mount(Composer, { props: { draft: 'Make Ines older', working: false, queue: [], ...props } })
}

/** Make `matchMedia` answer true for the given queries, as on a phone. */
function matchOnly(...queries: string[]): void {
  vi.stubGlobal('matchMedia', (query: string) => ({
    matches: queries.includes(query),
    media: query,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
  }))
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('Composer', () => {
  it('sends on Enter', async () => {
    const wrapper = mountComposer()
    await wrapper.get('textarea').trigger('keydown', { key: 'Enter' })
    expect(wrapper.emitted('send')).toHaveLength(1)
  })

  it('does not send on Shift+Enter, and leaves the key alone so a new line is made', async () => {
    const wrapper = mountComposer()
    const event = new KeyboardEvent('keydown', { key: 'Enter', shiftKey: true, cancelable: true, bubbles: true })
    wrapper.get('textarea').element.dispatchEvent(event)
    expect(wrapper.emitted('send')).toBeUndefined()
    expect(event.defaultPrevented).toBe(false)
  })

  it('holds the new line back from the textarea when Enter sends', () => {
    const wrapper = mountComposer()
    const event = new KeyboardEvent('keydown', { key: 'Enter', cancelable: true, bubbles: true })
    wrapper.get('textarea').element.dispatchEvent(event)
    expect(event.defaultPrevented).toBe(true)
  })

  it('does not send while an input method is composing', async () => {
    const wrapper = mountComposer()
    await wrapper.get('textarea').trigger('keydown', { key: 'Enter', isComposing: true })
    expect(wrapper.emitted('send')).toBeUndefined()
  })

  it('does not send an empty input', async () => {
    const wrapper = mountComposer({ draft: '  \n ' })
    await wrapper.get('textarea').trigger('keydown', { key: 'Enter' })
    await wrapper.get('form').trigger('submit')
    expect(wrapper.emitted('send')).toBeUndefined()
    expect(wrapper.get('button[type="submit"]').attributes('disabled')).toBeDefined()
  })

  it('sends when the form is submitted, as the Send button does', async () => {
    const wrapper = mountComposer()
    await wrapper.get('form').trigger('submit')
    expect(wrapper.emitted('send')).toHaveLength(1)
  })

  it('reports what is typed', async () => {
    const wrapper = mountComposer({ draft: '' })
    await wrapper.get('textarea').setValue('hello')
    expect(wrapper.emitted('update:draft')?.[0]).toEqual(['hello'])
  })

  it('offers Send and no Stop while the writer is idle', () => {
    const wrapper = mountComposer()
    expect(wrapper.get('button[type="submit"]').text()).toBe('Send')
    expect(wrapper.findAll('button').map((button) => button.text())).not.toContain('Stop')
  })

  it('offers Stop and queues on Enter while the writer works', async () => {
    const wrapper = mountComposer({ working: true })
    expect(wrapper.findAll('button').map((button) => button.text())).toContain('Stop')
    expect(wrapper.get('button[type="submit"]').text()).toBe('Queue')
    await wrapper.get('textarea').trigger('keydown', { key: 'Enter' })
    expect(wrapper.emitted('send')).toHaveLength(1)
  })

  it('asks to stop when Stop is pressed', async () => {
    const wrapper = mountComposer({ working: true })
    const stop = wrapper.findAll('button').find((button) => button.text() === 'Stop')
    await stop!.trigger('click')
    expect(wrapper.emitted('stop')).toHaveLength(1)
  })

  it('lists the prompts the writer has not read yet', () => {
    const wrapper = mountComposer({ working: true, queue: ['keep the dog', 'and the rain'] })
    const items = wrapper.findAll('.queue__item').map((item) => item.text())
    expect(items).toEqual(['keep the dog', 'and the rain'])
  })

  it('shows no queue when it is empty', () => {
    expect(mountComposer().find('.queue').exists()).toBe(false)
  })

  it('leaves Enter to start a new line on a touch screen, where the button sends', async () => {
    matchOnly(TOUCH_SCREEN)
    const wrapper = mountComposer()
    const event = new KeyboardEvent('keydown', { key: 'Enter', cancelable: true, bubbles: true })
    wrapper.get('textarea').element.dispatchEvent(event)
    expect(event.defaultPrevented).toBe(false)
    expect(wrapper.emitted('send')).toBeUndefined()
    expect(wrapper.text()).not.toContain('Enter sends')
    await wrapper.get('form').trigger('submit')
    expect(wrapper.emitted('send')).toHaveLength(1)
  })
})
