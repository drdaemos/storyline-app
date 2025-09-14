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
  id: string
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
  type: 'chunk' | 'complete'
  content?: string
}

export interface LocalSettings {
  aiProcessor: string
  theme: string
  lastSelectedCharacter?: string
}