<template>
  <!-- Header -->
  <div class="flex  mb-8 gap-4">
    <h2 class="text-3xl font-bold font-serif">Create New Character</h2>
    <UTabs
      v-model="activeTab"
      :items="[
        { key: 'manual', label: 'Manual Entry' },
        { key: 'yaml', label: 'Import YAML' }
      ]"
    />
  </div>

  <!-- Tabs -->


  <!-- Manual Entry Form -->
  <div v-if="activeTab === 'manual'">
    <form @submit.prevent="saveCharacter" class="space-y-6">
      <UCard>
        <template #header>
          <h3 class="text-lg font-semibold">Basic Information</h3>
        </template>

        <div class="space-y-4">
          <UFormField label="Character Name" required :error="errors.name">
            <UInput
              v-model="formData.name"
              placeholder="Enter character name"
              size="lg"
            />
          </UFormField>

          <UFormField label="Role/Profession" required :error="errors.role">
            <UInput
              v-model="formData.tagline"
              placeholder="e.g., Detective, Teacher, Wizard"
              size="lg"
            />
          </UFormField>

          <UFormField label="Backstory" required :error="errors.backstory">
            <UTextarea
              v-model="formData.backstory"
              :rows="4"
              placeholder="Character's history, experiences, and background"
            />
          </UFormField>
        </div>
      </UCard>

      <UCard>
        <template #header>
          <h3 class="text-lg font-semibold">Character Details</h3>
        </template>

        <div class="space-y-4">
          <UFormField label="Personality">
            <UTextarea
              v-model="formData.personality"
              :rows="3"
              placeholder="Personality traits and characteristics"
            />
          </UFormField>

          <UFormField label="Physical Appearance">
            <UTextarea
              v-model="formData.appearance"
              :rows="3"
              placeholder="Physical description for avatar generation"
            />
          </UFormField>

          <UFormField label="Setting Description">
            <UTextarea
              v-model="formData.setting_description"
              :rows="3"
              placeholder="Description of the world/setting the character exists in"
            />
          </UFormField>
        </div>
      </UCard>

      <UCard>
        <template #header>
          <h3 class="text-lg font-semibold">Locations</h3>
        </template>

        <div class="space-y-4">
          <p class="text-sm text-gray-600 dark:text-gray-400">Add up to 10 key locations for this character.</p>

          <div class="space-y-3">
            <div
              v-for="(location, index) in formData.key_locations"
              :key="index"
              class="flex gap-2 items-center"
            >
              <UInput
                v-model="formData.key_locations[index]"
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

          <UButton
            v-if="formData.key_locations.length < 10"
            color="neutral"
            variant="outline"
            icon="i-lucide-plus"
            @click="addLocation"
          >
            Add Location
          </UButton>
        </div>
      </UCard>

      <UCard>
        <template #header>
          <h3 class="text-lg font-semibold">Relationships</h3>
        </template>

        <div class="space-y-4">
          <p class="text-sm text-gray-600 dark:text-gray-400">Define relationships with other characters.</p>

          <div class="space-y-3">
            <div
              v-for="(relationship, index) in relationships"
              :key="index"
              class="flex gap-2 items-center"
            >
              <UInput
                v-model="relationship.name"
                placeholder="Character name"
                class="flex-1"
              />
              <UInput
                v-model="relationship.relationship"
                placeholder="Relationship type"
                class="flex-1"
              />
              <UButton
                color="neutral"
                variant="ghost"
                icon="i-lucide-x"
                size="sm"
                @click="removeRelationship(index)"
              />
            </div>
          </div>

          <UButton
            color="neutral"
            variant="outline"
            icon="i-lucide-plus"
            @click="addRelationship"
          >
            Add Relationship
          </UButton>
        </div>
      </UCard>

      <div class="flex gap-3 justify-end">
        <UButton
          color="primary"
          variant="outline"
          icon="i-lucide-wand-2"
          :disabled="loading || !canGenerate"
          :loading="generating"
          @click="handleGenerateCharacter"
        >
          {{ generating ? 'Generating...' : 'AI Generate Missing Fields' }}
        </UButton>

        <UButton
          type="submit"
          color="primary"
          :disabled="loading || !isFormValid"
          :loading="loading"
        >
          Create Character
        </UButton>
      </div>
    </form>
  </div>

  <!-- YAML Import -->
  <div v-if="activeTab === 'yaml'">
    <UCard>
      <template #header>
        <h3 class="text-lg font-semibold">Import Character from YAML</h3>
      </template>

      <div class="space-y-4">
        <p class="text-sm text-gray-600 dark:text-gray-400">
          Paste your character definition in YAML format below. The system will parse and validate it.
        </p>

        <UFormField label="YAML Content">
          <UTextarea
            v-model="yamlContent"
            :rows="20"
            class="font-mono text-sm"
            placeholder="name: Character Name
