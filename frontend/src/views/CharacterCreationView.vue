<template>
  <!-- Header -->
  <div class="flex mb-8 gap-4 items-center">
    <h2 class="text-3xl font-bold font-serif">Create New Character</h2>
  </div>

  <!-- 2 Column Layout -->
  <UMain>
    <div class="grid lg:grid-cols-2 grid-cols-1 gap-6 flex-1 pb-8">
      <!-- Left Column: AI Chat Assistant -->
      <div class="flex flex-col border border-gray-200 dark:border-gray-800 rounded-lg overflow-hidden max-h-[88vh] lg:sticky top-24">
        <div class="p-4 border-b border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-900">
          <div class="flex items-center gap-2">
            <UIcon name="i-lucide-sparkles" class="w-5 h-5 text-primary" />
            <h3 class="text-lg font-semibold">AI Assistant</h3>
          </div>
          <p class="text-sm text-gray-600 dark:text-gray-400 mt-1">
            Describe your character naturally, and I'll help build their profile.
          </p>
        </div>

        <!-- Chat Messages -->
        <div class="flex-1 overflow-y-auto p-4 space-y-4">
          <!-- Welcome message -->
          <div v-if="messages.length === 0" class="space-y-3">
            <div class="p-3 rounded-lg bg-primary/10 border border-primary/20">
              <p class="text-sm">
                Welcome! Describe the character you want to create. You can talk about their personality,
                backstory, appearance, or any other details.
              </p>
            </div>
          </div>

          <!-- Chat messages -->
          <div v-for="(message, index) in messages" :key="index" class="space-y-3">
            <div
              :class="[
                'p-3 rounded-lg max-w-[85%]',
                message.isUser
                  ? 'ml-auto bg-primary text-white'
                  : 'bg-gray-100 dark:bg-gray-800'
              ]"
            >
              <div class="flex items-start gap-2">
                <UIcon
                  :name="message.isUser ? 'i-lucide-user' : 'i-lucide-sparkles'"
                  class="w-4 h-4 mt-0.5 flex-shrink-0"
                />
                <div class="text-sm flex-1">
                  <template v-for="(segment, idx) in parseMessageSegments(message.content)" :key="idx">
                    <!-- Regular text segment -->
                    <span v-if="segment.type === 'text'" class="whitespace-pre-wrap">{{ segment.content }}</span>

                    <!-- Character update block -->
                    <div
                      v-else-if="segment.type === 'update'"
                      class="inline-flex items-center gap-2 px-3 py-1.5 my-1 rounded-md bg-primary/10 border border-primary/20 text-primary"
                    >
                      <UIcon
                        :name="segment.complete ? 'i-lucide-check-circle' : 'i-lucide-loader-circle'"
                        :class="['w-3.5 h-3.5', !segment.complete && 'animate-spin']"
                      />
                      <span class="text-xs font-medium">
                        {{ segment.complete ? 'Character updated' : 'Updating character...' }}
                      </span>
                    </div>
                  </template>
                </div>
              </div>
            </div>
          </div>

          <!-- Thinking indicator -->
          <div v-if="isThinking" class="flex items-center gap-2 text-sm text-gray-500">
            <div class="flex gap-1">
              <span class="w-2 h-2 rounded-full bg-current opacity-40 animate-pulse" style="animation-delay: 0s"></span>
              <span class="w-2 h-2 rounded-full bg-current opacity-40 animate-pulse" style="animation-delay: 0.2s"></span>
              <span class="w-2 h-2 rounded-full bg-current opacity-40 animate-pulse" style="animation-delay: 0.4s"></span>
            </div>
            <span>AI is thinking...</span>
          </div>

          <!-- Error message -->
          <div v-if="error" class="p-3 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800">
            <div class="flex items-start gap-2">
              <UIcon name="i-lucide-alert-circle" class="w-4 h-4 text-red-600 dark:text-red-400 mt-0.5" />
              <p class="text-sm text-red-600 dark:text-red-400">{{ error }}</p>
            </div>
          </div>

          <div ref="chatEndRef"></div>
        </div>

        <!-- Chat Input -->
        <div class="p-4 border-t border-gray-200 dark:border-gray-800">
          <form @submit.prevent="sendMessage" class="flex gap-2">
            <UInput
              v-model="userInput"
              placeholder="Describe your character..."
              :disabled="isThinking"
              class="flex-1"
              size="lg"
            />
            <UButton
              type="submit"
              color="primary"
              icon="i-lucide-send"
              :disabled="isThinking || !userInput.trim()"
              :loading="isThinking"
            />
          </form>
        </div>
      </div>

      <!-- Right Column: Character Sheet -->
      <div class="overflow-y-auto">
        <h2 class="text-lg font-semibold mb-2 font-serif">Character card</h2>
          <div class="flex items-center gap-3 mb-6">
            <div class="flex-1 space-y-2">
              <UFormField>
                <UInput
                  v-model="characterData.name"
                  placeholder="Jane Doe..."
                  size="lg"
                  variant="ghost"
                  class="w-full"
                />
              </UFormField>
              <UFormField>
                <UInput
                  v-model="characterData.tagline"
                  placeholder="e.g., 'A whisper in the wind, a shadow in the night.'"
                  variant="ghost"
                  class="w-full"
                />
              </UFormField>
            </div>
            <div class="w-20 h-20 rounded-lg bg-gray-100 dark:bg-gray-800 flex items-center justify-center overflow-hidden">
              <UIcon v-if="!characterData.appearance" name="i-lucide-user" class="w-10 h-10 text-gray-400" />
              <img v-else :src="characterData.appearance" alt="Character" class="w-full h-full object-cover" />
            </div>
          </div>

          <div class="space-y-6">
            <!-- Backstory Section -->
            <div>
              <h3 class="text-md font-semibold mb-2 font-serif">Backstory</h3>
              <UFormField>
                <UTextarea
                  v-model="characterData.backstory"
                  :rows="4"
                  autoresize 
                  variant="ghost"
                  class="w-full"
                  placeholder="Character's history and background..."
                />
              </UFormField>
            </div>

            <!-- Personality Section -->
            <div>
              <h3 class="text-md font-semibold mb-2 font-serif">Personality</h3>
              <UFormField>
                <UTextarea
                  v-model="characterData.personality"
                  :rows="4"
                  autoresize 
                  variant="ghost"
                  class="w-full"
                  placeholder="Personality traits and characteristics..."
                />
              </UFormField>
            </div>

            <!-- Appearance Section -->
            <div>
              <h3 class="text-md font-semibold mb-2 font-serif">Appearance</h3>
              <UFormField>
                <UTextarea
                  v-model="characterData.appearance"
                  :rows="4"
                  autoresize 
                  variant="ghost"
                  class="w-full"
                  placeholder="Physical description..."
                />
              </UFormField>
            </div>

            <!-- Relationships Section -->
            <div>
              <h3 class="text-md font-semibold mb-2 font-serif">Relationships</h3>
              <div class="space-y-3">
                <div
                  v-for="(rel, index) in relationshipsList"
                  :key="index"
                  class="p-3 border border-gray-200 dark:border-gray-800 rounded-lg space-y-2"
                >
                  <div class="flex gap-2 items-start">
                    <UFormField label="Name" class="flex-1">
                      <UInput
                        v-model="rel.name"
                        placeholder="Character name"
                      />
                    </UFormField>
                    <UButton
                      color="neutral"
                      variant="ghost"
                      icon="i-lucide-x"
                      size="sm"
                      class="mt-6"
                      @click="removeRelationship(index)"
                    />
                  </div>
                  <UFormField label="Description">
                    <UTextarea
                      v-model="rel.description"
                      :rows="2"
                      autoresize
                      variant="ghost"
                      class="w-full"
                      placeholder="Describe the relationship..."
                    />
                  </UFormField>
                </div>
              </div>
              <UButton
                color="neutral"
                variant="outline"
                icon="i-lucide-plus"
                size="sm"
                class="mt-2"
                @click="addRelationship"
              >
                Add Relationship
              </UButton>
            </div>

            <!-- World Building Section -->
            <div>
              <h3 class="text-md font-semibold mb-3 font-serif">World setting</h3>

              <!-- Setting Description -->
              <div class="mb-4">
                <UFormField>
                  <UTextarea
                    v-model="characterData.setting_description"
                    :rows="4"
                    autoresize 
                    variant="ghost"
                    class="w-full"
                    placeholder="Description of the world/setting..."
                  />
                </UFormField>
              </div>

              <!-- Key Locations -->
              <div>
                <h3 class="text-md font-semibold mb-3 font-serif">Key locations</h3>
                <UFormField>
                  <div class="space-y-4">
                    <div
                      v-for="(location, index) in characterData.key_locations"
                      :key="index"
                      class="flex gap-2"
                    >
                      <UInput
                        v-model="characterData.key_locations[index]"
                        :placeholder="`Location ${index + 1}`"
                        class="flex-1"
                      />
                      <UButton
                        color="neutral"
                        variant="ghost"
                        icon="i-lucide-x"
                        size="sm"
                        @click="removeLocation(index)"
                      />
                    </div>
                  </div>
                </UFormField>
                <UButton
                  v-if="(characterData.key_locations?.length || 0) < 10"
                  color="neutral"
                  variant="outline"
                  icon="i-lucide-plus"
                  size="sm"
                  class="mt-3"
                  @click="addLocation"
                >
                  Add Location
                </UButton>
              </div>

              <div>
              </div>
            </div>
          </div>

          <div class="flex gap-3 justify-end">
            <UButton
              color="neutral"
              variant="outline"
              @click="navigateBack"
            >
              Cancel
            </UButton>
            <UButton
              color="primary"
              :disabled="!isCharacterValid || saving"
              :loading="saving"
              @click="saveCharacter"
            >
              Create Character
            </UButton>
          </div>
      </div>
    </div>
  </UMain>
