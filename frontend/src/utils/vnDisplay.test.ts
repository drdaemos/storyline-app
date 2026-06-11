import { describe, expect, it } from 'vitest'
import { buildDisplayBlocks, describeEvent, formatGenerationJobPreview, formatScriptPreview } from './vnDisplay'
import type { VNEngineEvent, VNGenerationJob, VNNarrationEntry, VNScript } from '@/types/vn'

const events: VNEngineEvent[] = [
  { type: 'scene_entered', scene_id: 'sc_gate', intent: 'Mara reaches the gate' },
  { type: 'beat_entered', scene_id: 'sc_gate', beat_id: 'b_guard', intent: 'A guard blocks the way' },
  { type: 'check_resolved', beat_id: 'b_sneak', roll: 14, difficulty: 12, modifier_total: 2, success: true },
  { type: 'choice_made', intent: 'Slip past the guard' },
]

describe('buildDisplayBlocks', () => {
  it('shows all events structurally when nothing is narrated', () => {
    const blocks = buildDisplayBlocks(events, [])
    expect(blocks).toHaveLength(4)
    expect(blocks.every((block) => block.kind === 'event')).toBe(true)
  })

  it('replaces covered events with narration and keeps the rest', () => {
    const narration: VNNarrationEntry[] = [{ event_index: 2, text: 'Mara sized up the guard.' }]
    const blocks = buildDisplayBlocks(events, narration)
    expect(blocks[0]).toEqual({ kind: 'narration', text: 'Mara sized up the guard.' })
    expect(blocks.slice(1)).toEqual([
      { kind: 'event', event: events[2] },
      { kind: 'event', event: events[3] },
    ])
  })

  it('orders narration entries by event index and covers up to the last one', () => {
    const narration: VNNarrationEntry[] = [
      { event_index: 4, text: 'Then she was through.' },
      { event_index: 2, text: 'Mara sized up the guard.' },
    ]
    const blocks = buildDisplayBlocks(events, narration)
    expect(blocks).toEqual([
      { kind: 'narration', text: 'Mara sized up the guard.' },
      { kind: 'narration', text: 'Then she was through.' },
    ])
  })
})

describe('describeEvent', () => {
  it('marks scene entries and endings as headings', () => {
    expect(describeEvent(events[0])).toBe('— Mara reaches the gate —')
    expect(describeEvent({ type: 'ending_reached', ending_id: 'end_flight', intent: 'Mara flees the town' })).toBe('THE END — Mara flees the town')
  })

  it('renders check results with roll, modifier and outcome', () => {
    expect(describeEvent(events[2])).toBe('Check: roll 14 (+2) vs 12 — success')
    expect(describeEvent({ type: 'check_resolved', beat_id: 'b_x', roll: 3, difficulty: 12, modifier_total: 0, success: false })).toBe('Check: roll 3 vs 12 — failure')
    expect(describeEvent({ type: 'check_resolved', beat_id: 'b_x', roll: 9, difficulty: 10, modifier_total: -2, success: false })).toBe('Check: roll 9 (-2) vs 10 — failure')
  })

  it('renders choices, beats and extensions as plain lines', () => {
    expect(describeEvent(events[3])).toBe('> Slip past the guard')
    expect(describeEvent(events[1])).toBe('A guard blocks the way')
    expect(describeEvent({ type: 'went_deeper', beat_id: 'b_guard', deeper_domain: 'the gate watch' })).toBe('(a closer look: the gate watch)')
  })
})

const script: VNScript = {
  meta: { title: 'The Locked Granary', protagonist: 'Mara' },
  state_vars: [
    { name: 'has_key', type: 'flag', initial: false },
    { name: 'guard_trust', type: 'counter', max: 3, initial: 0 },
  ],
  start_scene: 'sc_gate',
  scenes: [
    {
      id: 'sc_gate',
      intent: 'Talk your way past the granary guard',
      prerequisites: [],
      repeatable: false,
      forced: null,
      entry_beat: 'b_talk',
      beats: [
        {
          id: 'b_talk',
          type: 'choice',
          intent: 'How does Mara handle the guard?',
          options: [
            { intent: 'Persuade him', target: 'b_persuade' },
            { intent: 'Mention his sister vouched for you', guard: [{ var: 'guard_trust', op: '>=', value: 1 }], target: 'b_vouched' },
          ],
        },
        {
          id: 'b_sneak',
          type: 'check',
          intent: 'Mara tries to slip past unnoticed',
          check: {
            difficulty: 12,
            modifiers: [{ var: 'has_key', op: '==', value: true, mod: 2 }],
            on_success: 'b_inside',
            on_failure: 'b_caught',
          },
        },
      ],
    },
  ],
}

describe('formatScriptPreview', () => {
  it('renders a finished script as readable sections', () => {
    const preview = formatScriptPreview(script)

    expect(preview).toContain('The Locked Granary')
    expect(preview).toContain('Protagonist: Mara')
    expect(preview).toContain('Scene 1: Talk your way past the granary guard')
    expect(preview).toContain('1. Persuade him -> b_persuade')
    expect(preview).toContain('check: difficulty 12')
    expect(preview).toContain('has_key == true (+2)')
  })
})

describe('formatGenerationJobPreview', () => {
  it('mixes completed scene detail with planned outline scenes', () => {
    const job: VNGenerationJob = {
      job_id: 'job-1',
      status: 'failed',
      error: 'stopped',
      processor_type: 'mock',
      synopsis: 'A gate problem',
      outline: {
        title: 'The Locked Granary',
        start_scene: 'sc_gate',
        scenes: [
          { id: 'sc_gate', intent: 'Talk past the guard', synopsis: 'Mara negotiates.', exit_mode: 'open', ending_ids: [] },
          { id: 'sc_reckoning', intent: 'Face the granary master', synopsis: 'Mara explains herself.', exit_mode: 'ending', ending_ids: ['end_bargain'] },
        ],
      },
      completed_scenes: ['sc_gate'],
      scenes: script.scenes,
      created_at: '2026-06-11T00:00:00',
      updated_at: '2026-06-11T00:00:00',
    }

    const preview = formatGenerationJobPreview(job)

    expect(preview).toContain('Generation status: failed')
    expect(preview).toContain('Completed scenes: 1')
    expect(preview).toContain('b_talk [choice]')
    expect(preview).toContain('Scene 2: Face the granary master')
    expect(preview).toContain('status: planned')
    expect(preview).toContain('synopsis: Mara explains herself.')
  })
})
