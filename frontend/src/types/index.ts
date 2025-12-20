export interface CharacterSummary {
  id: string
  name: string
  tagline: string
}

export interface Character {
  name: string
  tagline: string
  backstory: string
  personality?: string
  appearance?: string
  relationships?: Record<string, string>
  key_locations?: string[]
  setting_description?: string
  interests?: string[]
  dislikes?: string[]
  desires?: string[]
  kinks?: string[]
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
}

export interface InteractRequest {
  character_name: string
  user_message: string
  session_id?: string | null
  processor_type?: string
  backup_processor_type?: string
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
  type: 'chunk' | 'complete' | 'error' | 'session' | 'thinking' | 'command'
  session_id?: string
  content?: string
  error?: string
  stage?: string // For thinking events: 'summarizing' | 'deliberating' | 'responding'
  succeeded?: string // For command events: 'true' | 'false'
}

export interface LocalSettings {
  aiProcessor: string
  backupProcessor: string
  lastSelectedCharacter?: string
}

export interface SessionMessage {
  role: 'user' | 'assistant'
  content: string
  created_at: string
}

export interface SessionDetails {
  session_id: string
  character_name: string
  message_count: number
  last_messages: SessionMessage[]
  last_message_time: string
}

export interface Scenario {
  summary: string
  intro_message: string
  narrative_category: string
  character_id?: string
  persona_id?: string
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
  persona_id?: string
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
  created_at: string
  updated_at: string
}

export interface ListScenariosResponse {
  character_name: string
  scenarios: ScenarioSummary[]
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
  character_name: string
  intro_message?: string
  scenario_id?: string
  processor_type?: string
  backup_processor_type?: string
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