</template>

<script setup lang="ts">
import { ref, computed, reactive, nextTick, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useApi } from '@/composables/useApi'
import { useLocalSettings } from '@/composables/useLocalSettings'
import type { Character, ChatMessage, CharacterCreationRequest } from '@/types'

const router = useRouter()
const { streamCharacterCreation, createCharacter } = useApi()
const { settings } = useLocalSettings()

const userInput = ref('')
const messages = ref<ChatMessage[]>([])
const isThinking = ref(false)
const error = ref('')
const saving = ref(false)
const chatEndRef = ref<HTMLElement | null>(null)

interface RelationshipItem {
  name: string
  description: string
}

const characterData = reactive<Partial<Character>>({
  name: '',
  tagline: '',
  backstory: '',
  personality: '',
  appearance: '',
  relationships: {},
  key_locations: [],
  setting_description: '',
})

const relationshipsList = ref<RelationshipItem[]>([])

// Watch for relationships changes and sync with characterData
watch(relationshipsList, (newList) => {
  const relationshipsObj: Record<string, string> = {}
  newList.forEach((rel) => {
    if (rel.name.trim() && rel.description.trim()) {
      relationshipsObj[rel.name.trim()] = rel.description.trim()
    }
  })
  characterData.relationships = relationshipsObj
}, { deep: true })

