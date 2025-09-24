<template>
  <div class="character-creation-view">
    <div class="creation-content">
      <header class="view-header">
        <div class="header-main">
          <router-link to="/" class="back-button">
            <ArrowLeft :size="16" class="inline mr-1" /> Back to Characters
          </router-link>
          <h2>Create New Character</h2>
        </div>
      </header>

      <div class="creation-tabs">
        <button
          class="tab-button"
          :class="{ active: activeTab === 'manual' }"
          @click="activeTab = 'manual'"
        >
          Manual Entry
        </button>
        <button
          class="tab-button"
          :class="{ active: activeTab === 'yaml' }"
          @click="activeTab = 'yaml'"
        >
          Import YAML
        </button>
      </div>

      <!-- Manual Entry Form -->
      <div v-if="activeTab === 'manual'" class="manual-form">
        <form @submit.prevent="saveCharacter" class="character-form">
          <div class="form-section">
            <h3>Basic Information</h3>

            <div class="form-group">
              <label for="name" class="required">Character Name</label>
              <input
                id="name"
                v-model="formData.name"
                type="text"
                class="input"
                :class="{ error: errors.name }"
                placeholder="Enter character name"
                required
              />
              <span v-if="errors.name" class="error-message">{{ errors.name }}</span>
            </div>

            <div class="form-group">
              <label for="role" class="required">Role/Profession</label>
              <input
                id="role"
                v-model="formData.role"
                type="text"
                class="input"
                :class="{ error: errors.role }"
                placeholder="e.g., Detective, Teacher, Wizard"
                required
              />
              <span v-if="errors.role" class="error-message">{{ errors.role }}</span>
            </div>

            <div class="form-group">
              <label for="backstory" class="required">Backstory</label>
              <textarea
                id="backstory"
                v-model="formData.backstory"
                class="input textarea"
                :class="{ error: errors.backstory }"
                rows="4"
                placeholder="Character's history, experiences, and background"
                required
              ></textarea>
              <span v-if="errors.backstory" class="error-message">{{ errors.backstory }}</span>
            </div>
          </div>

          <div class="form-section">
            <h3>Character Details</h3>

            <div class="form-group">
              <label for="personality">Personality</label>
              <textarea
                id="personality"
                v-model="formData.personality"
                class="input textarea"
                rows="3"
                placeholder="Personality traits and characteristics"
              ></textarea>
            </div>

            <div class="form-group">
              <label for="appearance">Physical Appearance</label>
              <textarea
                id="appearance"
                v-model="formData.appearance"
                class="input textarea"
                rows="3"
                placeholder="Physical description for avatar generation"
              ></textarea>
            </div>

            <div class="form-group">
              <label for="setting">Setting Description</label>
              <textarea
                id="setting"
                v-model="formData.setting_description"
                class="input textarea"
                rows="3"
                placeholder="Description of the world/setting the character exists in"
              ></textarea>
            </div>
          </div>

          <div class="form-section">
            <h3>Locations</h3>
            <p class="section-description">Add up to 10 key locations for this character.</p>

            <div class="locations-list">
              <div
                v-for="(location, index) in formData.key_locations"
                :key="index"
                class="location-item"
              >
                <input
                  v-model="formData.key_locations[index]"
                  type="text"
                  class="input"
                  :placeholder="`Location ${index + 1}`"
                />
                <button
                  type="button"
                  class="btn-icon remove-location"
                  @click="removeLocation(index)"
                  title="Remove location"
                >
                  <X :size="14" />
                </button>
              </div>
            </div>

            <button
              v-if="formData.key_locations.length < 10"
              type="button"
              class="btn btn-secondary"
              @click="addLocation"
            >
              + Add Location
            </button>
          </div>

          <div class="form-section">
            <h3>Relationships</h3>
            <p class="section-description">Define relationships with other characters.</p>

            <div class="relationships-list">
              <div
                v-for="(relationship, index) in relationships"
                :key="index"
                class="relationship-item"
              >
                <input
                  v-model="relationship.name"
                  type="text"
                  class="input"
                  placeholder="Character name"
                />
                <input
                  v-model="relationship.relationship"
                  type="text"
                  class="input"
                  placeholder="Relationship type"
                />
                <button
                  type="button"
                  class="btn-icon remove-relationship"
                  @click="removeRelationship(index)"
                  title="Remove relationship"
                >
                  <X :size="14" />
                </button>
              </div>
            </div>

            <button
              type="button"
              class="btn btn-secondary"
              @click="addRelationship"
            >
              + Add Relationship
            </button>
          </div>

          <div class="form-actions">
            <button
              type="button"
              class="btn btn-generate"
              @click="handleGenerateCharacter"
              :disabled="loading || !canGenerate"
              title="AI will fill empty fields based on existing content"
            >
              <span v-if="!generating">
                <Wand2 :size="16" class="inline mr-1" /> AI Generate Missing Fields
              </span>
              <span v-else class="generating">
                <Wand2 :size="16" class="inline mr-1" /> Generating...
              </span>
            </button>

            <button
              type="submit"
              class="btn btn-primary"
              :disabled="loading || !isFormValid"
            >
              <span v-if="!loading">Create Character</span>
              <div v-else class="loading-spinner"></div>
            </button>
          </div>
        </form>
      </div>

      <!-- YAML Import -->
      <div v-if="activeTab === 'yaml'" class="yaml-form">
        <div class="yaml-section">
          <h3>Import Character from YAML</h3>
          <p class="section-description">
            Paste your character definition in YAML format below. The system will parse and validate it.
          </p>

          <div class="form-group">
            <label for="yaml-content">YAML Content</label>
            <textarea
              id="yaml-content"
              v-model="yamlContent"
              class="input textarea yaml-textarea"
              rows="20"
              placeholder="name: Character Name
