<script setup lang="ts">
import type { Component } from 'vue'
import {
  BookOpenText,
  Clock3,
  Compass,
  Dice5,
  FolderKanban,
  MessageSquareText,
  Search,
  SlidersHorizontal,
  Sparkles,
  SquareLibrary,
  Sword,
  UserRound,
  WandSparkles,
} from 'lucide-vue-next'
import { ref } from 'vue'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Separator } from '@/components/ui/separator'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Textarea } from '@/components/ui/textarea'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { Switch } from '@/components/ui/switch'

type ContinuationType = 'action' | 'dialogue' | 'relocation' | 'time_skip'

type SessionState = 'active' | 'paused' | 'complete' | 'archived'

interface ContinuationOption {
  id: string
  label: string
  type: ContinuationType
}

interface TurnPreview {
  id: string
  actor: string
  command: string
  narration: string
  mechanicalHint: string
  options: ContinuationOption[]
}

interface SessionCard {
  id: string
  title: string
  scenario: string
  updated: string
  progress: string
  state: SessionState
}

interface AssistantMessage {
  id: string
  role: 'assistant' | 'user'
  text: string
}

interface BlockLink {
  title: string
  meta: string
  cta: string
}

const continuationMeta: Record<ContinuationType, { icon: Component; className: string }> = {
  action: { icon: Sword, className: 'choice-pill-action' },
  dialogue: { icon: MessageSquareText, className: 'choice-pill-dialogue' },
  relocation: { icon: Compass, className: 'choice-pill-relocation' },
  time_skip: { icon: Clock3, className: 'choice-pill-timeskip' },
}

const navigationItems = ['Home', 'Hub', 'Sessions']

const homeContinue: SessionCard[] = [
  {
    id: 's-401',
    title: 'Nightfall Ledger',
    scenario: 'Dock investigator in strike-week city district',
    updated: '3h ago',
    progress: 'Turn 14',
    state: 'active',
  },
  {
    id: 's-398',
    title: 'Cathedral Transit Audit',
    scenario: 'Late-night rail anomaly investigation',
    updated: 'Yesterday',
    progress: 'Turn 8',
    state: 'paused',
  },
]

const quickStartLinks: BlockLink[] = [
  { title: 'Start from Scenario', meta: 'Pick scenario and persona', cta: 'Start' },
  { title: 'Quick Skirmish', meta: 'Minimal setup, immediate turn', cta: 'Launch' },
  { title: 'Resume Draft', meta: 'Continue unfinished world setup', cta: 'Open' },
]

const creationCards: BlockLink[] = [
  { title: 'Character', meta: 'NPC identity, voice, motivations', cta: 'Create' },
  { title: 'Persona', meta: 'Player-facing protagonist profile', cta: 'Create' },
  { title: 'Ruleset', meta: 'Stats, drives, mechanics, checks', cta: 'Create' },
  { title: 'World Lore', meta: 'Tags, factions, districts, history', cta: 'Create' },
  { title: 'Scenario', meta: 'Assemble entities into playable setup', cta: 'Create' },
]

const hubCollections: BlockLink[] = [
  { title: 'Characters', meta: '48 items · last edited 2h ago', cta: 'Browse' },
  { title: 'Personas', meta: '9 items · last edited yesterday', cta: 'Browse' },
  { title: 'Rulesets', meta: '12 items · 3 need review', cta: 'Browse' },
  { title: 'World Lore', meta: '142 entries · tag grouped', cta: 'Browse' },
  { title: 'Scenarios', meta: '21 setups · 5 in draft', cta: 'Browse' },
]

const sessions: SessionCard[] = [
  {
    id: 's-401',
    title: 'Nightfall Ledger',
    scenario: 'Dock investigator in strike-week city district',
    updated: '3h ago',
    progress: 'Turn 14',
    state: 'active',
  },
  {
    id: 's-398',
    title: 'Cathedral Transit Audit',
    scenario: 'Late-night rail anomaly investigation',
    updated: 'Yesterday',
    progress: 'Turn 8',
    state: 'paused',
  },
  {
    id: 's-390',
    title: 'Frozen District Rumors',
    scenario: 'Faction rumors and debt pressure storyline',
    updated: '2 days ago',
    progress: 'Turn 22',
    state: 'complete',
  },
  {
    id: 's-362',
    title: 'Asterline Platform Zero',
    scenario: 'Abandoned route exploration archive',
    updated: '4 days ago',
    progress: 'Turn 3',
    state: 'archived',
  },
]