// Watch for characterData.relationships changes from AI and sync with list
watch(() => characterData.relationships, (newRelationships) => {
  if (newRelationships) {
    const newList = Object.entries(newRelationships).map(([name, description]) => ({
      name,
      description,
    }))

    // Only update if different to avoid infinite loop
    if (JSON.stringify(newList) !== JSON.stringify(relationshipsList.value)) {
      relationshipsList.value = newList
    }
  }
}, { deep: true })

const isCharacterValid = computed(() => {
  return true
})

const navigateBack = () => {
  router.push('/')
}

const scrollToBottom = () => {
  nextTick(() => {
    chatEndRef.value?.scrollIntoView({ behavior: 'smooth' })
  })
}

const sendMessage = async () => {
  if (!userInput.value.trim() || isThinking.value) return

  const message = userInput.value.trim()

  // Add user message to chat
  messages.value.push({
    author: 'User',
    content: message,
    isUser: true,
    timestamp: new Date(),
  })

  userInput.value = ''
  isThinking.value = true
  error.value = ''
  // scrollToBottom()

  try {
    const payload: CharacterCreationRequest = {
      user_message: message,
      current_character: characterData,
      conversation_history: messages.value.map(msg => ({
        author: msg.author,
        content: msg.content,
        is_user: msg.isUser
      })),
      processor_type: settings.value.aiProcessor,
      backup_processor_type: settings.value.backupProcessor,
    }

    // Create a temporary AI message that will be updated in real-time
    const aiMessageIndex = messages.value.length

    await streamCharacterCreation(
      payload,
      // onMessage callback
      (messageChunk: string) => {
        if (!messages.value[aiMessageIndex]) {
          messages.value.push({
            author: 'AI Assistant',
            content: '',
            isUser: false,
            timestamp: new Date(),
          })
        }
        // Update the AI message content in real-time
        messages.value[aiMessageIndex].content += messageChunk
        isThinking.value = false
      },
      // onUpdate callback
      (updates: Partial<Character>) => {
        // Merge updates into characterData
        Object.assign(characterData, updates)
      },
      // onComplete callback
      () => {
        // Remove empty message if no content was received
        if (!messages.value[aiMessageIndex].content) {
          messages.value.splice(aiMessageIndex, 1)
        }
        isThinking.value = false
      },
      // onError callback
      (errorMessage: string) => {
        error.value = errorMessage
        // Remove the empty AI message on error
        messages.value.splice(aiMessageIndex, 1)
        isThinking.value = false
      }
    )
  } catch (err) {
    console.error('Failed to send message:', err)
    error.value = 'Failed to send message. Please try again.'
    isThinking.value = false
  }
}

