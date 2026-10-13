import { effectScope, nextTick, ref } from 'vue'
import { ApiError } from '@/api/client'
import * as client from '@/api/client'
import { freshInkStart } from '@/markdown/markdown'
import type { Activity } from '@/protocol/types'
import { useStoryFiles } from './useStoryFiles'

vi.mock('@/api/client', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/api/client')>()),
  readScript: vi.fn(),
  listLore: vi.fn(),
  readLore: vi.fn(),
}))

const readScript = vi.mocked(client.readScript)
const listLore = vi.mocked(client.listLore)
const readLore = vi.mocked(client.readLore)

async function settle(): Promise<void> {
  for (let round = 0; round < 5; round++) {
    await Promise.resolve()
    await nextTick()
  }
}

function setup() {
  const story = ref('tale')
  const activity = ref<Activity>('idle')
  const scriptRevision = ref(1)
  const loreRevision = ref(1)
  const scope = effectScope()
  const files = scope.run(() => useStoryFiles({ story, activity, scriptRevision, loreRevision }))!
  return { story, activity, scriptRevision, loreRevision, files, stop: () => scope.stop() }
}

beforeEach(() => {
  readScript.mockReset().mockResolvedValue({ text: 'One.\n' })
  listLore.mockReset().mockResolvedValue({ files: [{ filename: 'ines.md', summary: 'Keeper', keywords: null }] })
  readLore.mockReset().mockResolvedValue({ filename: 'plan.md', text: '# Plan' })
})

describe('useStoryFiles', () => {
  it('reads the script and the lore index when the room opens', async () => {
    const { files, stop } = setup()
    await settle()
    expect(files.script.value).toMatchObject({ status: 'ready', text: 'One.\n' })
    expect(files.loreIndex.value.files).toHaveLength(1)
    expect(files.scriptBaseline.value).toBeNull()
    stop()
  })

  it('reads the script again when its revision goes up', async () => {
    const { files, scriptRevision, stop } = setup()
    await settle()
    readScript.mockResolvedValue({ text: 'One.\nTwo.\n' })
    scriptRevision.value++
    await settle()
    expect(files.script.value.text).toBe('One.\nTwo.\n')
    stop()
  })

  it('remembers the script as it was when the writer starts a turn, so what follows is fresh', async () => {
    const { files, activity, scriptRevision, stop } = setup()
    await settle()
    activity.value = 'thinking'
    await settle()
    expect(files.scriptBaseline.value).toBe('One.\n')

    readScript.mockResolvedValue({ text: 'One.\nTwo.\n' })
    activity.value = 'writing'
    scriptRevision.value++
    await settle()
    expect(freshInkStart(files.scriptBaseline.value, files.script.value.text)).toBe(5)

    // The ink stays fresh after the turn ends.
    activity.value = 'idle'
    await settle()
    expect(freshInkStart(files.scriptBaseline.value, files.script.value.text)).toBe(5)

    // The next turn starts from the page as it now stands.
    activity.value = 'thinking'
    await settle()
    expect(files.scriptBaseline.value).toBe('One.\nTwo.\n')
    stop()
  })

  it('does not move the baseline while the writer changes from one activity to another', async () => {
    const { files, activity, scriptRevision, stop } = setup()
    await settle()
    activity.value = 'thinking'
    await settle()
    readScript.mockResolvedValue({ text: 'One.\nTwo.\n' })
    scriptRevision.value++
    await settle()
    activity.value = 'using_tool'
    await settle()
    expect(files.scriptBaseline.value).toBe('One.\n')
    stop()
  })

  it('reads a lore file only once it is wanted, and again when lore changes', async () => {
    const { files, loreRevision, stop } = setup()
    await settle()
    expect(readLore).not.toHaveBeenCalled()
    files.want('plan.md')
    await settle()
    expect(files.loreFiles['plan.md']).toMatchObject({ status: 'ready', text: '# Plan' })
    loreRevision.value++
    await settle()
    expect(readLore).toHaveBeenCalledTimes(2)
    stop()
  })

  it('treats a lore file that does not exist as missing, not as a failure', async () => {
    readLore.mockRejectedValue(new ApiError(404, 'No such file.'))
    const { files, stop } = setup()
    await settle()
    files.want('collaboration.md')
    await settle()
    expect(files.loreFiles['collaboration.md']).toMatchObject({ status: 'missing', error: null })
    stop()
  })

  it('reports any other failure', async () => {
    readLore.mockRejectedValue(new ApiError(500, 'The server answered 500.'))
    const { files, stop } = setup()
    await settle()
    files.want('style.md')
    await settle()
    expect(files.loreFiles['style.md']).toMatchObject({ status: 'error', error: 'The server answered 500.' })
    stop()
  })

  it('starts over when the story changes', async () => {
    const { files, story, stop } = setup()
    await settle()
    files.want('plan.md')
    await settle()
    readScript.mockResolvedValue({ text: 'Another tale.' })
    story.value = 'other'
    await settle()
    expect(files.script.value.text).toBe('Another tale.')
    expect(Object.keys(files.loreFiles)).toEqual([])
    expect(files.scriptBaseline.value).toBeNull()
    stop()
  })
})
