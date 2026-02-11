<template>
  <section class="space-y-6">
    <div class="story-panel p-5 md:p-7">
      <div class="flex gap-4 items-center justify-between flex-wrap">
        <div class="flex items-center gap-3">
          <UButton color="neutral" variant="ghost" icon="i-lucide-arrow-left" @click="navigateBack" />
          <div>
            <h2 class="text-3xl story-headline">{{ isEditMode ? 'Edit World Lore' : 'Create World Lore' }}</h2>
            <p class="text-sm story-subtext mt-1">AI-assisted lore authoring with reusable tags and retrieval keywords.</p>
          </div>
        </div>
        <div class="flex items-center gap-3">
          <div v-if="autoSaveStatus !== 'idle'" class="flex items-center gap-2 text-sm story-subtext">
            <UIcon
              :name="autoSaveStatus === 'saving' ? 'i-lucide-loader-circle' : 'i-lucide-check-circle'"
              :class="['w-4 h-4', autoSaveStatus === 'saving' && 'animate-spin']"
            />
            <span>{{ autoSaveStatus === 'saving' ? 'Saving...' : 'Saved' }}</span>
          </div>
          <UButton color="neutral" variant="ghost" icon="i-lucide-refresh-cw" :disabled="isThinking || saving" @click="resetWorldLoreCreation">
            Reset
          </UButton>
        </div>
      </div>
    </div>

    <UMain>
      <div class="grid lg:grid-cols-2 grid-cols-1 gap-6 flex-1 pb-8">
        <div class="flex flex-col story-panel overflow-hidden max-h-[88vh] lg:sticky top-24">
          <div class="p-4 border-b border-gray-200/70 dark:border-gray-800 bg-cyan-50/70 dark:bg-gray-900">
            <div class="flex items-center gap-2">
              <UIcon name="i-lucide-sparkles" class="w-5 h-5 text-primary" />
              <h3 class="text-lg font-semibold">AI Worldbuilding Assistant</h3>
            </div>
            <p class="text-sm story-subtext mt-1">Describe setting, institutions, tensions, and style. The assistant updates fields as you iterate.</p>
          </div>

          <div class="flex-1 overflow-y-auto p-4 space-y-4">
            <div v-if="messages.length === 0" class="space-y-3">
              <div class="p-3 rounded-lg bg-primary/10 border border-primary/20">
                <p class="text-sm">Start with a quick pitch. Example: "Neon port city run by trade guilds, ritualized duels, rain-soaked noir tone."</p>
              </div>
            </div>

            <div v-for="(message, index) in messages" :key="index" class="space-y-3">
              <div :class="['p-3 rounded-lg max-w-[85%]', message.isUser ? 'ml-auto bg-primary text-white' : 'bg-gray-100 dark:bg-gray-800']">
                <div class="flex items-start gap-2">
                  <UIcon :name="message.isUser ? 'i-lucide-user' : 'i-lucide-sparkles'" class="w-4 h-4 mt-0.5 flex-shrink-0" />
                  <div class="text-sm flex-1">
                    <template v-for="(segment, idx) in parseMessageSegments(message.content)" :key="idx">
                      <span v-if="segment.type === 'text'" class="whitespace-pre-wrap">{{ segment.content }}</span>
                      <div
                        v-else-if="segment.type === 'update'"
                        class="inline-flex items-center gap-2 px-3 py-1.5 my-1 rounded-md bg-primary/10 border border-primary/20 text-primary"
                      >
                        <UIcon
                          :name="segment.complete ? 'i-lucide-check-circle' : 'i-lucide-loader-circle'"
                          :class="['w-3.5 h-3.5', !segment.complete && 'animate-spin']"
                        />
                        <span class="text-xs font-medium">{{ segment.complete ? 'World lore updated' : 'Updating world lore...' }}</span>
                      </div>
                    </template>
                  </div>
                </div>
              </div>
            </div>

            <div v-if="isThinking" class="flex items-center gap-2 text-sm story-subtext">
              <div class="flex gap-1">
                <span class="w-2 h-2 rounded-full bg-current opacity-40 animate-pulse" style="animation-delay: 0s"></span>
                <span class="w-2 h-2 rounded-full bg-current opacity-40 animate-pulse" style="animation-delay: 0.2s"></span>
                <span class="w-2 h-2 rounded-full bg-current opacity-40 animate-pulse" style="animation-delay: 0.4s"></span>
              </div>
              <span>AI is thinking...</span>
            </div>

            <div v-if="error" class="p-3 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800">
              <div class="flex items-start gap-2">
                <UIcon name="i-lucide-alert-circle" class="w-4 h-4 text-red-600 dark:text-red-400 mt-0.5" />
                <p class="text-sm text-red-600 dark:text-red-400">{{ error }}</p>
              </div>
            </div>
          </div>

          <div class="p-4 border-t border-gray-200 dark:border-gray-800">
            <form @submit.prevent="sendMessage" class="flex gap-2">
              <UInput v-model="userInput" placeholder="Describe or refine the world..." :disabled="isThinking" class="flex-1" size="lg" />
              <UButton type="submit" color="primary" icon="i-lucide-send" :disabled="isThinking || !userInput.trim()" :loading="isThinking" />
            </form>
          </div>
        </div>

        <div class="overflow-y-auto story-panel p-5 md:p-6">
          <h2 class="text-xl story-headline mb-4">World Lore Entry</h2>

          <div class="space-y-5">
            <UFormField label="Name">
              <UInput v-model="worldLoreData.name" class="w-full" placeholder="e.g., Neon Harbor, Alt 1998" size="lg" variant="ghost" />
            </UFormField>

            <UFormField label="Lore Text">
              <UTextarea
                v-model="worldLoreData.lore_text"
                class="w-full"
                :rows="8"
                autoresize
                variant="ghost"
                placeholder="Core world facts, institutions, social norms, tone, constraints, and conflict vectors..."
              />
            </UFormField>

            <UFormField label="Tags">
              <UInput v-model="tagsInput" class="w-full" variant="ghost" placeholder="Comma-separated tags, e.g. cyberpunk, noir, political" @blur="syncTagsFromInput" />
              <p class="text-xs story-subtext mt-2">Used for UI filtering in the world lore library.</p>
            </UFormField>

            <UFormField label="Keywords">
              <UInput v-model="keywordsInput" class="w-full" variant="ghost" placeholder="Comma-separated retrieval keywords and aliases" @blur="syncKeywordsFromInput" />
              <p class="text-xs story-subtext mt-2">Optimized for future dynamic search/vector retrieval.</p>
            </UFormField>
          </div>

          <div class="flex gap-3 justify-end mt-6 pt-6 border-t border-gray-200/70 dark:border-gray-800">
            <UButton color="neutral" variant="outline" @click="navigateBack">Cancel</UButton>
            <UButton color="primary" :disabled="!isWorldLoreValid || saving" :loading="saving" @click="saveCurrentWorldLore">
              {{ isEditMode ? 'Update Lore' : 'Save Lore' }}
            </UButton>
          </div>
        </div>
      </div>
    </UMain>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useApi } from '@/composables/useApi'