const assistantMessages: AssistantMessage[] = [
  {
    id: 'a1',
    role: 'assistant',
    text: 'I can draft the opening beat in a noir tone and suggest 3 conflicts tied to your selected ruleset.',
  },
  {
    id: 'u1',
    role: 'user',
    text: 'Keep it tense and urban. Build around rail strikes and hidden ledgers.',
  },
  {
    id: 'a2',
    role: 'assistant',
    text: 'Prepared. Hooks include faction pressure, personal debt, and a viable overnight time skip branch.',
  },
]

const turnFeed: TurnPreview[] = [
  {
    id: '1',
    actor: 'You',
    command: 'Ask the dock union archivist about the sealed ledger.',
    narration:
      'She studies you for a long second, then slides the ledger across the counter. The cover is marked with a faded city crest and one word scratched over in red: NIGHTFALL.',
    mechanicalHint: 'Empathy 67% succeeded, suspicion +1',
    options: [
      { id: '1-1', label: 'Press for names in the ledger.', type: 'dialogue' },
      { id: '1-2', label: 'Take the ledger and leave quietly.', type: 'action' },
      { id: '1-3', label: 'Head to the rail district.', type: 'relocation' },
    ],
  },
  {
    id: '2',
    actor: 'You',
    command: 'Spend the evening cross-referencing names with old transit rosters.',
    narration:
      'Hours dissolve in a storm of paper cuts and coffee rings. Near midnight, a repeated surname appears alongside canceled commuter routes and one quarantined station.',
    mechanicalHint: 'Investigation pass, fatigue +2, new clue unlocked',
    options: [
      { id: '2-1', label: 'Skip to dawn and confront station security.', type: 'time_skip' },
      { id: '2-2', label: 'Call your contact before sunrise.', type: 'dialogue' },
      { id: '2-3', label: 'Scout the station perimeter now.', type: 'action' },
    ],
  },
]

const assistivePanelEnabled = ref(true)

const sessionFilters: { label: string; value: SessionState | 'all' }[] = [
  { label: 'All', value: 'all' },
  { label: 'Active', value: 'active' },
  { label: 'Paused', value: 'paused' },
  { label: 'Complete', value: 'complete' },
  { label: 'Archived', value: 'archived' },
]

const stateBadgeClass: Record<SessionState, string> = {
  active: 'choice-pill-relocation',
  paused: 'choice-pill-timeskip',
  complete: 'choice-pill-dialogue',
  archived: 'choice-pill-action',
}
</script>

