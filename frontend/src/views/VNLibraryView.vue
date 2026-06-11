<template>
  <div class="max-w-5xl mx-auto space-y-8">
    <div class="flex items-center justify-between gap-4">
      <h2 class="text-3xl font-bold font-serif">Visual Novels</h2>
      <UButton icon="i-lucide-arrow-left" variant="ghost" color="neutral" to="/">Back to characters</UButton>
    </div>

    <UAlert v-if="errorMessage" color="error" variant="soft" icon="i-lucide-alert-triangle" :description="errorMessage" />

    <UModal v-model:open="previewOpen" :ui="{ width: 'max-w-4xl' }">
      <template #content>
        <UCard>
          <template #header>
            <div class="flex items-center justify-between gap-3">
              <h3 class="text-lg font-semibold">{{ previewTitle }}</h3>
              <UButton color="neutral" variant="ghost" icon="i-lucide-x" size="sm" @click="closePreview" />
            </div>
          </template>
          <div class="max-h-[70vh] overflow-y-auto">
            <div v-if="previewLoading" class="flex items-center justify-center py-8">
              <UIcon name="i-lucide-loader-2" class="w-6 h-6 animate-spin text-primary-500" />
            </div>
            <pre v-else class="whitespace-pre-wrap text-sm leading-6 font-mono bg-gray-50 dark:bg-gray-950 border border-gray-200 dark:border-gray-800 rounded-lg p-4">{{ previewText }}</pre>
          </div>
          <template #footer>
            <div class="flex justify-end">
              <UButton color="neutral" variant="outline" @click="closePreview">Close</UButton>
            </div>
          </template>
        </UCard>
      </template>
    </UModal>

    <!-- Scripts -->
    <section>
      <h3 class="text-xl font-semibold mb-3">Scripts</h3>
      <p v-if="!scripts.length" class="text-gray-500">No scripts yet — generate one below or import JSON.</p>
      <UPageGrid v-else>
        <UCard v-for="script in scripts" :key="script.id">
          <template #header>
            <div class="flex items-center justify-between gap-2">
              <span class="font-semibold">{{ script.title }}</span>
              <UBadge :color="script.validation_status === 'valid' ? 'success' : 'error'" variant="soft">
                {{ script.validation_status }}
              </UBadge>
            </div>
          </template>
          <p class="text-sm text-gray-500">{{ script.scene_count }} scenes · {{ script.ending_count }} endings</p>
          <template #footer>
            <div class="flex gap-2">
              <UButton variant="soft" icon="i-lucide-file-text" @click="previewScript(script.id)">Preview</UButton>
              <UButton :disabled="script.validation_status !== 'valid'" icon="i-lucide-play" @click="play(script.id)">Play</UButton>
              <UButton color="error" variant="ghost" icon="i-lucide-trash-2" @click="removeScript(script.id)" />
            </div>
          </template>
        </UCard>
      </UPageGrid>
    </section>

    <!-- Sessions -->
    <section v-if="sessions.length">
      <h3 class="text-xl font-semibold mb-3">Sessions</h3>
      <ul class="space-y-2">
        <li v-for="s in sessions" :key="s.session_id" class="flex items-center justify-between gap-4 px-4 py-2 rounded-lg border border-gray-200 dark:border-gray-800">
          <span>
            {{ s.script_title }}
            <UBadge :color="s.status === 'running' ? 'primary' : 'neutral'" variant="soft" class="ml-2">{{ s.status }}</UBadge>
          </span>
          <div class="flex gap-2">
            <UButton size="sm" variant="soft" @click="router.push({ name: 'vn-player', params: { sessionId: s.session_id } })">
              {{ s.status === 'running' ? 'Resume' : 'Review' }}
            </UButton>
            <UButton size="sm" color="error" variant="ghost" icon="i-lucide-trash-2" @click="removeSession(s.session_id)" />
          </div>
        </li>
      </ul>
    </section>

    <!-- Unfinished generations -->
    <section v-if="jobs.length">
      <h3 class="text-xl font-semibold mb-3">Unfinished generations</h3>
      <div class="space-y-3">
        <UCard v-for="job in jobs" :key="job.job_id">
          <template #header>
            <div class="flex items-center justify-between gap-2">
              <span class="font-semibold">{{ job.outline?.title || job.synopsis || 'Untitled' }}</span>
              <UBadge :color="job.status === 'failed' ? 'error' : 'warning'" variant="soft">{{ job.status }}</UBadge>
            </div>
          </template>
          <p v-if="job.error" class="text-sm text-red-500 mb-2">{{ job.error }}</p>
          <div v-if="job.outline" class="text-sm space-y-1">
            <p class="text-gray-500">Generated so far:</p>
            <ul>
              <li v-for="scene in job.outline.scenes" :key="scene.id" class="flex items-center gap-2">
                <UIcon :name="job.completed_scenes.includes(scene.id) ? 'i-lucide-check-circle-2' : 'i-lucide-circle-dashed'" :class="job.completed_scenes.includes(scene.id) ? 'text-green-500' : 'text-gray-400'" />
                <span :class="{ 'text-gray-400': !job.completed_scenes.includes(scene.id) }">{{ scene.intent }}</span>
              </li>
            </ul>
          </div>
          <p v-else class="text-sm text-gray-500">No outline yet — generation failed before the first stage completed.</p>
          <template #footer>
            <div class="flex gap-2">
              <UButton variant="soft" icon="i-lucide-file-text" @click="previewJob(job)">Preview</UButton>
              <UButton :loading="generating" :disabled="generating" icon="i-lucide-rotate-cw" @click="resume(job.job_id)">Resume</UButton>
              <UButton color="error" variant="ghost" icon="i-lucide-trash-2" @click="discardJob(job.job_id)" />
            </div>
          </template>
        </UCard>
      </div>
    </section>

    <!-- Generate -->
    <section>
      <h3 class="text-xl font-semibold mb-3">Generate a new script</h3>
      <UCard>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <UFormField label="Protagonist name">
            <UInput v-model="form.protagonistName" placeholder="Mara" />
          </UFormField>
          <UFormField label="Protagonist background">
            <UInput v-model="form.protagonistBackground" placeholder="A thief with a debt to pay" />
          </UFormField>
          <UFormField label="Synopsis" class="md:col-span-2">
            <UTextarea v-model="form.synopsis" :rows="2" placeholder="Starting situation and central conflict" class="w-full" />
          </UFormField>
          <UFormField label="Protagonist goal" class="md:col-span-2">
            <UInput v-model="form.goal" placeholder="What the protagonist wants" />
          </UFormField>
          <UFormField label="World description">
            <UInput v-model="form.world" placeholder="A small river town under curfew" />
          </UFormField>
          <UFormField label="Rules / tone">
            <UInput v-model="form.rules" placeholder="Low fantasy, grounded stakes, no gore" />
          </UFormField>
          <UFormField label="Scenes">
            <UInputNumber v-model="form.targetScenes" :min="2" :max="20" />
          </UFormField>
          <UFormField label="Endings">
            <UInputNumber v-model="form.targetEndings" :min="1" :max="8" />
          </UFormField>
        </div>
        <template #footer>
          <div class="space-y-3">
            <UButton :loading="generating" :disabled="!canGenerate" icon="i-lucide-sparkles" @click="generate">Generate</UButton>
            <div v-if="progressLog.length" class="text-sm font-mono space-y-0.5 max-h-48 overflow-y-auto">
              <p v-for="(line, index) in progressLog" :key="index">{{ line }}</p>
            </div>
          </div>
        </template>
      </UCard>
    </section>

    <!-- Import -->
    <section>
      <h3 class="text-xl font-semibold mb-3">Import script JSON</h3>
      <UCard>
        <UTextarea v-model="importJson" :rows="6" placeholder="Paste a script JSON…" class="w-full font-mono text-xs" />
        <template #footer>
          <div class="space-y-3">
            <UButton variant="soft" icon="i-lucide-file-up" :disabled="!importJson.trim()" @click="doImport">Import</UButton>
            <div v-if="importIssues.length" class="text-sm space-y-1">
              <p v-for="(issue, index) in importIssues" :key="index" :class="issue.severity === 'error' ? 'text-red-500' : 'text-amber-500'">
                [{{ issue.code }}] {{ issue.message }}
              </p>
            </div>
          </div>
        </template>
      </UCard>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useVnApi } from '@/composables/useVnApi'