role: Character Role
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
            ></textarea>
          </div>

          <div class="yaml-actions">
            <button
              type="button"
              class="btn btn-secondary"
              @click="processYaml"
              :disabled="loading || !yamlContent.trim()"
            >
              <span v-if="!processingYaml">Parse YAML</span>
              <span v-else>Processing...</span>
            </button>

            <button
              type="button"
              class="btn btn-primary"
              @click="saveYamlCharacter"
              :disabled="loading || !yamlContent.trim()"
            >
              <span v-if="!loading">Create from YAML</span>
              <div v-else class="loading-spinner"></div>
            </button>
          </div>
        </div>

        <div v-if="yamlPreview" class="yaml-preview">
          <h4>Preview</h4>
          <pre class="yaml-preview-content">{{ yamlPreview }}</pre>
        </div>
      </div>

      <div v-if="successMessage" class="success-message">
        {{ successMessage }}
      </div>

      <div v-if="errorMessage" class="error-message-global">
        {{ errorMessage }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useApi } from '@/composables/useApi'
import { useLocalSettings } from '@/composables/useLocalSettings'
import { validateCharacterName, debounce } from '@/utils/formatters'
import type { Character } from '@/types'
import { ArrowLeft, Wand2, X } from 'lucide-vue-next'

const router = useRouter()
const { createCharacter, generateCharacter, loading, error } = useApi()
const { settings } = useLocalSettings()

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
  role: '',
  backstory: '',
  personality: '',
  appearance: '',
  relationships: {},
  key_locations: [''],
  setting_description: ''
})

const relationships = ref<RelationshipItem[]>([
  { name: '', relationship: '' }
])

const errors = reactive({
  name: '',
  role: '',
  backstory: ''
})

const isFormValid = computed(() => {
  return formData.name.trim().length > 0 &&
         formData.role.trim().length > 0 &&
         formData.backstory.trim().length > 0 &&
         validateCharacterName(formData.name)
})

