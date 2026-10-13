/** The files the book shows: the script, the lore index and single lore files. Read-only, read again on request. */
import { reactive, ref, watch } from 'vue'
import type { Ref } from 'vue'
import { ApiError, describeError, listLore, readLore, readScript } from '@/api/client'
import type { Activity, LoreFileSummary } from '@/protocol/types'

export type LoadStatus = 'loading' | 'ready' | 'missing' | 'error'

export interface Loaded {
  status: LoadStatus
  text: string
  error: string | null
}

export interface StoryFilesInput {
  story: Ref<string>
  activity: Ref<Activity>
  scriptRevision: Ref<number>
  loreRevision: Ref<number>
}

/** The three lore files with a fixed role, by the name of their book tab. */
export const ROLE_FILES = {
  plan: 'plan.md',
  style: 'style.md',
  agreement: 'collaboration.md',
} as const

function emptyLoaded(): Loaded {
  return { status: 'loading', text: '', error: null }
}

export function useStoryFiles(input: StoryFilesInput) {
  const script = ref<Loaded>(emptyLoaded())
  /** The script as it was when the writer last started a turn; what follows it is fresh ink. */
  const scriptBaseline = ref<string | null>(null)
  const loreIndex = ref<{ status: LoadStatus; files: LoreFileSummary[]; error: string | null }>({
    status: 'loading',
    files: [],
    error: null,
  })
  /** Every lore file asked for so far, by filename. */
  const loreFiles = reactive<Record<string, Loaded>>({})
  const wanted = new Set<string>()

  async function loadScript(story: string): Promise<void> {
    try {
      const { text } = await readScript(story)
      if (story !== input.story.value) return
      script.value = { status: 'ready', text, error: null }
      // A room opened mid-turn has no earlier script to compare with; the first read is the baseline.
      if (scriptBaseline.value === null && input.activity.value !== 'idle') scriptBaseline.value = text
    } catch (error) {
      if (story !== input.story.value) return
      script.value = failure(error, script.value.text)
    }
  }

  async function loadLoreIndex(story: string): Promise<void> {
    try {
      const { files } = await listLore(story)
      if (story !== input.story.value) return
      loreIndex.value = { status: 'ready', files, error: null }
    } catch (error) {
      if (story !== input.story.value) return
      loreIndex.value = { status: 'error', files: loreIndex.value.files, error: describeError(error) }
    }
  }

  async function loadLoreFile(story: string, filename: string): Promise<void> {
    try {
      const { text } = await readLore(story, filename)
      if (story !== input.story.value) return
      loreFiles[filename] = { status: 'ready', text, error: null }
    } catch (error) {
      if (story !== input.story.value) return
      loreFiles[filename] = failure(error, loreFiles[filename]?.text ?? '')
    }
  }

  function failure(error: unknown, previousText: string): Loaded {
    if (error instanceof ApiError && error.status === 404) {
      return { status: 'missing', text: '', error: null }
    }
    return { status: 'error', text: previousText, error: describeError(error) }
  }

  /** Ask for a lore file to be shown; it is read now and again whenever lore changes. */
  function want(filename: string): void {
    if (wanted.has(filename)) return
    wanted.add(filename)
    loreFiles[filename] = emptyLoaded()
    void loadLoreFile(input.story.value, filename)
  }

  function reset(): void {
    script.value = emptyLoaded()
    scriptBaseline.value = null
    loreIndex.value = { status: 'loading', files: [], error: null }
    for (const key of Object.keys(loreFiles)) delete loreFiles[key]
    wanted.clear()
  }

  watch(
    input.story,
    () => {
      reset()
    },
    { flush: 'sync' }
  )

  watch(
    [input.story, input.scriptRevision],
    ([story]) => {
      if (story) void loadScript(story)
    },
    { immediate: true }
  )

  watch(
    [input.story, input.loreRevision],
    ([story]) => {
      if (!story) return
      void loadLoreIndex(story)
      for (const filename of wanted) void loadLoreFile(story, filename)
    },
    { immediate: true }
  )

  watch(input.activity, (now, before) => {
    if (before === 'idle' && now !== 'idle' && script.value.status === 'ready') {
      scriptBaseline.value = script.value.text
    }
  })

  return { script, scriptBaseline, loreIndex, loreFiles, want }
}

export type StoryFiles = ReturnType<typeof useStoryFiles>
