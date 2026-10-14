/** Whether a CSS media query matches, kept up to date; false where `matchMedia` is missing. */
import { onBeforeUnmount, ref } from 'vue'
import type { Ref } from 'vue'

/** The width below which the room shows one pane at a time; the stylesheets use the same number. */
export const NARROW_SCREEN = '(max-width: 760px)'

/** A touch screen, where a soft keyboard has no Shift+Enter. */
export const TOUCH_SCREEN = '(pointer: coarse)'

export function useMediaQuery(query: string): Ref<boolean> {
  const list = typeof window.matchMedia === 'function' ? window.matchMedia(query) : null
  const matches = ref(list?.matches ?? false)
  if (list === null) return matches

  function update(event: MediaQueryListEvent): void {
    matches.value = event.matches
  }

  list.addEventListener('change', update)
  onBeforeUnmount(() => list.removeEventListener('change', update))
  return matches
}
