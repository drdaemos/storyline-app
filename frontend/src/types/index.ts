export interface Character {
  name: string
  role: string
  backstory: string
  personality?: string
  appearance?: string
  relationships?: Record<string, string>
  key_locations?: string[]
  setting_description?: string
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
}

export interface CreateCharacterRequest {
  data: Character | string
  is_yaml_text?: boolean
}

export interface CreateCharacterResponse {
  message: string
  character_filename: string
}

export interface StreamEvent {
  type: 'chunk' | 'complete' | 'error' | 'session' | 'thinking'
  session_id?: string
  content?: string
  error?: string
  stage?: string  // For thinking events: 'summarizing' | 'deliberating' | 'responding'
}

export interface LocalSettings {
  aiProcessor: string
  theme: string
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