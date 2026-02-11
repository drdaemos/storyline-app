export interface CharacterSummary {
  id: string
  name: string
  tagline: string
  tags?: string[]
  is_persona?: boolean
}

export interface Character {
  name: string
  tagline: string
  backstory: string
  personality?: string
  appearance?: string
  relationships?: Record<string, string>
  ruleset_id?: string
  ruleset_stats?: Record<string, number | string | boolean>
  interests?: string[]
  dislikes?: string[]
  desires?: string[]
  kinks?: string[]
  tags?: string[]
}

export interface SessionInfo {
  session_id: string
  character_name: string
  message_count: number
  last_message_time: string
  last_character_response: string | null
}

export interface ChatMessage {
  author: string
  content: string
  isUser: boolean
  timestamp: Date
  metaText?: string | null
}

export interface InteractRequest {
  character_name: string
  user_message: string
  session_id: string
}

export interface CreateCharacterRequest {
  data: Character | string
  is_yaml_text?: boolean
  is_persona?: boolean
}

export interface CreateCharacterResponse {
  message: string
  character_filename: string
}

export interface GenerateCharacterRequest {
  partial_character: Partial<Character>
  processor_type?: string
  backup_processor_type?: string
}

export interface GenerateCharacterResponse {
  character: Character
  generated_fields: string[]
}

export interface StreamEvent {
  type: 'chunk' | 'complete' | 'error' | 'session' | 'thinking'
  session_id?: string
  content?: string
  error?: string
  stage?: string // For thinking events: 'summarizing' | 'deliberating' | 'responding'
  suggested_actions?: string[]
  meta_text?: string | null
}

export interface LocalSettings {
  largeModelKey: string
  smallModelKey: string
  selectedPersonaId?: string
  lastSelectedCharacter?: string
}

export interface SessionMessage {
  role: 'user' | 'assistant'
  content: string
  created_at: string
  meta_text?: string | null
}

export interface SessionDetails {
  session_id: string
  character_name: string
  message_count: number
  last_messages: SessionMessage[]
  last_message_time: string
  suggested_actions?: string[]
}

export interface Scenario {
  summary: string
  intro_message: string
  narrative_category: string
  character_id?: string
  character_ids?: string[]
  character_tags?: string[]
  ruleset_id?: string
  persona_id?: string
  world_lore_id?: string | null
  world_lore_tags?: string[]
  scene_seed?: Record<string, unknown>
  location?: string
  time_context?: string
  atmosphere?: string
  plot_hooks?: string[]
  stakes?: string
  character_goals?: Record<string, string>
  potential_directions?: string[]
  suggested_persona_id?: string
  suggested_persona_reason?: string
}

export interface PartialScenario {
  summary?: string
  intro_message?: string
  narrative_category?: string
  character_id?: string
  character_ids?: string[]
  character_tags?: string[]
  ruleset_id?: string
  persona_id?: string
  world_lore_id?: string | null
  world_lore_tags?: string[]
  scene_seed?: Record<string, unknown>
  location?: string
  time_context?: string
  atmosphere?: string
  plot_hooks?: string[]
  stakes?: string
  character_goals?: Record<string, string>
  potential_directions?: string[]
  suggested_persona_id?: string
  suggested_persona_reason?: string
}

export interface PersonaSummary {
  id: string
  name: string
  tagline?: string
  personality?: string
}

export interface ScenarioCreationRequest {
  user_message: string
  current_scenario: PartialScenario
  character_name: string
  character_names?: string[]
  persona_id?: string | null
  available_personas?: PersonaSummary[]
  conversation_history?: Array<{
    author: string
    content: string
    is_user: boolean
  }>
  processor_type?: string
  backup_processor_type?: string
}

export interface ScenarioCreationStreamEvent {
  type: 'message' | 'update' | 'complete' | 'error'
  message?: string
  updates?: PartialScenario
  error?: string
}

export interface SaveScenarioRequest {
  scenario: Scenario
  scenario_id?: string
}

export interface SaveScenarioResponse {
  scenario_id: string
}

export interface ScenarioSummary {
  id: string
  summary: string
  narrative_category: string
  character_id: string
  character_ids?: string[]
  character_tags?: string[]
  ruleset_id?: string
  world_lore_id?: string | null
  world_lore_tags?: string[]
  created_at: string
  updated_at: string
}

export interface ListScenariosResponse {
  character_name: string
  scenarios: ScenarioSummary[]
}

export interface WorldLoreAsset {
  id: string
  name: string
  lore_text: string
  tags: string[]
  keywords: string[]
  lore_json?: Record<string, unknown> | null
  created_at: string
  updated_at: string
}

export interface SaveWorldLoreRequest {
  name: string
  lore_text: string
  tags?: string[]
  keywords?: string[]
  lore_json?: Record<string, unknown> | null
  world_lore_id?: string
}

export interface SaveWorldLoreResponse {
  world_lore_id: string
  message?: string
}

export interface PartialWorldLore {
  name?: string
  lore_text?: string
  tags?: string[]
  keywords?: string[]
}

export interface WorldLoreCreationRequest {
  user_message: string
  current_world_lore: PartialWorldLore
  conversation_history?: Array<{
    author: string
    content: string
    is_user: boolean
  }>
  processor_type?: string
  backup_processor_type?: string
}

export interface WorldLoreCreationStreamEvent {
  type: 'message' | 'update' | 'complete' | 'error'
  message?: string
  updates?: PartialWorldLore
  error?: string
}

export interface GenerateScenariosRequest {
  character_name: string
  count: number
  mood: string
  persona_id?: string | null
  processor_type?: string
  backup_processor_type?: string
}

export interface GenerateScenariosResponse {
  character_name: string
  scenarios: Scenario[]
}

export interface StartSessionRequest {
  character_name?: string
  intro_message?: string
  scenario_id?: string
  persona_id?: string | null
  ruleset_id?: string
  world_lore_id?: string
  scene_seed?: Record<string, unknown>
  small_model_key: string
  large_model_key: string
}

export interface StartSessionResponse {
  session_id: string
}

export interface CharacterCreationRequest {
  user_message: string
  current_character: Partial<Character>
  conversation_history?: Array<{
    author: string
    content: string
    is_user: boolean
  }>
  processor_type?: string
  backup_processor_type?: string
}

export interface CharacterCreationStreamEvent {
  type: 'message' | 'update' | 'complete' | 'error'
  message?: string // AI message to show in chat
  updates?: Partial<Character> // Character fields to update
  error?: string
}

export interface SessionPersonaResponse {
  persona_id: string | null
  persona_name: string | null
}

export interface RulesetDefinition {
  id: string
  name: string
  rulebook_text: string
  character_stat_schema: Record<string, unknown>
  scene_state_schema: Record<string, unknown>
  mechanics_guidance?: Record<string, unknown> | null
}
