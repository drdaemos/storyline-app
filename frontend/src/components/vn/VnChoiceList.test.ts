import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import VnChoiceList from './VnChoiceList.vue'
import type { VNPending } from '@/types/vn'

const choicePending: VNPending = {
  kind: 'choice',
  prompt: 'How does Mara handle the guard?',
  options: [
    { index: 0, intent: 'Persuade him' },
    { index: 1, intent: 'Slip past' },
  ],
  deeper_domain: '',
}

const extensionPending: VNPending = {
  kind: 'extension',
  prompt: 'Mara approaches the gate',
  options: [],
  deeper_domain: 'gate details',
}

describe('VnChoiceList', () => {
  it('renders nothing when no input is pending', () => {
    const wrapper = mount(VnChoiceList, { props: { pending: null } })
    expect(wrapper.find('button').exists()).toBe(false)
  })

  it('renders one button per eligible option with the prompt', () => {
    const wrapper = mount(VnChoiceList, { props: { pending: choicePending } })
    expect(wrapper.text()).toContain('How does Mara handle the guard?')
    const buttons = wrapper.findAll('button.vn-option')
    expect(buttons).toHaveLength(2)
    expect(buttons[0].text()).toBe('Persuade him')
    expect(buttons[1].text()).toBe('Slip past')
  })

  it('emits choose with the option index', async () => {
    const wrapper = mount(VnChoiceList, { props: { pending: choicePending } })
    await wrapper.findAll('button.vn-option')[1].trigger('click')
    expect(wrapper.emitted('choose')).toEqual([[1]])
  })

  it('renders go-deeper / proceed at extension points and emits accordingly', async () => {
    const wrapper = mount(VnChoiceList, { props: { pending: extensionPending } })
    expect(wrapper.find('button.vn-option').exists()).toBe(false)
    await wrapper.find('button.vn-deeper').trigger('click')
    await wrapper.find('button.vn-proceed').trigger('click')
    expect(wrapper.emitted('goDeeper')).toHaveLength(1)
    expect(wrapper.emitted('proceed')).toHaveLength(1)
  })

  it('disables buttons while an action is in flight', () => {
    const wrapper = mount(VnChoiceList, { props: { pending: choicePending, disabled: true } })
    for (const button of wrapper.findAll('button')) {
      expect(button.attributes('disabled')).toBeDefined()
    }
  })
})