const saveCharacter = async () => {
  if (!isCharacterValid.value) return

  saving.value = true
  try {
    await createCharacter({
      data: characterData as Character,
      is_yaml_text: false,
    })

    // Navigate back with success
    router.push('/')
  } catch (err) {
    error.value = (err as any)?.message || 'Failed to create character'
  } finally {
    saving.value = false
  }
}

const addRelationship = () => {
  relationshipsList.value.push({ name: '', description: ''})
}

const removeRelationship = (index: number) => {
  relationshipsList.value.splice(index, 1)
}

const addLocation = () => {
  if (!characterData.key_locations) {
    characterData.key_locations = []
  }
  if (characterData.key_locations.length < 10) {
    characterData.key_locations.push('')
  }
}

const removeLocation = (index: number) => {
  characterData.key_locations?.splice(index, 1)
}

interface MessageSegment {
  type: 'text' | 'update'
  content: string
  complete: boolean
}

const parseMessageSegments = (content: string): MessageSegment[] => {
  if (!content) return []

  const segments: MessageSegment[] = []

  // Split by <character_update> tags and track positions
  const parts = content.split(/(<character_update>[\s\S]*?(?:<\/character_update>|$))/g)

  for (const part of parts) {
    if (!part) continue

    // Check if this part is a character update block
    if (part.startsWith('<character_update>')) {
      const hasClosingTag = part.includes('</character_update>')
      segments.push({
        type: 'update',
        content: '', // We don't need the actual content for display
        complete: hasClosingTag,
      })
    } else {
      // Regular text
      segments.push({
        type: 'text',
        content: part,
        complete: true,
      })
    }
  }

  return segments
}
</script>
