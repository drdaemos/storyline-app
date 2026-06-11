<template>
  <div class="max-w-3xl mx-auto">
    <!-- Header -->
    <div class="flex items-center justify-between mb-6 gap-4">
      <div class="flex items-center gap-3">
        <UButton icon="i-lucide-arrow-left" variant="ghost" color="neutral" @click="router.push({ name: 'vn-library' })" />
        <h2 class="text-2xl font-bold font-serif">{{ session?.script_title || 'Loading…' }}</h2>
      </div>
      <div class="flex items-center gap-2">
        <USwitch v-model="narrationEnabled" label="Narration" />
        <UButton icon="i-lucide-bug" variant="ghost" color="neutral" :title="'Toggle state panel'" @click="showState = !showState" />
      </div>
    </div>

    <UAlert v-if="errorMessage" color="error" variant="soft" icon="i-lucide-alert-triangle" :description="errorMessage" class="mb-4" />

    <div class="flex gap-6">
      <!-- Story feed -->
      <div class="flex-1 space-y-4">
        <div class="prose dark:prose-invert max-w-none space-y-3">
          <template v-for="(block, index) in displayBlocks" :key="index">
            <p v-if="block.kind === 'narration'" class="whitespace-pre-wrap">{{ block.text }}</p>
            <p
              v-else
              class="text-gray-600 dark:text-gray-300"
              :class="{ 'font-semibold': block.event.type === 'scene_entered' || block.event.type === 'ending_reached', 'italic text-sm': block.event.type === 'check_resolved' || block.event.type === 'choice_made' }"
            >
              {{ describeEvent(block.event) }}
            </p>
          </template>
          <p v-if="streamingNarration" class="whitespace-pre-wrap">{{ streamingNarration }}</p>
        </div>

        <!-- Ended -->
        <UAlert
          v-if="session?.status === 'ended'"
          color="primary"
          variant="soft"
          icon="i-lucide-flag"
          title="The story has ended"
          :description="`Ending: ${session.view.ending_id}`"
        >
          <template #actions>
            <UButton variant="solid" @click="restart">Play again</UButton>
          </template>
        </UAlert>

        <!-- Pending input -->
        <VnChoiceList
          v-else-if="session"
          :pending="session.view.pending"
          :disabled="busy"
          @choose="(index) => act({ type: 'choose', option_index: index })"
          @go-deeper="act({ type: 'go_deeper' })"
          @proceed="act({ type: 'proceed' })"
        />
      </div>

      <!-- Debug state panel -->
      <UCard v-if="showState && session" class="w-64 shrink-0 self-start">
        <VnStatePanel :vars="session.view.vars" :visited="session.view.visited" :scene-id="session.view.scene_id" :beat-id="session.view.beat_id" />
      </UCard>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import VnChoiceList from '@/components/vn/VnChoiceList.vue'
import VnStatePanel from '@/components/vn/VnStatePanel.vue'
import { useVnApi } from '@/composables/useVnApi'
import { useLocalSettings } from '@/composables/useLocalSettings'
import type { VNAction, VNSessionView } from '@/types/vn'
import { buildDisplayBlocks, describeEvent } from '@/utils/vnDisplay'

const props = defineProps<{ sessionId: string }>()

const router = useRouter()
const { getSession, advanceSession, narrateSession, createSession } = useVnApi()
const { settings } = useLocalSettings()

const session = ref<VNSessionView | null>(null)
const busy = ref(false)
const errorMessage = ref('')
const showState = ref(false)
const narrationEnabled = ref(false)
const streamingNarration = ref('')

const displayBlocks = computed(() => (session.value ? buildDisplayBlocks(session.value.event_log, session.value.narration_log) : []))

const load = async () => {
  try {
    session.value = await getSession(props.sessionId)
  } catch (err) {
    errorMessage.value = err instanceof Error ? err.message : 'Failed to load session'
  }
}

const narrate = async () => {
  if (!session.value) return
  streamingNarration.value = ''
  try {
    await narrateSession(props.sessionId, settings.value.aiProcessor || 'claude-sonnet', (chunk) => {
      streamingNarration.value += chunk
    })
    // refresh to pick up the persisted narration_log, then clear the streaming buffer
    session.value = await getSession(props.sessionId)
  } catch (err) {
    errorMessage.value = err instanceof Error ? err.message : 'Narration failed'
  } finally {
    streamingNarration.value = ''
  }
}

const act = async (action: VNAction) => {
  if (busy.value) return
  busy.value = true
  errorMessage.value = ''
  try {
    session.value = await advanceSession(props.sessionId, action)
    if (narrationEnabled.value && session.value.new_events.length) {
      await narrate()
    }
  } catch (err) {
    errorMessage.value = err instanceof Error ? err.message : 'Action failed'
  } finally {
    busy.value = false
  }
}

const restart = async () => {
  if (!session.value) return
  busy.value = true
  try {
    const fresh = await createSession(session.value.script_id)
    router.push({ name: 'vn-player', params: { sessionId: fresh.session_id } })
    session.value = fresh
  } catch (err) {
    errorMessage.value = err instanceof Error ? err.message : 'Failed to restart'
  } finally {
    busy.value = false
  }
}

onMounted(async () => {
  await load()
  if (narrationEnabled.value && session.value && !session.value.narration_log.length) {
    await narrate()
  }
})
</script>
