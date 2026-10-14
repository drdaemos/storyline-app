/** Keep a scroll container pinned to its end until the reader scrolls away; tell when new content waits below. */
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type { Ref, WatchSource } from 'vue'

const NEAR_END = 32

export function distanceFromEnd(element: Pick<HTMLElement, 'scrollHeight' | 'scrollTop' | 'clientHeight'>): number {
  return element.scrollHeight - element.scrollTop - element.clientHeight
}

export interface FollowScrollOptions {
  /** Pin to the end only while this is true (default: always). */
  active?: Ref<boolean>
  /** Start pinned to the end. */
  startAtEnd?: boolean
}

export function useFollowScroll(
  container: Ref<HTMLElement | null>,
  contentChanged: WatchSource,
  options: FollowScrollOptions = {}
) {
  const following = ref(options.startAtEnd ?? true)
  const unseen = ref(false)
  let observer: ResizeObserver | null = null
  /** Where the last scroll left the container, to tell the reader scrolling up from content growing. */
  let lastTop = 0

  function isActive(): boolean {
    return options.active ? options.active.value : true
  }

  function scrollToEnd(): void {
    const element = container.value
    if (!element) return
    element.scrollTop = element.scrollHeight
    lastTop = element.scrollTop
  }

  /**
   * A scroll event arrives a frame after the scroll; content that grew meanwhile leaves the end out of
   * reach without the reader moving, so only a move up stops following.
   */
  function onScroll(): void {
    const element = container.value
    if (!element) return
    const movedUp = element.scrollTop < lastTop
    lastTop = element.scrollTop
    following.value = distanceFromEnd(element) <= NEAR_END || (following.value && !movedUp)
    if (following.value) unseen.value = false
  }

  function jumpToEnd(): void {
    following.value = true
    unseen.value = false
    scrollToEnd()
  }

  watch(contentChanged, async () => {
    if (!isActive()) return
    if (following.value) {
      await nextTick()
      scrollToEnd()
    } else {
      unseen.value = true
    }
  })

  onMounted(() => {
    const element = container.value
    if (!element) return
    element.addEventListener('scroll', onScroll, { passive: true })
    if (following.value) scrollToEnd()
    if (typeof ResizeObserver !== 'undefined') {
      observer = new ResizeObserver(() => {
        if (following.value && isActive()) scrollToEnd()
      })
      // The container itself shrinks when something beside it grows, such as the agenda or the input.
      observer.observe(element)
      for (const child of Array.from(element.children)) observer.observe(child)
    }
  })

  onBeforeUnmount(() => {
    container.value?.removeEventListener('scroll', onScroll)
    observer?.disconnect()
  })

  return { following, unseen, jumpToEnd }
}