import { useLocalSettings } from '@/composables/useLocalSettings'
import { useCharacterCreationAutoSave } from '@/composables/useCharacterCreationAutoSave'
import type { ChatMessage, PartialWorldLore, SaveWorldLoreRequest, WorldLoreAsset, WorldLoreCreationRequest } from '@/types'

const router = useRouter()
const route = useRoute()
const { streamWorldLoreCreation, saveWorldLore, getWorldLore } = useApi()
const { settings } = useLocalSettings()

const editId = computed(() => {
  const id = route.query.id
  return typeof id === 'string' && id.trim() ? id : null
})
const isEditMode = computed(() => !!editId.value)

const userInput = ref('')
const messages = ref<ChatMessage[]>([])
const isThinking = ref(false)
const saving = ref(false)
const error = ref('')

const worldLoreData = reactive<Required<PartialWorldLore>>({
  name: '',
  lore_text: '',
  tags: [],
  keywords: [],
})

const tagsInput = ref('')
const keywordsInput = ref('')

const { autoSaveStatus, saveToLocalStorage, loadFromLocalStorage, clearLocalStorage } =
  useCharacterCreationAutoSave(worldLoreData as Record<string, unknown>, messages, 'world-lore-creation')

const isWorldLoreValid = computed(() => worldLoreData.name.trim().length > 0 && worldLoreData.lore_text.trim().length > 0)

const normalizeTerms = (value: string): string[] => {
  const terms = value
    .split(',')
    .map(v => v.trim())
    .filter(Boolean)
  return terms.filter((term, index) => terms.indexOf(term) === index)
}

const syncTagsFromInput = () => {
  worldLoreData.tags = normalizeTerms(tagsInput.value)
}

const syncKeywordsFromInput = () => {
  worldLoreData.keywords = normalizeTerms(keywordsInput.value)
}

