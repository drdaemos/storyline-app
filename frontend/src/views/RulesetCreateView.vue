<script setup lang="ts">
import { ScrollText, Sparkles } from 'lucide-vue-next'
import { computed, reactive, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { usePipelineApi } from '@/composables/usePipelineApi'
import type { CreateRulesetInput } from '@/types/pipeline'

type RulesetEditorMode = 'text' | 'json'

const router = useRouter()
const { createRuleset } = usePipelineApi()

const saving = ref(false)
const error = ref<string | null>(null)
const mode = ref<RulesetEditorMode>('text')

const form = reactive({
  name: '',
  rules_text: '',
  rules_json: `{
  "name": "Seven Minutes in Heaven",
  "rules_text": "Consent-first social scene with seven-minute timer.",
  "state_schemas": {
    "drives": [],
    "skills": [],
    "emotional_state": {
      "global_dims": [],
      "per_relationship": []
    }
  },
  "config": {
    "time_per_turn": "1 minute"
  }
}`,
})

const ruleBlocks = computed(() => {
  return form.rules_text
    .split(/\n{2,}/)
    .map((block) => block.trim())
    .filter((block) => block.length > 0)
})

const isRecord = (value: unknown): value is Record<string, unknown> => {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

const parsedJsonSummary = computed(() => {
  try {
    const parsed = JSON.parse(form.rules_json) as unknown
    if (!isRecord(parsed)) {
      return null
    }
    const ruleset = isRecord(parsed.ruleset) ? parsed.ruleset : parsed
    const drives = isRecord(ruleset.state_schemas) && Array.isArray(ruleset.state_schemas.drives)
      ? ruleset.state_schemas.drives.length
      : 0
    const skills = isRecord(ruleset.state_schemas) && Array.isArray(ruleset.state_schemas.skills)
      ? ruleset.state_schemas.skills.length
      : 0
    const hasConfig = isRecord(ruleset.config)
    const rulesetName = typeof ruleset.name === 'string' ? ruleset.name : ''
    return {
      name: rulesetName,
      drives,
      skills,
      hasConfig,
    }
  } catch {
    return null
  }
})

const appendTemplate = (template: string) => {
  if (!form.rules_text.trim()) {
    form.rules_text = template
    return
  }

  form.rules_text = `${form.rules_text.trim()}\n\n${template}`
}

const parseRulesetFromJson = (): CreateRulesetInput => {
  let parsed: unknown
  try {
    parsed = JSON.parse(form.rules_json) as unknown
  } catch {
    throw new Error('Ruleset JSON is invalid. Check commas, quotes, and brackets.')
  }

  if (!isRecord(parsed)) {
    throw new Error('Ruleset JSON must be an object.')
  }

  const rulesetCandidate = isRecord(parsed.ruleset) ? parsed.ruleset : parsed
  const nameFromJson = typeof rulesetCandidate.name === 'string' ? rulesetCandidate.name.trim() : ''
  const fallbackName = form.name.trim()
  const normalizedName = nameFromJson || fallbackName

  if (!normalizedName) {
    throw new Error('Ruleset JSON must include a non-empty "name".')
  }

  const payload: CreateRulesetInput = {
    name: normalizedName,
  }

  if (typeof rulesetCandidate.rules_text === 'string') {
    payload.rules_text = rulesetCandidate.rules_text
  }

  if (isRecord(rulesetCandidate.state_schemas)) {
    payload.state_schemas = rulesetCandidate.state_schemas
  }

  if (isRecord(rulesetCandidate.config)) {
    payload.config = rulesetCandidate.config
  }

  return payload
}

const saveRuleset = async () => {
  if (mode.value === 'text' && !form.name.trim()) {
    error.value = 'Ruleset name is required.'
    return
  }

  saving.value = true
  error.value = null

  try {
    const payload = mode.value === 'json'
      ? parseRulesetFromJson()
      : {
        name: form.name.trim(),
        rules_text: form.rules_text.trim(),
      }

    await createRuleset(payload)

    await router.push('/library/rulesets')
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to create ruleset.'
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <main class="mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8">
    <section class="surface-panel rounded-2xl p-6">
      <div class="mb-3 flex items-center gap-2">
        <Badge variant="outline">Create</Badge>
        <Badge class="choice-pill-dialogue">Ruleset</Badge>
      </div>
      <h1 class="display-heading text-3xl leading-tight sm:text-4xl">Create Ruleset</h1>
      <p class="mt-3 max-w-3xl text-sm text-muted-foreground sm:text-base">
        Define mechanics and tone constraints used by characters, scenarios, and play sessions.
      </p>
    </section>

    <section class="grid gap-4 lg:grid-cols-[1.65fr_1fr]">
      <article class="surface-panel rounded-2xl p-6">
        <div class="mb-4 flex items-center justify-between gap-2">
          <h2 class="text-xl font-semibold">Ruleset Surface</h2>
          <Button data-testid="save-ruleset" :disabled="saving" @click="saveRuleset">
            Save Ruleset
          </Button>
        </div>

        <div class="mb-4 inline-flex items-center gap-1 rounded-lg border border-border/70 bg-background/70 p-1">
          <Button
            data-testid="ruleset-mode-text"
            size="sm"
            type="button"
            :variant="mode === 'text' ? 'secondary' : 'ghost'"
            @click="mode = 'text'"
          >
            Text
          </Button>
          <Button
            data-testid="ruleset-mode-json"
            size="sm"
            type="button"
            :variant="mode === 'json' ? 'secondary' : 'ghost'"
            @click="mode = 'json'"
          >
            JSON
          </Button>
        </div>

        <div class="space-y-4">
          <template v-if="mode === 'text'">
            <div class="space-y-1.5">
              <label for="ruleset-name" class="text-sm">Name</label>
              <Input id="ruleset-name" v-model="form.name" placeholder="Noir Ledger Protocol" />
            </div>

            <div class="space-y-1.5">
              <label for="ruleset-text" class="text-sm">Rules Text</label>
              <Textarea
                id="ruleset-text"
                v-model="form.rules_text"
                rows="16"
                placeholder="Describe drives, skill checks, pacing, and failure consequences..."
              />
            </div>
          </template>

          <template v-else>
            <div class="space-y-1.5">
              <label for="ruleset-json" class="text-sm">Ruleset JSON</label>
              <Textarea
                id="ruleset-json"
                data-testid="ruleset-json"
                v-model="form.rules_json"
                rows="20"
                placeholder="Paste full ruleset JSON with name, rules_text, state_schemas, and config"
              />
            </div>
            <div class="rounded-xl border border-border/70 bg-background/70 p-3 text-xs text-muted-foreground">
              Accepts either `{ ...ruleset fields... }` or `{ "ruleset": { ... } }`.
            </div>
          </template>
        </div>

        <p v-if="error" class="mt-4 text-sm text-destructive">{{ error }}</p>

        <div class="mt-5 flex items-center justify-between gap-2">
          <Button variant="ghost" as-child>
            <RouterLink to="/library/rulesets">Back to Rulesets</RouterLink>
          </Button>
          <Button :disabled="saving" @click="saveRuleset">Save Ruleset</Button>
        </div>
      </article>

      <aside class="surface-panel rounded-2xl p-6 lg:sticky lg:top-24 lg:h-fit">
        <div class="mb-3 flex items-center gap-2">
          <Sparkles class="size-4" />
          <h2 class="text-xl font-semibold">{{ mode === 'text' ? 'Authoring Guide' : 'JSON Guide' }}</h2>
        </div>

        <template v-if="mode === 'text'">
          <p class="text-sm text-muted-foreground">
            Keep each rules block short and testable. Use consistent section names so scenario composition stays clear.
          </p>

          <div class="mt-4 space-y-2">
            <Button
              variant="outline"
              class="w-full justify-start"
              @click="appendTemplate('Drives:\n- Curiosity: 50\n- Loyalty: 50\n- Fear: 50')"
            >
              Add Drives Template
            </Button>
            <Button
              variant="outline"
              class="w-full justify-start"
              @click="appendTemplate('Skills:\n- Investigation\n- Composure\n- Influence')"
            >
              Add Skills Template
            </Button>
            <Button
              variant="outline"
              class="w-full justify-start"
              @click="appendTemplate('Resolution:\n- Roll d100\n- 1-34: fail\n- 35-69: mixed\n- 70-100: success')"
            >
              Add Resolution Template
            </Button>
          </div>

          <div class="mt-4 rounded-xl border border-border/70 bg-background/70 p-3">
            <p class="mb-2 text-xs uppercase tracking-wide text-muted-foreground">Blocks Preview</p>
            <ul class="space-y-2">
              <li v-for="(block, index) in ruleBlocks" :key="`block-${index}`" class="rounded-md border border-border/60 px-2 py-1.5 text-xs">
                <span class="mr-2 text-muted-foreground">{{ index + 1 }}.</span>
                {{ block.slice(0, 120) }}
              </li>
            </ul>
            <p v-if="!ruleBlocks.length" class="text-xs text-muted-foreground">No rule blocks yet.</p>
          </div>
        </template>

        <template v-else>
          <p class="text-sm text-muted-foreground">
            JSON mode stores complete mechanical schema: drives, skills, emotional dimensions, and runtime config.
          </p>
          <div class="mt-4 rounded-xl border border-border/70 bg-background/70 p-3">
            <p class="mb-2 text-xs uppercase tracking-wide text-muted-foreground">Parsed Summary</p>
            <p class="text-xs">
              Name:
              <span class="text-foreground">
                {{ parsedJsonSummary?.name || 'Missing' }}
              </span>
            </p>
            <p class="text-xs">Drives: {{ parsedJsonSummary?.drives ?? 0 }}</p>
            <p class="text-xs">Skills: {{ parsedJsonSummary?.skills ?? 0 }}</p>
            <p class="text-xs">Config: {{ parsedJsonSummary?.hasConfig ? 'Included' : 'Missing' }}</p>
          </div>
        </template>

        <p class="mt-4 inline-flex items-center gap-1.5 rounded-md border border-border/60 bg-background/70 px-2.5 py-1 text-xs text-muted-foreground">
          <ScrollText class="size-3.5" />
          {{
            mode === 'text'
              ? 'Ruleset text is stored as authored and validated at runtime.'
              : 'Full ruleset JSON is validated by backend schema on save.'
          }}
        </p>
      </aside>
    </section>
  </main>
</template>
