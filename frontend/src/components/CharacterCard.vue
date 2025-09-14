<template>
  <div
    class="character-card"
    :class="{ 'selected': selected, 'create-new': isCreateNew }"
    @click="handleClick"
  >
    <div v-if="isCreateNew" class="create-new-content">
      <div class="create-icon">+</div>
      <h3>Create New Character</h3>
    </div>

    <div v-else class="character-content">
      <div class="character-avatar">
        <img
          v-if="characterInfo?.appearance"
          :src="getAvatarUrl(character)"
          :alt="character"
          loading="lazy"
          @error="handleImageError"
        />
        <div v-else class="avatar-placeholder">
          {{ character.charAt(0).toUpperCase() }}
        </div>
      </div>

      <div class="character-info">
        <h3 class="character-name">{{ character }}</h3>
        <p v-if="characterInfo?.role" class="character-role">
          {{ characterInfo.role }}
        </p>
        <p v-if="characterInfo?.backstory" class="character-description">
          {{ truncateText(characterInfo.backstory, 100) }}
        </p>
      </div>
    </div>

    <div v-if="selected" class="selection-indicator">
      ✓
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useApi } from '@/composables/useApi'
import { truncateText } from '@/utils/formatters'

interface Props {
  character?: string
  selected?: boolean
  isCreateNew?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  selected: false,
  isCreateNew: false
})

const emit = defineEmits<{
  select: [character: string]
  create: []
}>()

const { getCharacterInfo } = useApi()
const characterInfo = ref<Record<string, string> | null>(null)
const imageError = ref(false)

const handleClick = () => {
  if (props.isCreateNew) {
    emit('create')
  } else if (props.character) {
    emit('select', props.character)
  }
}

const getAvatarUrl = (name: string): string => {
  // For now, we'll use a placeholder service
  // In production, this would likely be served from your backend
  return `https://api.dicebear.com/7.x/avataaars/svg?seed=${encodeURIComponent(name)}`
}

const handleImageError = () => {
  imageError.value = true
}

onMounted(async () => {
  if (props.character && !props.isCreateNew) {
    try {
      characterInfo.value = await getCharacterInfo(props.character)
    } catch (error) {
      console.warn(`Failed to load character info for ${props.character}:`, error)
    }
  }
})
</script>

<style scoped>
.character-card {
  position: relative;
  background: var(--surface-color);
  border: 2px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: 1.5rem;
  cursor: pointer;
  transition: all 0.2s;
  min-height: 200px;
  display: flex;
  flex-direction: column;
}

.character-card:hover {
  border-color: var(--primary-color);
  box-shadow: var(--shadow-md);
  transform: translateY(-2px);
}

.character-card.selected {
  border-color: var(--primary-color);
  background: #eff6ff;
  box-shadow: var(--shadow-md);
}

.character-card.create-new {
  border-style: dashed;
  justify-content: center;
  align-items: center;
  text-align: center;
  color: var(--text-secondary);
}

.character-card.create-new:hover {
  color: var(--primary-color);
  background: #eff6ff;
}

.create-new-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1rem;
}

.create-icon {
  font-size: 3rem;
  font-weight: 300;
  opacity: 0.7;
}

.character-content {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  height: 100%;
}

.character-avatar {
  align-self: center;
}

.character-avatar img {
  width: 60px;
  height: 60px;
  border-radius: 50%;
  object-fit: cover;
}

.avatar-placeholder {
  width: 60px;
  height: 60px;
  border-radius: 50%;
  background: var(--primary-color);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.5rem;
  font-weight: 600;
}

.character-info {
  text-align: center;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.character-name {
  font-size: 1.125rem;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.character-role {
  font-size: 0.875rem;
  color: var(--text-secondary);
  font-weight: 500;
  margin: 0;
}

.character-description {
  font-size: 0.8rem;
  color: var(--text-secondary);
  line-height: 1.4;
  margin: 0;
  flex: 1;
}

.selection-indicator {
  position: absolute;
  top: 0.75rem;
  right: 0.75rem;
  width: 24px;
  height: 24px;
  background: var(--primary-color);
  color: white;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.75rem;
  font-weight: 600;
}

@media (max-width: 768px) {
  .character-card {
    padding: 1rem;
    min-height: 160px;
  }

  .character-avatar img,
  .avatar-placeholder {
    width: 48px;
    height: 48px;
  }

  .character-name {
    font-size: 1rem;
  }

  .character-role {
    font-size: 0.8rem;
  }

  .character-description {
    font-size: 0.75rem;
  }
}
</style>