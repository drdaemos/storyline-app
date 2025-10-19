import { describe, it, expect, beforeEach, vi } from 'vitest'
import { useLocalSettings } from './useLocalSettings'

describe('useLocalSettings', () => {
  beforeEach(() => {
    // Clear localStorage before each test
    localStorage.clear()
    vi.clearAllMocks()
  })

  it('should return the same settings ref across multiple instances', () => {
    const instance1 = useLocalSettings()
    const instance2 = useLocalSettings()

    // Both instances should reference the same settings object
    expect(instance1.settings).toBe(instance2.settings)
  })

  it('should update settings across all instances when changed in one', async () => {
    const instance1 = useLocalSettings()
    const instance2 = useLocalSettings()

    // Change settings in instance1
    instance1.settings.value.aiProcessor = 'claude-sonnet'

    // Wait for Vue's reactivity to propagate
    await new Promise(resolve => setTimeout(resolve, 0))

    // instance2 should see the change
    expect(instance2.settings.value.aiProcessor).toBe('claude-sonnet')
  })

  it('should save changes to localStorage', async () => {
    const instance = useLocalSettings()

    // Change settings
    instance.settings.value.aiProcessor = 'gpt'
    instance.settings.value.backupProcessor = 'claude-haiku'

    // Wait for the watcher to trigger
    await new Promise(resolve => setTimeout(resolve, 10))

    // Check localStorage
    expect(localStorage.getItem('storyline_ai_processor')).toBe('gpt')
    expect(localStorage.getItem('storyline_backup_processor')).toBe('claude-haiku')
  })

  it('should load settings from localStorage on initialization', () => {
    // Set values in localStorage before creating instance
    localStorage.setItem('storyline_ai_processor', 'grok')
    localStorage.setItem('storyline_backup_processor', 'deepseek')

    // Create a new instance (need to reload the module to re-initialize)
    const instance = useLocalSettings()
    instance.loadSettings()

    expect(instance.settings.value.aiProcessor).toBe('grok')
    expect(instance.settings.value.backupProcessor).toBe('deepseek')
  })
})