<template>
  <main class="narrative-app-shell min-h-screen pb-12">
    <div class="mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8">
      <section class="surface-panel rounded-2xl p-6">
        <div class="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div class="flex items-center gap-2">
            <Badge variant="outline">Style Lab</Badge>
            <Badge class="choice-pill-dialogue">Feature-Complete Prototype Pass</Badge>
          </div>
          <div class="flex items-center gap-2">
            <Button variant="outline" size="sm">
              <Sparkles class="mr-2 size-4" />
              Palette Draft
            </Button>
          </div>
        </div>
        <h1 class="display-heading text-3xl leading-tight sm:text-4xl">Storyline UI Prototypes</h1>
        <p class="mt-3 max-w-3xl text-sm leading-relaxed text-muted-foreground sm:text-base">
          Home, Hub, Sessions, Play, and Creation shown as cohesive interactive prototypes with shared styling,
          narrative tone, and clear app-like behavior.
        </p>
      </section>

      <section class="surface-panel rounded-2xl p-4 sm:p-5">
        <div class="rounded-xl border border-border/70 bg-background/80 px-4 py-3">
          <div class="flex items-center justify-between gap-3">
            <div class="inline-flex items-center gap-2">
              <SquareLibrary class="size-5" />
              <span class="display-heading text-lg">Storyline</span>
            </div>

            <nav class="hidden items-center gap-1 md:flex">
              <Button v-for="item in navigationItems" :key="item" variant="ghost" size="sm" class="text-xs">
                {{ item }}
              </Button>
            </nav>

            <div class="flex items-center gap-2">
              <Button variant="outline" size="icon" aria-label="Search">
                <Search class="size-4" />
              </Button>
              <Button variant="outline" size="icon" aria-label="Models">
                <SlidersHorizontal class="size-4" />
              </Button>
            </div>
          </div>
        </div>
      </section>

      <Tabs default-value="home" class="gap-4">
        <TabsList class="grid w-full grid-cols-5">
          <TabsTrigger value="home">Home</TabsTrigger>
          <TabsTrigger value="hub">Hub</TabsTrigger>
          <TabsTrigger value="sessions">Sessions</TabsTrigger>
          <TabsTrigger value="play">Play</TabsTrigger>
          <TabsTrigger value="creation">Creation</TabsTrigger>
        </TabsList>

        <TabsContent value="home">
          <section class="surface-panel rounded-2xl p-6">
            <div class="mb-4 flex items-center justify-between gap-2">
              <h2 class="text-xl font-semibold">Home</h2>
              <Badge variant="outline">Sections + blocks</Badge>
            </div>

            <div class="grid gap-4 lg:grid-cols-[1.8fr_1fr]">
              <div class="space-y-4">
                <div class="rounded-xl border border-border/70 bg-background/70 p-4">
                  <div class="mb-3 flex items-center justify-between">
                    <h3 class="text-base font-semibold">Continue Playing</h3>
                    <Button variant="ghost" size="sm">See all sessions</Button>
                  </div>
                  <div class="grid gap-3 sm:grid-cols-2">
                    <article
                      v-for="session in homeContinue"
                      :key="session.id"
                      class="rounded-lg border border-border/65 bg-background/80 p-3"
                    >
                      <p class="text-sm font-medium">{{ session.title }}</p>
                      <p class="mt-1 text-xs text-muted-foreground">{{ session.scenario }}</p>
                      <div class="mt-3 flex items-center justify-between">
                        <span :class="['rounded-full px-2 py-0.5 text-[11px]', stateBadgeClass[session.state]]">{{ session.progress }}</span>
                        <Button variant="ghost" size="sm">Resume</Button>
                      </div>
                    </article>
                  </div>
                </div>

                <div class="rounded-xl border border-border/70 bg-background/70 p-4">
                  <h3 class="mb-3 text-base font-semibold">Start New</h3>
                  <div class="grid gap-2 sm:grid-cols-3">
                    <div
                      v-for="item in quickStartLinks"
                      :key="item.title"
                      class="rounded-lg border border-border/65 bg-background/80 px-3 py-2.5"
                    >
                      <p class="text-sm">{{ item.title }}</p>
                      <p class="text-xs text-muted-foreground">{{ item.meta }}</p>
                      <Button variant="ghost" size="sm" class="mt-2">{{ item.cta }}</Button>
                    </div>
                  </div>
                </div>
              </div>

              <aside class="space-y-4">
                <div class="rounded-xl border border-border/70 bg-background/70 p-4">
                  <h3 class="text-base font-semibold">Creation Hub</h3>
                  <p class="mt-1 text-sm text-muted-foreground">Jump into characters, lore, rulesets, and scenario assembly.</p>
                  <Button class="mt-3 w-full">Open Hub</Button>
                </div>
                <div class="rounded-xl border border-border/70 bg-background/70 p-4">
                  <h3 class="text-base font-semibold">World Signals</h3>
                  <p class="mt-2 text-sm">3 scenarios have missing lore references.</p>
                  <p class="text-sm">2 rulesets need stat schema review.</p>
                </div>
              </aside>
            </div>
          </section>
        </TabsContent>

        <TabsContent value="hub">
          <section class="surface-panel rounded-2xl p-6">
            <div class="mb-4 flex items-center justify-between gap-2">
              <h2 class="text-xl font-semibold">Creation Hub</h2>
              <Button variant="outline" size="sm">
                <Search class="mr-2 size-4" />
                Search Entities
              </Button>
            </div>

            <div class="mb-4 rounded-xl border border-border/70 bg-background/70 p-4">
              <h3 class="mb-3 text-base font-semibold">Create New</h3>
              <div class="grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
                <button
                  v-for="entry in creationCards"
                  :key="entry.title"
                  type="button"
                  class="rounded-lg border border-border/65 bg-background/80 px-3 py-3 text-left hover:bg-accent/30"
                >
                  <p class="text-sm">{{ entry.title }}</p>
                  <p class="text-xs text-muted-foreground">{{ entry.meta }}</p>
                  <span class="mt-2 inline-block text-xs text-foreground/80">{{ entry.cta }}</span>
                </button>
              </div>
            </div>

            <div class="grid gap-4 lg:grid-cols-[1.8fr_1fr]">
              <div class="rounded-xl border border-border/70 bg-background/70 p-4">
                <h3 class="mb-3 text-base font-semibold">Libraries</h3>
                <div class="space-y-2">
                  <div
                    v-for="entry in hubCollections"
                    :key="entry.title"
                    class="flex items-center justify-between rounded-lg border border-border/60 bg-background/80 px-3 py-2"
                  >
                    <div>
                      <p class="text-sm">{{ entry.title }}</p>
                      <p class="text-xs text-muted-foreground">{{ entry.meta }}</p>
                    </div>
                    <Button variant="ghost" size="sm">{{ entry.cta }}</Button>
                  </div>
                </div>
              </div>

              <aside class="rounded-xl border border-border/70 bg-background/70 p-4">
                <h3 class="text-base font-semibold">Draft Queue</h3>
                <p class="mt-2 text-sm">Scenario: "Winter Station Debt"</p>
                <p class="text-sm">World Lore: 4 unsaved entries</p>
                <p class="text-sm">Ruleset: 1 validation warning</p>
              </aside>
            </div>
          </section>
        </TabsContent>

        <TabsContent value="sessions">
          <section class="surface-panel rounded-2xl p-6">
            <div class="mb-4 flex items-center justify-between gap-2">
              <h2 class="text-xl font-semibold">Sessions</h2>
              <Button variant="outline" size="sm">
                <Search class="mr-2 size-4" />
                Search by scenario or persona
              </Button>
            </div>

            <div class="mb-4 flex flex-wrap gap-2">
              <Button
                v-for="filter in sessionFilters"
                :key="filter.value"
                variant="outline"
                size="sm"
              >
                {{ filter.label }}
              </Button>
            </div>

            <div class="grid gap-3 sm:grid-cols-2">
              <article
                v-for="session in sessions"
                :key="session.id"
                class="rounded-xl border border-border/70 bg-background/70 p-4"
              >
                <div class="mb-2 flex items-center justify-between">
                  <p class="text-sm font-medium">{{ session.title }}</p>
                  <Badge :class="stateBadgeClass[session.state]">{{ session.state }}</Badge>
                </div>
                <p class="text-xs text-muted-foreground">{{ session.scenario }}</p>
                <div class="mt-3 flex items-center justify-between">
                  <p class="text-xs text-muted-foreground">{{ session.progress }} · {{ session.updated }}</p>
                  <div class="flex gap-1">
                    <Button variant="ghost" size="sm">Open</Button>
                    <Button variant="ghost" size="sm">Resume</Button>
                  </div>
                </div>
              </article>
            </div>
          </section>
        </TabsContent>

        <TabsContent value="play">
          <section class="surface-panel rounded-2xl p-6">
            <div class="grid gap-6 lg:grid-cols-[2.1fr_1fr]">
              <div>
                <div class="mb-3 flex items-center justify-between gap-2">
                  <h2 class="text-xl font-semibold">Play (Session View)</h2>
                  <TooltipProvider>
                    <Tooltip>
                      <TooltipTrigger as-child>
                        <Button variant="ghost" size="sm">Immersive mode</Button>
                      </TooltipTrigger>
                      <TooltipContent>
                        <p>Hide mechanics and focus on narrative text.</p>
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </div>

                <ScrollArea class="h-[430px] rounded-xl border border-border/70 bg-background/65 px-4 py-3">
                  <article
                    v-for="turn in turnFeed"
                    :key="turn.id"
                    class="mb-5 border-b border-border/50 pb-5 last:mb-0 last:border-b-0 last:pb-0"
                  >
                    <div class="mb-2 flex items-center justify-between text-xs uppercase tracking-wider text-muted-foreground">
                      <span class="inline-flex items-center gap-1.5">
                        <UserRound class="size-3.5" />
                        {{ turn.actor }}
                      </span>
                      <span>Turn {{ turn.id }}</span>
                    </div>

                    <p class="mb-2 text-sm font-medium">{{ turn.command }}</p>
                    <p class="mb-3 font-serif text-[1.03rem] leading-relaxed text-foreground/90">
                      {{ turn.narration }}
                    </p>

                    <p class="mb-3 inline-flex items-center gap-1.5 rounded-md border border-border/60 bg-background/80 px-2.5 py-1 text-xs text-muted-foreground">
                      <Dice5 class="size-3.5" />
                      {{ turn.mechanicalHint }}
                    </p>

                    <div class="flex flex-wrap gap-2">
                      <button
                        v-for="option in turn.options"
                        :key="option.id"
                        type="button"
                        :class="['choice-option', continuationMeta[option.type].className]"
                      >
                        <component :is="continuationMeta[option.type].icon" class="size-3.5" />
                        <span>{{ option.label }}</span>
                      </button>
                    </div>
                  </article>
                </ScrollArea>

                <div class="mt-4 rounded-xl border border-border/70 bg-background/60 p-3">
                  <p class="text-xs uppercase tracking-wider text-muted-foreground">Command Dock</p>
                  <div class="mt-2 flex gap-2">
                    <Input
                      id="command-input"
                      name="commandInput"
                      placeholder="Try: scout station perimeter before dawn"
                    />
                    <Button>Act</Button>
                    <Dialog>
                      <DialogTrigger as-child>
                        <Button variant="outline" size="icon" aria-label="Model settings">
                          <SlidersHorizontal class="size-4" />
                        </Button>
                      </DialogTrigger>
                      <DialogContent>
                        <DialogHeader>
                          <DialogTitle>Model Settings</DialogTitle>
                          <DialogDescription>Two-model setup available in play context.</DialogDescription>
                        </DialogHeader>
                        <div class="space-y-3">
                          <div class="space-y-1.5">
                            <label for="primary-model" class="text-sm">Primary model</label>
                            <Select>
                              <SelectTrigger id="primary-model"><SelectValue placeholder="Select model" /></SelectTrigger>
                              <SelectContent>
                                <SelectItem value="gpt-5.2">gpt-5.2</SelectItem>
                                <SelectItem value="claude-sonnet">claude-sonnet</SelectItem>
                              </SelectContent>
                            </Select>
                          </div>
                          <div class="space-y-1.5">
                            <label for="backup-model" class="text-sm">Backup model</label>
                            <Select>
                              <SelectTrigger id="backup-model"><SelectValue placeholder="Select model" /></SelectTrigger>
                              <SelectContent>
                                <SelectItem value="gpt-5-mini">gpt-5-mini</SelectItem>
                                <SelectItem value="claude-haiku">claude-haiku</SelectItem>
                              </SelectContent>
                            </Select>
                          </div>
                        </div>
                        <DialogFooter>
                          <Button variant="outline">Cancel</Button>
                          <Button>Save</Button>
                        </DialogFooter>
                      </DialogContent>
                    </Dialog>
                  </div>
                  <div class="mt-2 flex flex-wrap gap-2">
                    <Button variant="ghost" size="sm">Undo</Button>
                    <Button variant="ghost" size="sm">Regenerate</Button>
                    <Button variant="ghost" size="sm">Help</Button>
                  </div>
                </div>
              </div>

              <aside class="rounded-xl border border-border/70 bg-background/60 p-4">
                <h3 class="mb-3 text-base font-semibold">State Rail</h3>
                <div class="space-y-3 text-sm">
                  <div>
                    <p class="text-xs uppercase tracking-wider text-muted-foreground">Location</p>
                    <p>Terminal 6, rail district</p>
                  </div>
                  <Separator />
                  <div>
                    <p class="text-xs uppercase tracking-wider text-muted-foreground">Active Threads</p>
                    <p>Nightfall Ledger, Missing Dispatcher</p>
                  </div>
                  <Separator />
                  <div>
                    <p class="text-xs uppercase tracking-wider text-muted-foreground">Party Mood</p>
                    <p>Guarded optimism</p>
                  </div>
                </div>
              </aside>
            </div>
          </section>
        </TabsContent>

        <TabsContent value="creation">
          <section class="surface-panel rounded-2xl p-6">
            <div class="mb-4 flex items-end justify-between gap-2">
              <div>
                <h2 class="text-xl font-semibold">Creation (Two-Panel)</h2>
                <p class="text-sm text-muted-foreground">Structured composer on the left, AI assistant chat on the right.</p>
              </div>
              <Button variant="outline" size="sm">
                <WandSparkles class="mr-2 size-4" />
                Generate Draft
              </Button>
            </div>

            <div class="grid gap-4 lg:grid-cols-[1.7fr_1fr]">
              <div class="rounded-xl border border-border/70 bg-background/65 p-4">
                <div class="grid gap-4 md:grid-cols-2">
                  <div class="space-y-2">
                    <label for="scenario-name" class="text-sm font-medium">Scenario Name</label>
                    <Input id="scenario-name" placeholder="Last Tram To Dusk Harbor" />
                  </div>
                  <div class="space-y-2">
                    <label for="ruleset" class="text-sm font-medium">Ruleset</label>
                    <Select>
                      <SelectTrigger id="ruleset">
                        <SelectValue placeholder="Select ruleset" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="midnight-accord">Midnight Accord</SelectItem>
                        <SelectItem value="cathedral-dust">Cathedral Dust</SelectItem>
                        <SelectItem value="citizen-network">Citizen Network</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div class="space-y-2 md:col-span-2">
                    <label for="opening" class="text-sm font-medium">Opening Scene</label>
                    <Textarea id="opening" rows="5" placeholder="Paint tone, stakes, and immediate tension..." />
                  </div>
                  <div class="flex items-center gap-2">
                    <Checkbox id="fail-forward" />
                    <label for="fail-forward" class="text-sm">Enable fail-forward resolution</label>
                  </div>
                  <div class="flex items-center justify-between rounded-md border border-border/70 px-3 py-2">
                    <label for="assistive" class="text-sm">Show tactical side rail by default</label>
                    <Switch id="assistive" v-model:checked="assistivePanelEnabled" />
                  </div>
                </div>

                <div class="mt-4 flex flex-wrap gap-2">
                  <Button>Save Draft</Button>
                  <Button variant="secondary">Save and Start Session</Button>
                </div>
              </div>

              <aside class="rounded-xl border border-border/70 bg-background/65 p-4">
                <div class="mb-3 flex items-center justify-between">
                  <h3 class="text-base font-semibold">AI Assistant</h3>
                  <Badge variant="outline">Context aware</Badge>
                </div>

                <ScrollArea class="h-[280px] rounded-lg border border-border/60 bg-background/70 px-3 py-2">
                  <div class="space-y-2">
                    <div
                      v-for="message in assistantMessages"
                      :key="message.id"
                      :class="[
                        'rounded-lg px-3 py-2 text-sm leading-relaxed',
                        message.role === 'assistant'
                          ? 'bg-accent/35 text-accent-foreground'
                          : 'bg-secondary text-secondary-foreground',
                      ]"
                    >
                      {{ message.text }}
                    </div>
                  </div>
                </ScrollArea>

                <div class="mt-3 space-y-2">
                  <Input id="assistant-prompt" name="assistantPrompt" placeholder="Ask assistant to refine tone, stakes, or hooks" />
                  <div class="flex gap-2">
                    <Button size="sm">Send</Button>
                    <Button size="sm" variant="ghost">Insert Suggestion</Button>
                  </div>
                </div>
              </aside>
            </div>
          </section>
        </TabsContent>
      </Tabs>

      <Card class="surface-panel rounded-2xl">
        <CardHeader>
          <CardTitle class="text-xl font-semibold">Micro-Interactions</CardTitle>
          <CardDescription>Reusable interaction language across all screens.</CardDescription>
        </CardHeader>
        <CardContent class="flex flex-wrap items-center gap-3">
          <Button>Primary</Button>
          <Button variant="secondary">Secondary</Button>
          <Button variant="outline">Outline</Button>
          <Button variant="ghost">
            <FolderKanban class="mr-2 size-4" />
            Open Drafts
          </Button>
          <Button variant="ghost">
            <BookOpenText class="mr-2 size-4" />
            Browse Lore
          </Button>
          <Dialog>
            <DialogTrigger as-child>
              <Button variant="ghost">Open Confirmation</Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Archive Session?</DialogTitle>
                <DialogDescription>
                  This preserves the timeline and removes it from active queues.
                </DialogDescription>
              </DialogHeader>
              <DialogFooter>
                <Button variant="outline">Cancel</Button>
                <Button>Archive</Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </CardContent>
      </Card>
    </div>
  </main>
</template>