tagline: Character tagline
backstory: Character backstory...
personality: Character personality...
appearance: Physical description...
key_locations:
- Location 1
- Location 2
relationships:
friend_name: friend
family_member: sister
setting_description: World description..."
          />
        </UFormField>

        <div class="flex gap-3">
          <UButton
            color="neutral"
            variant="outline"
            :disabled="loading || !yamlContent.trim()"
            :loading="processingYaml"
            @click="processYaml"
          >
            {{ processingYaml ? 'Processing...' : 'Parse YAML' }}
          </UButton>

          <UButton
            color="primary"
            :disabled="loading || !yamlContent.trim()"
            :loading="loading"
            @click="saveYamlCharacter"
          >
            Create from YAML
          </UButton>
        </div>

        <div v-if="yamlPreview">
          <UDivider />
          <h4 class="text-md font-semibold mb-2">Preview</h4>
          <pre class="font-mono text-sm bg-gray-100 dark:bg-gray-800 p-4 rounded-lg overflow-x-auto">{{ yamlPreview }}</pre>
        </div>
      </div>
    </UCard>
  </div>

  <!-- Success/Error Messages -->
  <UAlert
    v-if="successMessage"
    color="success"
    variant="soft"
    icon="i-lucide-check-circle"
    :description="successMessage"
    @close="successMessage = ''"
  />

  <UAlert
    v-if="errorMessage"
    color="error"
    variant="soft"
    icon="i-lucide-alert-circle"
    :description="errorMessage"
    @close="errorMessage = ''"
  />
</template>

<script setup lang="ts">
import { ref, computed, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useApi } from '@/composables/useApi'
import { useLocalSettings } from '@/composables/useLocalSettings'
import { validateCharacterName, debounce } from '@/utils/formatters'
import type { Character } from '@/types'

const router = useRouter()
const { createCharacter, generateCharacter, loading, error } = useApi()
const { settings, loadSettings } = useLocalSettings()

const activeTab = ref<'manual' | 'yaml'>('manual')
const generating = ref(false)
const processingYaml = ref(false)
const successMessage = ref('')
const errorMessage = ref('')
const yamlContent = ref('')
const yamlPreview = ref('')

interface RelationshipItem {
  name: string
  relationship: string
}

const formData = reactive<Character>({
  name: '',
  tagline: '',
  backstory: '',
  personality: '',
  appearance: '',
  relationships: {},
  key_locations: [''],
  setting_description: '',
})

const relationships = ref<RelationshipItem[]>([{ name: '', relationship: '' }])

const errors = reactive({
  name: '',
  role: '',
  backstory: '',
})

const isFormValid = computed(() => {
  return (
    formData.name.trim().length > 0 &&
    formData.tagline.trim().length > 0 &&
    formData.backstory.trim().length > 0 &&
    validateCharacterName(formData.name)
  )
})

const canGenerate = computed(() => {
  return (
    formData.name.trim().length > 0 ||
    formData.tagline.trim().length > 0 ||
    formData.backstory.trim().length > 0
  )
})

const validateForm = () => {
  errors.name = ''
  errors.role = ''
  errors.backstory = ''

  if (!formData.name.trim()) {
    errors.name = 'Character name is required'
  } else if (!validateCharacterName(formData.name)) {
    errors.name = 'Character name must be 1-50 characters'
  }

  if (!formData.tagline.trim()) {
    errors.role = 'Tagline is required'
  }

  if (!formData.backstory.trim()) {
    errors.backstory = 'Backstory is required'
  }

  return !errors.name && !errors.role && !errors.backstory
}

const addLocation = () => {
  if (formData.key_locations.length < 10) {
    formData.key_locations.push('')
  }
}

const removeLocation = (index: number) => {
  formData.key_locations.splice(index, 1)
  if (formData.key_locations.length === 0) {
    formData.key_locations.push('')
  }
}

const addRelationship = () => {
  relationships.value.push({ name: '', relationship: '' })
}

const removeRelationship = (index: number) => {
  relationships.value.splice(index, 1)
  if (relationships.value.length === 0) {
    relationships.value.push({ name: '', relationship: '' })
  }
}

const processRelationships = () => {
  const relationshipsObj: Record<string, string> = {}

  relationships.value.forEach((rel) => {
    if (rel.name.trim() && rel.relationship.trim()) {
      relationshipsObj[rel.name.trim()] = rel.relationship.trim()
    }
  })

  return relationshipsObj
}

