/** Close a popover on Escape or on a press outside it, and give focus back to what opened it. */
import { onBeforeUnmount, watch } from 'vue'
import type { Ref } from 'vue'

export function useDismiss(
  open: Ref<boolean>,
  root: Ref<HTMLElement | null>,
  returnFocusTo: Ref<HTMLElement | null>
): void {
  function onKeydown(event: KeyboardEvent): void {
    if (event.key !== 'Escape') return
    event.stopPropagation()
    open.value = false
    returnFocusTo.value?.focus()
  }

  function onPointerDown(event: PointerEvent): void {
    const target = event.target
    if (target instanceof Node && root.value && !root.value.contains(target)) open.value = false
  }

  function stop(): void {
    document.removeEventListener('keydown', onKeydown)
    document.removeEventListener('pointerdown', onPointerDown)
  }

  watch(open, (isOpen) => {
    stop()
    if (!isOpen) return
    document.addEventListener('keydown', onKeydown)
    document.addEventListener('pointerdown', onPointerDown)
  })

  onBeforeUnmount(stop)
}
