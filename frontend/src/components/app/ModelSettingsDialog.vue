<script setup lang="ts">
import { SlidersHorizontal } from 'lucide-vue-next'
import { computed, ref, watch } from 'vue'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useLocalSettings } from '@/composables/useLocalSettings'
import { usePromptProcessorOptions } from '@/composables/usePromptProcessorOptions'

interface Props {
  iconOnly?: boolean
  buttonVariant?: 'default' | 'outline' | 'ghost' | 'secondary'
  buttonSize?: 'default' | 'sm' | 'lg' | 'icon'
}

const props = withDefaults(defineProps<Props>(), {
  iconOnly: true,
  buttonVariant: 'outline',
  buttonSize: 'icon',
})
const open = ref(false)

const { settings, updateSetting } = useLocalSettings()
const { refresh: refreshProcessorOptions, getOptionsWithCurrentValues } = usePromptProcessorOptions()
const modelOptions = computed(() =>
  getOptionsWithCurrentValues([settings.value.aiProcessor, settings.value.backupProcessor])
)

const buttonAriaLabel = computed(() => (props.iconOnly ? 'Model settings' : 'Open model settings'))

watch(open, async (isOpen) => {
  if (!isOpen) {
    return
  }
  await refreshProcessorOptions()
})
</script>

<template>
  <Dialog v-model:open="open">
    <DialogTrigger as-child>
      <Button :variant="buttonVariant" :size="buttonSize" :aria-label="buttonAriaLabel" type="button">
        <SlidersHorizontal class="size-4" />
        <span v-if="!iconOnly" class="ml-1">Model Settings</span>
      </Button>
    </DialogTrigger>
    <DialogContent>
      <DialogHeader>
        <DialogTitle>Model Settings</DialogTitle>
        <DialogDescription>Choose primary and fallback models for assistant actions.</DialogDescription>
      </DialogHeader>

      <div class="space-y-3">
        <div class="space-y-1.5">
          <label for="primary-model" class="text-sm">Primary model</label>
          <Select
            :model-value="settings.aiProcessor"
            @update:model-value="(value) => updateSetting('aiProcessor', String(value))"
          >
            <SelectTrigger id="primary-model">
              <SelectValue placeholder="Select model" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem v-for="model in modelOptions" :key="model.id" :value="model.id">
                {{ model.displayName }}
              </SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div class="space-y-1.5">
          <label for="fallback-model" class="text-sm">Fallback model</label>
          <Select
            :model-value="settings.backupProcessor"
            @update:model-value="(value) => updateSetting('backupProcessor', String(value))"
          >
            <SelectTrigger id="fallback-model">
              <SelectValue placeholder="Select model" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem
                v-for="model in modelOptions"
                :key="`${model.id}-fallback`"
                :value="model.id"
              >
                {{ model.displayName }}
              </SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      <DialogFooter>
        <DialogClose as-child>
          <Button variant="outline" type="button">Close</Button>
        </DialogClose>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>
