// TypeScript mirrors of the VN backend models (src/models/vn/*)

export type VNStateValue = boolean | number | string

export interface VNPendingOption {
  index: number
  intent: string
}

export interface VNPending {
  kind: 'choice' | 'extension'
  prompt: string
  options: VNPendingOption[]
  deeper_domain: string
}

export interface VNEngineView {
  status: 'running' | 'ended'
  scene_id: string
  beat_id: string
  pending: VNPending | null
  ending_id: string | null
  vars: Record<string, VNStateValue>
  visited: string[]
}

export type VNEngineEvent =
  | { type: 'scene_entered'; scene_id: string; intent: string }
  | { type: 'beat_entered'; scene_id: string; beat_id: string; intent: string }
  | {
      type: 'check_resolved'
      beat_id: string
      roll: number
      difficulty: number
      modifier_total: number
      success: boolean
    }
  | { type: 'choice_made'; intent: string }
  | { type: 'went_deeper'; beat_id: string; deeper_domain: string }
  | { type: 'ending_reached'; ending_id: string; intent: string }

export interface VNAction {
  type: 'proceed' | 'choose' | 'go_deeper'
  option_index?: number | null
}

export interface VNNarrationEntry {
  event_index: number
  text: string
}

export interface VNSessionView {
  session_id: string
  script_id: string
  script_title: string
  status: 'running' | 'ended'
  view: VNEngineView
  new_events: VNEngineEvent[]
  event_log: VNEngineEvent[]
  narration_log: VNNarrationEntry[]
}

export interface VNSessionSummary {
  session_id: string
  script_id: string
  script_title: string
  status: 'running' | 'ended'
  created_at: string
  updated_at: string
}

export interface VNScriptSummary {
  id: string
  title: string
  validation_status: 'unvalidated' | 'valid' | 'invalid'
  scene_count: number
  ending_count: number
  created_at: string
  updated_at: string
}

export type VNCondition =
  | { var: string; op: '==' | '>=' | '<='; value: VNStateValue }
  | { visited: string; value?: boolean }

export type VNGuard = VNCondition[]

export interface VNEffect {
  var: string
  op: 'set' | 'inc' | 'dec'
  value: VNStateValue
}

export interface VNExitEdge {
  target_scene: string
  guard?: VNGuard
  priority?: number
}

export interface VNChoiceOption {
  intent: string
  guard?: VNGuard
  target: string
}

export interface VNExtension {
  deeper_domain: string
}

export interface VNBeatBase {
  id: string
  type: 'plain' | 'check' | 'choice' | 'ending'
  intent: string
  effects?: VNEffect[]
  extension?: VNExtension | null
}

export interface VNPlainBeat extends VNBeatBase {
  type: 'plain'
  next?: string | null
  exit_edges?: VNExitEdge[] | null
  exit?: 'open' | null
}

export interface VNCheckBeat extends VNBeatBase {
  type: 'check'
  check: {
    difficulty: number
    modifiers?: Array<VNCondition & { mod: number }>
    on_success: string
    on_failure: string
  }
}

export interface VNChoiceBeat extends VNBeatBase {
  type: 'choice'
  options: VNChoiceOption[]
}

export interface VNEndingBeat extends VNBeatBase {
  type: 'ending'
  ending_id: string
}

export type VNBeat = VNPlainBeat | VNCheckBeat | VNChoiceBeat | VNEndingBeat

export interface VNScene {
  id: string
  intent: string
  prerequisites?: VNGuard
  repeatable?: boolean
  forced?: number | null
  entry_beat: string
  beats: VNBeat[]
}

export interface VNScript {
  meta: {
    title: string
    protagonist: string
  }
  state_vars: Array<
    | { name: string; type: 'flag'; initial: boolean }
    | { name: string; type: 'counter'; max: number; initial: number }
    | { name: string; type: 'enum'; values: string[]; initial: string }
  >
  start_scene: string
  scenes: VNScene[]
}

export interface VNScriptDetail {
  id: string
  title: string
  validation_status: 'unvalidated' | 'valid' | 'invalid'
  script: VNScript
  created_at: string
  updated_at: string
}

export interface VNValidationIssue {
  code: string
  severity: 'error' | 'warning'
  message: string
  scene_id: string | null
  beat_id: string | null
  state: Record<string, VNStateValue> | null
}

export interface VNValidationReport {
  issues: VNValidationIssue[]
}

export interface VNImportResponse {
  script_id: string
  validation_status: string
  report: VNValidationReport
}

// Generation input (mirrors src/models/vn/input.py)
export interface VNInputCharacter {
  name: string
  background: string
  appearance: string
  protagonist: boolean
}

export interface VNGenerationInput {
  characters: VNInputCharacter[]
  setting: { world_description: string; anchors: string[] }
  rules: string
  premise: {
    synopsis: string
    protagonist_goal: string
    scope: { target_scenes: number; target_endings: number }
  }
}

// SSE events from POST /api/vn/scripts/generate and /api/vn/generation-jobs/{id}/resume
export type VNGenerationEvent =
  | { type: 'started'; job_id: string }
  | {
      type: 'progress'
      stage: 'outline' | 'scene_graph' | 'mechanics'
      status: 'started' | 'passed' | 'repairing' | 'failed'
      scene_id: string | null
      detail: string
    }
  | { type: 'complete'; script_id: string; validation_status: string }
  | { type: 'error'; job_id: string; error: string; issues: VNValidationIssue[] }

// Persisted generation run (failed runs keep their checkpoint and can be resumed)
export interface VNSceneOutlineItem {
  id: string
  intent: string
  synopsis: string
  exit_mode: 'open' | 'directed' | 'ending'
  ending_ids: string[]
}

export interface VNScriptOutline {
  title: string
  start_scene: string
  scenes: VNSceneOutlineItem[]
}

export interface VNGenerationJob {
  job_id: string
  status: 'running' | 'failed'
  error: string | null
  processor_type: string
  synopsis: string
  outline: VNScriptOutline | null
  completed_scenes: string[]
  scenes: VNScene[]
  created_at: string
  updated_at: string
}
