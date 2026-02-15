export interface SessionInfoV2 {
  session_id: string
  character_name: string
  message_count: number
  last_message_time: string
  last_character_response: string | null
  scenario_name: string | null
  turn_count: number | null
}

export interface SessionMessageV2 {
  role: string
  content: string
  created_at: string
}

export interface SessionDetailsV2 {
  session_id: string
  character_name: string
  message_count: number
  last_messages: SessionMessageV2[]
  last_message_time: string
}

export interface RulesetSummaryV2 {
  id: string
  name: string
  drive_count: number
  skill_count: number
  created_at: string
}

export interface WorldLoreSummaryV2 {
  id: string
  name: string
  tags: string[]
  content_preview: string
}

export interface ScenarioSummaryV2 {
  id: string
  summary: string
  character_ids: string[]
  ruleset_id: string
  created_at: string
  updated_at: string
}

export interface ListScenariosResponseV2 {
  scenarios: ScenarioSummaryV2[]
}

export interface ScenarioDetailV2 {
  summary: string
  intro_message: string
  character_ids: string[]
  persona_id: string
  ruleset_id: string
  lore_ids: string[]
  location: string
  time_context: string
  atmosphere: string
  plot_hooks: string[]
  stakes: string
  character_goals: Record<string, string>
  potential_directions: string[]
}

export interface SessionStateWorld {
  location: string
  time: string
  characters_present: string[]
}

export interface SessionStateResponseV2 {
  session_id: string
  world_state: SessionStateWorld
  turn_counter: number
  status: string
  character_states: Record<string, unknown>
  narration_history: string[]
}

export interface SessionCharacterSummaryV2 {
  character_id: string
  character_name: string
  is_present: boolean
  drives: Record<string, number>
  active_intent_goal: string | null
}

export interface ContinuationOptionV2 {
  type: 'action' | 'dialogue' | 'relocation' | 'time_skip'
  description: string
  target: string | null
}

export interface TurnStreamEventV2 {
  type: string
  step?: string
  text?: string
  message?: string
  options?: ContinuationOptionV2[]
  turn?: number
}

export interface StartSessionRequestV2 {
  scenario_id: string
  processor_type?: string
  mini_processor_type?: string
  backup_processor_type?: string
}

export interface StartSessionResponseV2 {
  session_id: string
}

export interface CreateRulesetInput {
  name: string
  rules_text?: string
  state_schemas?: Record<string, unknown>
  config?: Record<string, unknown>
}

export interface CreateWorldLoreInput {
  name: string
  content: string
  tags: string[]
}

export interface CharacterSummaryV2 {
  id: string
  name: string
  tagline: string
}

export interface CharacterDetailV2 {
  name: string
  tagline: string
  backstory: string
  personality: string
  appearance: string
  interests: string[]
  dislikes: string[]
  desires: string[]
  kinks: string[]
  is_persona: boolean
  starting_drives: Record<string, number>
  starting_skills: Record<string, number>
  starting_emotional_state: Record<string, unknown>
}
