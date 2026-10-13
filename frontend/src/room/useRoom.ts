/** The live room of one story: its state, its connection, and the things the user can do in it. */
import { computed, onScopeDispose, ref, shallowRef, watch } from 'vue'
import type { Ref } from 'vue'
import {
  clearConversation,
  describeError,
  interrupt,
  openStory,
  sendPrompt,
  setModel,
  undoLastTurn,
} from '@/api/client'
import type { RoomStream, StreamStatus } from '@/api/sse'
import { applyEvent, applySnapshot, initialRoomState } from './roomState'
import type { RoomState } from './roomState'

export interface Connection {
  status: StreamStatus
  detail: string | null
}

export function useRoom(story: Ref<string>) {
  const state = shallowRef<RoomState>(initialRoomState(story.value))
  const connection = ref<Connection>({ status: 'connecting', detail: null })
  let stream: RoomStream | null = null

  function connect(name: string): void {
    stream?.close()
    state.value = initialRoomState(name)
    connection.value = { status: 'connecting', detail: null }
    stream = openStory(name, {
      onSnapshot: (snapshot) => {
        state.value = applySnapshot(state.value, snapshot)
      },
      onEvent: (event) => {
        state.value = applyEvent(state.value, event)
      },
      onStatus: (status, detail) => {
        connection.value = { status, detail: detail ?? null }
      },
    })
  }

  watch(story, connect, { immediate: true })
  onScopeDispose(() => stream?.close())

  function fail(error: unknown): void {
    state.value = applyEvent(state.value, { type: 'notice', level: 'error', text: describeError(error) })
  }

  async function attempt(action: () => Promise<void>): Promise<boolean> {
    try {
      await action()
      return true
    } catch (error) {
      fail(error)
      return false
    }
  }

  function setDraft(text: string): void {
    state.value = { ...state.value, draft: text }
  }

  /** Send the input to the writer, or queue it while the writer works. */
  async function send(): Promise<void> {
    const text = state.value.draft.trim()
    if (!text) return
    setDraft('')
    const sent = await attempt(() => sendPrompt(story.value, text))
    if (!sent) {
      const typedSince = state.value.draft
      setDraft(typedSince.trim() ? `${text}\n\n${typedSince}` : text)
    }
  }

  async function stop(): Promise<void> {
    await attempt(() => interrupt(story.value))
  }

  async function changeModel(modelName: string): Promise<void> {
    const name = modelName.trim()
    if (!name) return
    await attempt(() => setModel(story.value, name))
  }

  async function undo(): Promise<void> {
    await attempt(async () => {
      const { undone } = await undoLastTurn(story.value)
      if (!undone) {
        state.value = applyEvent(state.value, { type: 'notice', level: 'info', text: 'Nothing to undo.' })
      }
    })
  }

  async function clear(): Promise<void> {
    await attempt(() => clearConversation(story.value))
  }

  return {
    state: computed(() => state.value),
    connection: computed(() => connection.value),
    setDraft,
    send,
    stop,
    changeModel,
    undo,
    clear,
  }
}

export type Room = ReturnType<typeof useRoom>