import { useFormDraft } from '@/composables/useFormDraft'
import { useLocalSettings } from '@/composables/useLocalSettings'
import type { VNGenerationEvent, VNGenerationJob, VNScriptSummary, VNSessionSummary, VNValidationIssue } from '@/types/vn'
import { formatGenerationJobPreview, formatScriptPreview } from '@/utils/vnDisplay'

const router = useRouter()
const api = useVnApi()
const { settings } = useLocalSettings()

const scripts = ref<VNScriptSummary[]>([])
const sessions = ref<VNSessionSummary[]>([])
const jobs = ref<VNGenerationJob[]>([])
const errorMessage = ref('')
const importJson = ref('')
const importIssues = ref<VNValidationIssue[]>([])
const generating = ref(false)
const progressLog = ref<string[]>([])
const previewOpen = ref(false)
const previewLoading = ref(false)
const previewTitle = ref('Script preview')
const previewText = ref('')

const form = ref({
  protagonistName: '',
  protagonistBackground: '',
  synopsis: '',
  goal: '',
  world: '',
  rules: '',
  targetScenes: 6,
  targetEndings: 2,
})

useFormDraft('vn-generation-draft', form)

const canGenerate = computed(() => form.value.protagonistName.trim() && form.value.synopsis.trim() && form.value.goal.trim() && !generating.value)

