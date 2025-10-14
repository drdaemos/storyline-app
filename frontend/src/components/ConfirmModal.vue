<template>
  <UModal v-model:open="isOpen">
    <template #content>
      <UCard>
      <template #header>
        <div class="flex items-center justify-between">
          <h3 class="text-lg font-semibold">{{ title }}</h3>
          <UButton
            color="neutral"
            variant="ghost"
            icon="i-lucide-x"
            size="sm"
            @click="handleCancel"
          />
        </div>
      </template>

      <p class="text-base">{{ message }}</p>

      <template #footer>
        <div class="flex gap-3 justify-end">
          <UButton
            color="neutral"
            variant="outline"
            @click="handleCancel"
          >
            Cancel
          </UButton>
          <UButton
            color="error"
            @click="handleConfirm"
          >
            {{ confirmText }}
          </UButton>
        </div>
      </template>
    </UCard>
    </template>
  </UModal>
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  show: boolean
  title: string
  message: string
  confirmText?: string
}

const props = withDefaults(defineProps<Props>(), {
  confirmText: 'Confirm'
})

const emit = defineEmits<{
  'confirm': []
  'cancel': []
}>()

const isOpen = computed({
  get: () => props.show,
  set: (value: boolean) => {
    if (!value) {
      emit('cancel')
    }
  }
})

const handleConfirm = () => {
  emit('confirm')
}

const handleCancel = () => {
  emit('cancel')
}
</script>