watch(() => worldLoreData.tags, (tags) => {
  tagsInput.value = tags.join(', ')
}, { deep: true, immediate: true })

watch(() => worldLoreData.keywords, (keywords) => {
  keywordsInput.value = keywords.join(', ')
}, { deep: true, immediate: true })

const navigateBack = () => {
  router.push({ name: 'library-world-lore' })
}

const resetWorldLoreCreation = async () => {
  worldLoreData.name = ''
  worldLoreData.lore_text = ''
  worldLoreData.tags = []
  worldLoreData.keywords = []
  messages.value = []
  error.value = ''

  if (isEditMode.value && editId.value) {
    try {
      const existing = await getWorldLore(editId.value)
      applyWorldLore(existing)
    } catch (_err) {
      error.value = 'Failed to reload world lore data.'
    }
    return
  }

  clearLocalStorage()
}

const applyWorldLore = (lore: PartialWorldLore | WorldLoreAsset) => {
  worldLoreData.name = lore.name || ''
  worldLoreData.lore_text = lore.lore_text || ''
  worldLoreData.tags = [...(lore.tags || [])]
  worldLoreData.keywords = [...(lore.keywords || [])]
}

const sendMessage = async () => {
  if (!userInput.value.trim() || isThinking.value) return

  const message = userInput.value.trim()
  messages.value.push({
    author: 'User',
    content: message,
    isUser: true,
    timestamp: new Date(),
  })

  userInput.value = ''
  isThinking.value = true
  error.value = ''

  const payload: WorldLoreCreationRequest = {
    user_message: message,
    current_world_lore: worldLoreData,
    conversation_history: messages.value.map(msg => ({
      author: msg.author,
      content: msg.content,
      is_user: msg.isUser,
    })),
    processor_type: settings.value.largeModelKey,
    backup_processor_type: settings.value.smallModelKey,
  }

  const aiMessageIndex = messages.value.length

  try {
    await streamWorldLoreCreation(
      payload,
      (messageChunk: string) => {
        if (!messages.value[aiMessageIndex]) {
          messages.value.push({
            author: 'AI Assistant',
            content: '',
            isUser: false,
            timestamp: new Date(),
          })
        }
        messages.value[aiMessageIndex].content += messageChunk
        isThinking.value = false
      },
      (updates: PartialWorldLore) => {
        applyWorldLore(updates)
      },
      () => {
        if (!messages.value[aiMessageIndex]?.content) {
          messages.value.splice(aiMessageIndex, 1)
        }
        isThinking.value = false
        saveToLocalStorage()
      },
      (errorMessage: string) => {
        error.value = errorMessage
        messages.value.splice(aiMessageIndex, 1)
        isThinking.value = false
      }
    )
  } catch (_err) {
    error.value = 'Failed to send message. Please try again.'
    isThinking.value = false
  }
}

const saveCurrentWorldLore = async () => {
  if (!isWorldLoreValid.value) return
  saving.value = true
  error.value = ''

  syncTagsFromInput()
  syncKeywordsFromInput()

  try {
    const payload: SaveWorldLoreRequest = {
      name: worldLoreData.name.trim(),
      lore_text: worldLoreData.lore_text.trim(),
      tags: worldLoreData.tags,
      keywords: worldLoreData.keywords,
      world_lore_id: editId.value || undefined,
    }
    await saveWorldLore(payload)
    clearLocalStorage()
    router.push({ name: 'library-world-lore' })
  } catch (err) {
    const detail = err instanceof Error ? err.message : 'Unknown error'
    error.value = `Failed to save world lore: ${detail}`
  } finally {
    saving.value = false
  }
}

interface MessageSegment {
  type: 'text' | 'update'
  content: string
  complete: boolean
}

const parseMessageSegments = (content: string): MessageSegment[] => {
  if (!content) return []
  const segments: MessageSegment[] = []
  const parts = content.split(/(<world_lore_update>[\s\S]*?(?:<\/world_lore_update>|$))/g)
  for (const part of parts) {
    if (!part) continue
    if (part.startsWith('<world_lore_update>')) {
      segments.push({ type: 'update', content: '', complete: part.includes('</world_lore_update>') })
    } else {
      segments.push({ type: 'text', content: part, complete: true })
    }
  }
  return segments
}

onMounted(async () => {
  if (isEditMode.value && editId.value) {
    try {
      const existing = await getWorldLore(editId.value)
      applyWorldLore(existing)
    } catch (_err) {
      error.value = 'Failed to load existing world lore.'
    }
    return
  }
  loadFromLocalStorage()
})
</script>
