import type {
  VNBeat,
  VNCheckBeat,
  VNChoiceBeat,
  VNCondition,
  VNEngineEvent,
  VNGenerationJob,
  VNGuard,
  VNPlainBeat,
  VNScene,
  VNScript,
  VNStateValue,
  VNNarrationEntry,
} from '@/types/vn'

export type VNDisplayBlock =
  | { kind: 'narration'; text: string }
  | { kind: 'event'; event: VNEngineEvent }

/**
 * Interleave narration with structural events for the player feed.
 * Each narration entry covers all events before its event_index; events past the
 * last narrated index are shown structurally (intents, check results, choices).
 */
export function buildDisplayBlocks(eventLog: VNEngineEvent[], narrationLog: VNNarrationEntry[]): VNDisplayBlock[] {
  const blocks: VNDisplayBlock[] = []
  let covered = 0
  const sorted = [...narrationLog].sort((a, b) => a.event_index - b.event_index)
  for (const entry of sorted) {
    blocks.push({ kind: 'narration', text: entry.text })
    covered = Math.max(covered, entry.event_index)
  }
  for (const event of eventLog.slice(covered)) {
    blocks.push({ kind: 'event', event })
  }
  return blocks
}

export function describeEvent(event: VNEngineEvent): string {
  switch (event.type) {
    case 'scene_entered':
      return `— ${event.intent} —`
    case 'beat_entered':
      return event.intent
    case 'check_resolved':
      return `Check: roll ${event.roll}${event.modifier_total ? ` (${event.modifier_total > 0 ? '+' : ''}${event.modifier_total})` : ''} vs ${event.difficulty} — ${event.success ? 'success' : 'failure'}`
    case 'choice_made':
      return `> ${event.intent}`
    case 'went_deeper':
      return `(a closer look: ${event.deeper_domain})`
    case 'ending_reached':
      return `THE END — ${event.intent}`
  }
}

export function formatScriptPreview(script: VNScript): string {
  return [
    `${script.meta.title}`,
    `Protagonist: ${script.meta.protagonist}`,
    `Start scene: ${script.start_scene}`,
    '',
    formatStateVars(script),
    '',
    ...script.scenes.map((scene, index) => formatScene(scene, index + 1)),
  ].join('\n')
}

export function formatGenerationJobPreview(job: VNGenerationJob): string {
  const title = job.outline?.title || job.synopsis || 'Untitled generation'
  const scenesById = new Map(job.scenes.map((scene) => [scene.id, scene]))
  const plannedScenes = job.outline?.scenes || []
  const sceneSections = plannedScenes.length
    ? plannedScenes.map((outlineScene, index) => {
        const scene = scenesById.get(outlineScene.id)
        if (scene) {
          return formatScene(scene, index + 1)
        }
        return [
          `Scene ${index + 1}: ${outlineScene.intent}`,
          `  id: ${outlineScene.id}`,
          '  status: planned',
          `  synopsis: ${outlineScene.synopsis}`,
          `  exit: ${outlineScene.exit_mode}${outlineScene.ending_ids.length ? ` (${outlineScene.ending_ids.join(', ')})` : ''}`,
        ].join('\n')
      })
    : [`Synopsis: ${job.synopsis}`, '', 'No outline has been generated yet.']

  return [`${title}`, `Generation status: ${job.status}`, `Completed scenes: ${job.scenes.length}`, '', ...sceneSections].join('\n')
}

function formatStateVars(script: VNScript): string {
  if (!script.state_vars.length) {
    return 'State: none'
  }
  return [
    'State:',
    ...script.state_vars.map((stateVar) => {
      if (stateVar.type === 'counter') {
        return `  - ${stateVar.name}: ${stateVar.initial}/${stateVar.max}`
      }
      if (stateVar.type === 'enum') {
        return `  - ${stateVar.name}: ${stateVar.initial} (${stateVar.values.join(', ')})`
      }
      return `  - ${stateVar.name}: ${formatValue(stateVar.initial)}`
    }),
  ].join('\n')
}

function formatScene(scene: VNScene, index: number): string {
  return [
    `Scene ${index}: ${scene.intent}`,
    `  id: ${scene.id}`,
    `  entry: ${scene.entry_beat}`,
    scene.prerequisites?.length ? `  prerequisites: ${formatGuard(scene.prerequisites)}` : null,
    scene.forced !== null && scene.forced !== undefined ? `  forced priority: ${scene.forced}` : null,
    scene.repeatable ? '  repeatable: yes' : null,
    '  Beats:',
    ...scene.beats.map(formatBeat),
  ]
    .filter((line): line is string => line !== null)
    .join('\n')
}

function formatBeat(beat: VNBeat): string {
  const lines = [`    - ${beat.id} [${beat.type}]: ${beat.intent}`]
  if (beat.effects?.length) {
    lines.push(`      effects: ${beat.effects.map((effect) => `${effect.var} ${effect.op} ${formatValue(effect.value)}`).join('; ')}`)
  }
  if (beat.extension) {
    lines.push(`      look closer: ${beat.extension.deeper_domain}`)
  }
  if (beat.type === 'plain') {
    lines.push(...formatPlainBeatRouting(beat))
  } else if (beat.type === 'check') {
    lines.push(...formatCheckBeat(beat))
  } else if (beat.type === 'choice') {
    lines.push(...formatChoiceBeat(beat))
  } else {
    lines.push(`      ending: ${beat.ending_id}`)
  }
  return lines.join('\n')
}

function formatPlainBeatRouting(beat: VNPlainBeat): string[] {
  if (beat.next) {
    return [`      next: ${beat.next}`]
  }
  if (beat.exit === 'open') {
    return ['      exit: open scene choice']
  }
  return (beat.exit_edges || []).map((edge) => `      exit -> ${edge.target_scene} (priority ${edge.priority ?? 1}${edge.guard?.length ? `, if ${formatGuard(edge.guard)}` : ''})`)
}

function formatCheckBeat(beat: VNCheckBeat): string[] {
  const lines = [`      check: difficulty ${beat.check.difficulty}`, `      success -> ${beat.check.on_success}`, `      failure -> ${beat.check.on_failure}`]
  if (beat.check.modifiers?.length) {
    lines.push(`      modifiers: ${beat.check.modifiers.map((modifier) => `${formatCondition(modifier)} (${modifier.mod >= 0 ? '+' : ''}${modifier.mod})`).join('; ')}`)
  }
  return lines
}

function formatChoiceBeat(beat: VNChoiceBeat): string[] {
  return beat.options.map((option, index) => `      ${index + 1}. ${option.intent} -> ${option.target}${option.guard?.length ? ` (if ${formatGuard(option.guard)})` : ''}`)
}

function formatGuard(guard: VNGuard): string {
  return guard.map(formatCondition).join(' and ')
}

function formatCondition(condition: VNCondition): string {
  if ('var' in condition) {
    return `${condition.var} ${condition.op} ${formatValue(condition.value)}`
  }
  return `visited(${condition.visited}) is ${condition.value ?? true}`
}

function formatValue(value: VNStateValue): string {
  if (typeof value === 'string') {
    return `"${value}"`
  }
  return String(value)
}
