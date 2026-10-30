import { mount } from '@vue/test-utils'
import type { ToolCallEntry } from '@/protocol/types'
import ToolStamp from './ToolStamp.vue'

function entry(overrides: Partial<ToolCallEntry> = {}): ToolCallEntry {
  return {
    kind: 'tool_call',
    tool_call_id: 't1',
    tool_name: 'read_lore',
    arguments: '{"filename":"sealed/vera.md"}',
    result: 'She is the ferryman.',
    outcome: 'success',
    ...overrides,
  }
}

describe('ToolStamp', () => {
  it('shows the request and result of an ordinary call when opened', async () => {
    const wrapper = mount(ToolStamp, { props: { entry: entry() } })
    await wrapper.get('.stamp__button').trigger('click')
    expect(wrapper.text()).toContain('She is the ferryman.')
    expect(wrapper.find('.stamp__seal').exists()).toBe(false)
  })

  it('shows only the name, outcome and a sealed mark for a sealed call', () => {
    const wrapper = mount(ToolStamp, { props: { entry: entry({ sealed: true }) } })
    expect(wrapper.text()).toContain('read_lore')
    expect(wrapper.text()).toContain('success')
    expect(wrapper.get('.stamp__seal').text()).toBe('sealed')
    expect(wrapper.text()).not.toContain('ferryman')
    expect(wrapper.text()).not.toContain('vera.md')
  })

  it('keeps a sealed call hidden when opened, until the user reveals it', async () => {
    const wrapper = mount(ToolStamp, { props: { entry: entry({ sealed: true }) } })
    await wrapper.get('.stamp__button').trigger('click')
    expect(wrapper.text()).toContain('spoil')
    expect(wrapper.text()).not.toContain('ferryman')
    expect(wrapper.text()).not.toContain('vera.md')

    await wrapper.get('.stamp__reveal').trigger('click')
    expect(wrapper.text()).toContain('She is the ferryman.')
    expect(wrapper.text()).toContain('vera.md')
  })
})