const refresh = async () => {
  try {
    ;[scripts.value, sessions.value, jobs.value] = await Promise.all([api.listScripts(), api.listSessions(), api.listGenerationJobs()])
  } catch (err) {
    errorMessage.value = err instanceof Error ? err.message : 'Failed to load library'
  }
}

const play = async (scriptId: string) => {
  try {
    const session = await api.createSession(scriptId)
    router.push({ name: 'vn-player', params: { sessionId: session.session_id } })
  } catch (err) {
    errorMessage.value = err instanceof Error ? err.message : 'Failed to start session'
  }
}

const previewScript = async (scriptId: string) => {
  previewOpen.value = true
  previewLoading.value = true
  previewTitle.value = 'Script preview'
  previewText.value = ''
  errorMessage.value = ''
  try {
    const detail = await api.getScript(scriptId)
    previewTitle.value = detail.title
    previewText.value = formatScriptPreview(detail.script)
  } catch (err) {
    errorMessage.value = err instanceof Error ? err.message : 'Failed to load script preview'
    previewOpen.value = false
  } finally {
    previewLoading.value = false
  }
}

const previewJob = (job: VNGenerationJob) => {
  previewTitle.value = job.outline?.title || job.synopsis || 'Script preview'
  previewText.value = formatGenerationJobPreview(job)
  previewOpen.value = true
}

const closePreview = () => {
  previewOpen.value = false
}

const removeScript = async (scriptId: string) => {
  await api.deleteScript(scriptId)
  await refresh()
}

const removeSession = async (sessionId: string) => {
  await api.deleteSession(sessionId)
  await refresh()
}

const doImport = async () => {
  importIssues.value = []
  errorMessage.value = ''
  try {
    const parsed = JSON.parse(importJson.value)
    const result = await api.importScript(parsed)
    importIssues.value = result.report.issues
    if (result.validation_status === 'valid') {
      importJson.value = ''
    }
    await refresh()
  } catch (err) {
    errorMessage.value = err instanceof Error ? err.message : 'Import failed'
  }
}

const logGenerationEvent = (event: VNGenerationEvent) => {
  if (event.type === 'progress' && event.status === 'passed') {
    void refresh()
  }
  if (event.type === 'started') {
    progressLog.value.push('generation job started')
    void refresh()
  } else if (event.type === 'progress') {
    progressLog.value.push(`${event.stage}${event.scene_id ? ` [${event.scene_id}]` : ''}: ${event.status}${event.detail ? ` — ${event.detail}` : ''}`)
  } else if (event.type === 'complete') {
    progressLog.value.push(`complete: script ${event.script_id} (${event.validation_status})`)
  } else {
    progressLog.value.push(`error: ${event.error} — progress is saved, you can resume`)
  }
}

const generate = async () => {
  generating.value = true
  progressLog.value = []
  errorMessage.value = ''
  try {
    await api.generateScript(
      {
        characters: [
          {
            name: form.value.protagonistName.trim(),
            background: form.value.protagonistBackground.trim(),
            appearance: '',
            protagonist: true,
          },
        ],
        setting: { world_description: form.value.world.trim(), anchors: [] },
        rules: form.value.rules.trim(),
        premise: {
          synopsis: form.value.synopsis.trim(),
          protagonist_goal: form.value.goal.trim(),
          scope: { target_scenes: form.value.targetScenes, target_endings: form.value.targetEndings },
        },
      },
      settings.value.aiProcessor || 'claude-sonnet',
      logGenerationEvent,
    )
  } catch (err) {
    errorMessage.value = err instanceof Error ? err.message : 'Generation failed'
  } finally {
    generating.value = false
    await refresh()
  }
}

const resume = async (jobId: string) => {
  generating.value = true
  progressLog.value = []
  errorMessage.value = ''
  try {
    await api.resumeGeneration(jobId, logGenerationEvent)
  } catch (err) {
    errorMessage.value = err instanceof Error ? err.message : 'Resume failed'
  } finally {
    generating.value = false
    await refresh()
  }
}

const discardJob = async (jobId: string) => {
  await api.deleteGenerationJob(jobId)
  await refresh()
}

onMounted(refresh)
</script>
