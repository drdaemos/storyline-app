import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick, ref } from 'vue'
import { useFormDraft } from './useFormDraft'

// In-memory localStorage: Node's built-in one needs a --localstorage-file flag.
const store = new Map<string, string>()

beforeEach(() => {
  store.clear()
  vi.stubGlobal('localStorage', {
    getItem: (key: string) => store.get(key) ?? null,
    setItem: (key: string, value: string) => store.set(key, value),
    removeItem: (key: string) => store.delete(key),
  })
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('useFormDraft', () => {
  it('restores a saved draft into the form on init', () => {
    store.set('test-draft', JSON.stringify({ name: 'Mara', scenes: 8 }))
    const form = ref({ name: '', synopsis: '', scenes: 6 })
    useFormDraft('test-draft', form)
    expect(form.value).toEqual({ name: 'Mara', synopsis: '', scenes: 8 })
  })

  it('saves the form whenever it changes', async () => {
    const form = ref({ name: '', scenes: 6 })
    useFormDraft('test-draft', form)
    form.value.name = 'Mara'
    await nextTick()
    expect(JSON.parse(store.get('test-draft') ?? '{}')).toEqual({ name: 'Mara', scenes: 6 })
  })

  it('keeps form defaults when the stored draft is corrupt', () => {
    store.set('test-draft', 'not json')
    const form = ref({ name: 'default' })
    useFormDraft('test-draft', form)
    expect(form.value).toEqual({ name: 'default' })
  })

  it('clearDraft removes the stored draft', async () => {
    const form = ref({ name: '' })
    const { clearDraft } = useFormDraft('test-draft', form)
    form.value.name = 'Mara'
    await nextTick()
    expect(store.has('test-draft')).toBe(true)
    clearDraft()
    expect(store.has('test-draft')).toBe(false)
  })
})