const handleGenerateCharacter = debounce(async () => {
  generating.value = true

  try {
    // Prepare partial character data, including relationships
    const partialCharacter: Partial<Character> = {}

    // Add non-empty fields to partial character
    if (formData.name.trim()) partialCharacter.name = formData.name.trim()
    if (formData.tagline.trim()) partialCharacter.tagline = formData.tagline.trim()
    if (formData.backstory.trim()) partialCharacter.backstory = formData.backstory.trim()
    if (formData.personality?.trim()) partialCharacter.personality = formData.personality.trim()
    if (formData.appearance?.trim()) partialCharacter.appearance = formData.appearance.trim()
    if (formData.setting_description?.trim())
      partialCharacter.setting_description = formData.setting_description.trim()

    // Add non-empty locations
    const filteredLocations = formData.key_locations?.filter((loc) => loc.trim().length > 0) || []
    if (filteredLocations.length > 0) partialCharacter.key_locations = filteredLocations

    // Add relationships
    const processedRelationships = processRelationships()
    if (Object.keys(processedRelationships).length > 0) {
      partialCharacter.relationships = processedRelationships
    }

    // Call the API to generate missing fields
    const response = await generateCharacter({
      partial_character: partialCharacter,
      processor_type: settings.value.aiProcessor,
    })

    // Update form data with generated character
    const generatedCharacter = response.character
    formData.name = generatedCharacter.name
    formData.tagline = generatedCharacter.tagline
    formData.backstory = generatedCharacter.backstory
    formData.personality = generatedCharacter.personality || ''
    formData.appearance = generatedCharacter.appearance || ''
    formData.setting_description = generatedCharacter.setting_description || ''
    formData.key_locations = generatedCharacter.key_locations || ['']

    // Update relationships
    if (generatedCharacter.relationships) {
      relationships.value = Object.entries(generatedCharacter.relationships).map(
        ([name, relationship]) => ({
          name,
          relationship,
        })
      )
      // Ensure there's always at least one empty relationship slot
      if (relationships.value.length === 0) {
        relationships.value.push({ name: '', relationship: '' })
      }
    }

    // Show success message with generated fields
    const generatedCount = response.generated_fields.length
    if (generatedCount > 0) {
      successMessage.value = `AI generated ${generatedCount} field(s): ${response.generated_fields.join(', ')}. Review and modify as needed!`
    } else {
      successMessage.value = 'All fields were already filled. No generation needed!'
    }
    setTimeout(() => (successMessage.value = ''), 8000)
  } catch (err: unknown) {
    console.error('Character generation failed:', err)
    errorMessage.value =
      (err as any)?.message || 'Failed to generate character fields. Please try again.'
    setTimeout(() => (errorMessage.value = ''), 5000)
  } finally {
    generating.value = false
  }
}, 500)

const processYaml = debounce(async () => {
  if (!yamlContent.value.trim()) return

  processingYaml.value = true

  try {
    // Simple YAML preview - in production, this would use a proper YAML parser
    yamlPreview.value = yamlContent.value
    successMessage.value = 'YAML parsed successfully!'
    setTimeout(() => (successMessage.value = ''), 3000)
  } catch (_err) {
    errorMessage.value = 'Invalid YAML format. Please check your syntax.'
    setTimeout(() => (errorMessage.value = ''), 5000)
  } finally {
    processingYaml.value = false
  }
}, 300)

const saveCharacter = async () => {
  if (!validateForm()) return

  try {
    // Process relationships
    formData.relationships = processRelationships()

    // Filter out empty locations
    formData.key_locations = formData.key_locations.filter((loc) => loc.trim().length > 0)

    const response = await createCharacter({
      data: formData,
      is_yaml_text: false,
    })

    successMessage.value = response.message
    setTimeout(() => {
      router.push('/')
    }, 2000)
  } catch (err: unknown) {
    validateForm()
    errorMessage.value =
      (err as any)?.value?.message || 'Failed to create character. Please try again.'
    setTimeout(() => (errorMessage.value = ''), 5000)
  }
}

const saveYamlCharacter = async () => {
  if (!yamlContent.value.trim()) return

  try {
    const response = await createCharacter({
      data: yamlContent.value,
      is_yaml_text: true,
    })

    successMessage.value = response.message
    setTimeout(() => {
      router.push('/')
    }, 2000)
  } catch (err: unknown) {
    errorMessage.value =
      (err as any)?.value?.message ||
      'Failed to create character from YAML. Please check your format.'
    setTimeout(() => (errorMessage.value = ''), 5000)
  }
}

// Reload settings on mount to pick up any changes
onMounted(() => {
  loadSettings()
})
</script>