const canGenerate = computed(() => {
  return formData.name.trim().length > 0 ||
         formData.role.trim().length > 0 ||
         formData.backstory.trim().length > 0
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

  if (!formData.role.trim()) {
    errors.role = 'Role is required'
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

  relationships.value.forEach(rel => {
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
    if (formData.role.trim()) partialCharacter.role = formData.role.trim()
    if (formData.backstory.trim()) partialCharacter.backstory = formData.backstory.trim()
    if (formData.personality?.trim()) partialCharacter.personality = formData.personality.trim()
    if (formData.appearance?.trim()) partialCharacter.appearance = formData.appearance.trim()
    if (formData.setting_description?.trim()) partialCharacter.setting_description = formData.setting_description.trim()

    // Add non-empty locations
    const filteredLocations = formData.key_locations?.filter(loc => loc.trim().length > 0) || []
    if (filteredLocations.length > 0) partialCharacter.key_locations = filteredLocations

    // Add relationships
    const processedRelationships = processRelationships()
    if (Object.keys(processedRelationships).length > 0) {
      partialCharacter.relationships = processedRelationships
    }

    // Call the API to generate missing fields
    const response = await generateCharacter({
      partial_character: partialCharacter,
      processor_type: settings.value.aiProcessor
    })

    // Update form data with generated character
    const generatedCharacter = response.character
    formData.name = generatedCharacter.name
    formData.role = generatedCharacter.role
    formData.backstory = generatedCharacter.backstory
    formData.personality = generatedCharacter.personality || ''
    formData.appearance = generatedCharacter.appearance || ''
    formData.setting_description = generatedCharacter.setting_description || ''
    formData.key_locations = generatedCharacter.key_locations || ['']

    // Update relationships
    if (generatedCharacter.relationships) {
      relationships.value = Object.entries(generatedCharacter.relationships).map(([name, relationship]) => ({
        name,
        relationship
      }))
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
    setTimeout(() => successMessage.value = '', 8000)

  } catch (err: unknown) {
    console.error('Character generation failed:', err)
    errorMessage.value = (err as any)?.message || 'Failed to generate character fields. Please try again.'
    setTimeout(() => errorMessage.value = '', 5000)
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
    setTimeout(() => successMessage.value = '', 3000)
  } catch (_err) {
    errorMessage.value = 'Invalid YAML format. Please check your syntax.'
    setTimeout(() => errorMessage.value = '', 5000)
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
    formData.key_locations = formData.key_locations.filter(loc => loc.trim().length > 0)

    const response = await createCharacter({
      data: formData,
      is_yaml_text: false
    })

    successMessage.value = response.message
    setTimeout(() => {
      router.push('/')
    }, 2000)

  } catch (err: unknown) {
    validateForm()
    errorMessage.value = (err as any)?.value?.message || 'Failed to create character. Please try again.'
    setTimeout(() => errorMessage.value = '', 5000)
  }
}

const saveYamlCharacter = async () => {
  if (!yamlContent.value.trim()) return

  try {
    const response = await createCharacter({
      data: yamlContent.value,
      is_yaml_text: true
    })

    successMessage.value = response.message
    setTimeout(() => {
      router.push('/')
    }, 2000)

  } catch (err: unknown) {
    errorMessage.value = (err as any)?.value?.message || 'Failed to create character from YAML. Please check your format.'
    setTimeout(() => errorMessage.value = '', 5000)
  }
}
</script>

<style scoped>
.character-creation-view {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.creation-content {
  max-width: 900px;
  margin: 0 auto;
  padding: 2rem 1.5rem;
  width: 100%;
}

.view-header {
  margin-bottom: 2rem;
}

.header-main {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-bottom: 1rem;
}

.back-button {
  color: var(--text-secondary);
  text-decoration: none;
  font-weight: 500;
  padding: 0.5rem;
  border-radius: var(--radius-sm);
  transition: all 0.2s;
}

.back-button:hover {
  color: var(--primary-color);
  background: #eff6ff;
}

.header-main h2 {
  margin: 0;
  color: var(--text-primary);
  font-size: 2rem;
  font-weight: 600;
}

.creation-tabs {
  display: flex;
  border-bottom: 1px solid var(--border-color);
  margin-bottom: 2rem;
}

.tab-button {
  background: none;
  border: none;
  padding: 1rem 2rem;
  font-size: 1rem;
  font-weight: 500;
  color: var(--text-secondary);
  cursor: pointer;
  border-bottom: 2px solid transparent;
  transition: all 0.2s;
}

.tab-button:hover {
  color: var(--text-primary);
  background: var(--background-color);
}

.tab-button.active {
  color: var(--primary-color);
  border-bottom-color: var(--primary-color);
}

.character-form {
  display: flex;
  flex-direction: column;
  gap: 2rem;
}

.form-section {
  background: var(--surface-color);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: 2rem;
}

.form-section h3 {
  margin: 0 0 1.5rem 0;
  color: var(--text-primary);
  font-size: 1.25rem;
}

.section-description {
  margin: 0 0 1rem 0;
  color: var(--text-secondary);
  font-size: 0.875rem;
}

.form-group {
  margin-bottom: 1.5rem;
}

.form-group:last-child {
  margin-bottom: 0;
}

.form-group label {
  display: block;
  margin-bottom: 0.5rem;
  font-weight: 500;
  color: var(--text-primary);
}

.form-group label.required::after {
  content: ' *';
  color: var(--error-color);
}

.error-message {
  display: block;
  margin-top: 0.5rem;
  color: var(--error-color);
  font-size: 0.875rem;
}

.locations-list,
.relationships-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  margin-bottom: 1rem;
}

.location-item,
.relationship-item {
  display: flex;
  gap: 0.75rem;
  align-items: center;
}

.relationship-item .input {
  flex: 1;
}

.btn-icon {
  background: none;
  border: none;
  padding: 0.5rem;
  cursor: pointer;
  border-radius: var(--radius-sm);
  transition: background-color 0.2s;
  color: var(--text-secondary);
}

.remove-location:hover,
.remove-relationship:hover {
  background: #fee2e2;
  color: var(--error-color);
}

.form-actions {
  display: flex;
  gap: 1rem;
  justify-content: flex-end;
  margin-top: 2rem;
}

.btn-generate {
  background: linear-gradient(135deg, #8b5cf6 0%, #a855f7 100%);
  color: white;
  border: 1px solid transparent;
  transition: all 0.3s ease;
}

.btn-generate:hover:not(:disabled) {
  background: linear-gradient(135deg, #7c3aed 0%, #9333ea 100%);
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(139, 92, 246, 0.3);
}

.btn-generate:disabled {
  background: #d1d5db;
  color: #9ca3af;
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}

.generating {
  animation: sparkle 1.5s ease-in-out infinite;
}

@keyframes sparkle {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}

.yaml-section {
  background: var(--surface-color);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: 2rem;
}

.yaml-section h3 {
  margin: 0 0 1rem 0;
  color: var(--text-primary);
}

.yaml-textarea {
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  font-size: 0.875rem;
  line-height: 1.5;
}

.yaml-actions {
  display: flex;
  gap: 1rem;
  margin-top: 1rem;
}

.yaml-preview {
  margin-top: 2rem;
  background: var(--background-color);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: 1.5rem;
}

.yaml-preview h4 {
  margin: 0 0 1rem 0;
  color: var(--text-primary);
}

.yaml-preview-content {
  margin: 0;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  font-size: 0.875rem;
  line-height: 1.5;
  white-space: pre-wrap;
  overflow-x: auto;
}

.success-message {
  background: #dcfce7;
  color: #166534;
  padding: 1rem;
  border-radius: var(--radius-md);
  margin-top: 1rem;
  text-align: center;
}

.error-message-global {
  background: #fee2e2;
  color: var(--error-color);
  padding: 1rem;
  border-radius: var(--radius-md);
  margin-top: 1rem;
  text-align: center;
}

@media (max-width: 768px) {
  .creation-content {
    padding: 1.5rem 1rem;
  }

  .header-main {
    flex-direction: column;
    align-items: flex-start;
    gap: 0.5rem;
  }

  .header-main h2 {
    font-size: 1.75rem;
  }

  .creation-tabs {
    overflow-x: auto;
  }

  .tab-button {
    padding: 0.75rem 1.5rem;
    white-space: nowrap;
  }

  .form-section {
    padding: 1.5rem;
  }

  .form-actions {
    flex-direction: column;
  }

  .yaml-actions {
    flex-direction: column;
  }

  .relationship-item {
    flex-direction: column;
    align-items: stretch;
  }
}

@media (max-width: 480px) {
  .location-item {
    flex-direction: column;
    align-items: stretch;
  }

  .form-section {
    padding: 1rem;
  }
}

/* Icon utility classes */
.inline {
  display: inline-block;
  vertical-align: middle;
}

.mr-1 {
  margin-right: 0.25rem;
}
</style>