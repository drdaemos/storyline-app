<template>
  <div v-if="show" class="modal-overlay" @click="handleCancel">
    <div class="modal-content" @click.stop>
      <header class="modal-header">
        <h3>{{ title }}</h3>
        <button class="close-button" @click="handleCancel">
          <X :size="18" />
        </button>
      </header>

      <div class="modal-body">
        <p>{{ message }}</p>
      </div>

      <footer class="modal-footer">
        <button class="btn btn-secondary" @click="handleCancel">
          Cancel
        </button>
        <button class="btn btn-danger" @click="handleConfirm">
          {{ confirmText }}
        </button>
      </footer>
    </div>
  </div>
</template>

<script setup lang="ts">
import { X } from 'lucide-vue-next'

interface Props {
  show: boolean
  title: string
  message: string
  confirmText?: string
}

withDefaults(defineProps<Props>(), {
  confirmText: 'Confirm'
})

const emit = defineEmits<{
  'confirm': []
  'cancel': []
}>()

const handleConfirm = () => {
  emit('confirm')
}

const handleCancel = () => {
  emit('cancel')
}
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 1rem;
}

.modal-content {
  background: var(--surface-color);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
  width: 100%;
  max-width: 400px;
  max-height: 90vh;
  overflow-y: auto;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1.5rem;
  border-bottom: 1px solid var(--border-color);
}

.modal-header h3 {
  margin: 0;
  color: var(--text-primary);
}

.close-button {
  background: none;
  border: none;
  font-size: 1.25rem;
  cursor: pointer;
  padding: 0.5rem;
  border-radius: var(--radius-sm);
  color: var(--text-secondary);
  transition: all 0.2s;
}

.close-button:hover {
  background: var(--background-color);
  color: var(--text-primary);
}

.modal-body {
  padding: 1.5rem;
}

.modal-body p {
  margin: 0;
  color: var(--text-primary);
  line-height: 1.5;
}

.modal-footer {
  padding: 1rem 1.5rem 1.5rem;
  display: flex;
  gap: 0.75rem;
  justify-content: flex-end;
}

.btn-danger {
  background: #dc2626;
  color: white;
  border: 1px solid #dc2626;
}

.btn-danger:hover {
  background: #b91c1c;
  border-color: #b91c1c;
}

@media (max-width: 768px) {
  .modal-overlay {
    padding: 0;
    align-items: flex-end;
  }

  .modal-content {
    width: 100%;
    max-width: none;
    border-radius: var(--radius-lg) var(--radius-lg) 0 0;
    max-height: 80vh;
  }

  .modal-header {
    padding: 1.25rem;
  }

  .modal-body {
    padding: 1.25rem;
  }

  .modal-footer {
    padding: 1rem 1.25rem 1.25rem;
  }
}
</style>