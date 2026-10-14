import { mount } from '@vue/test-utils'
import { defineComponent, h, nextTick, ref } from 'vue'
import { useFollowScroll } from './useFollowScroll'

/** A scroll box with sizes jsdom does not lay out: scrollTop is clamped like a browser's. */
function fakeBox(element: HTMLElement, sizes: { content: number; view: number }) {
  let top = 0
  Object.defineProperty(element, 'scrollHeight', { get: () => sizes.content })
  Object.defineProperty(element, 'clientHeight', { get: () => sizes.view })
  Object.defineProperty(element, 'scrollTop', {
    get: () => top,
    set: (value: number) => {
      top = Math.max(0, Math.min(value, sizes.content - sizes.view))
    },
  })
  return {
    scrollTo(value: number) {
      element.scrollTop = value
      element.dispatchEvent(new Event('scroll'))
    },
  }
}

function mountLog() {
  const sizes = { content: 1000, view: 400 }
  const content = ref(0)
  let box!: ReturnType<typeof fakeBox>
  let follow!: ReturnType<typeof useFollowScroll>
  const Log = defineComponent({
    setup() {
      const scroller = ref<HTMLElement | null>(null)
      follow = useFollowScroll(scroller, () => content.value)
      return () =>
        h('div', {
          ref: (element) => {
            if (element && !scroller.value) {
              box = fakeBox(element as HTMLElement, sizes)
              scroller.value = element as HTMLElement
            }
          },
        })
    },
  })
  const wrapper = mount(Log)
  return { wrapper, sizes, content, box: () => box, follow: () => follow }
}

describe('useFollowScroll', () => {
  it('keeps following when content grows before the scroll event of the last pin arrives', async () => {
    const log = mountLog()
    const element = log.wrapper.element as HTMLElement
    log.content.value++
    await nextTick()
    await nextTick()
    expect(element.scrollTop).toBe(600)
    log.sizes.content = 1400
    element.dispatchEvent(new Event('scroll'))
    expect(log.follow().following.value).toBe(true)
    log.content.value++
    await nextTick()
    await nextTick()
    expect(log.follow().unseen.value).toBe(false)
    expect(element.scrollTop).toBe(1000)
  })

  it('stops following when the reader scrolls up, and tells of new content below', async () => {
    const log = mountLog()
    log.content.value++
    await nextTick()
    await nextTick()
    log.box().scrollTo(200)
    expect(log.follow().following.value).toBe(false)
    log.content.value++
    await nextTick()
    expect(log.follow().unseen.value).toBe(true)
  })

  it('follows again once the reader scrolls back to the end', async () => {
    const log = mountLog()
    log.content.value++
    await nextTick()
    await nextTick()
    log.box().scrollTo(200)
    log.box().scrollTo(600)
    expect(log.follow().following.value).toBe(true)
  })
})
