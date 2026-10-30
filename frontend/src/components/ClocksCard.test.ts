import { mount } from '@vue/test-utils'
import type { ClockView } from '@/protocol/types'
import ClocksCard from './ClocksCard.vue'

const CLOCKS: ClockView[] = [
  { id: 'a', name: 'The tide', segments: 6, filled: 2 },
  { id: 'b', name: 'The audit', segments: 4, filled: 4 },
]

describe('ClocksCard', () => {
  it('renders nothing with no clocks and none hidden', () => {
    const wrapper = mount(ClocksCard, { props: { clocks: [], hidden: 0 } })
    expect(wrapper.find('section').exists()).toBe(false)
  })

  it('draws each clock with its name and filled and empty segments', () => {
    const wrapper = mount(ClocksCard, { props: { clocks: CLOCKS, hidden: 0 } })
    const items = wrapper.findAll('li')
    expect(items).toHaveLength(2)
    expect(items[0]!.text()).toContain('The tide')
    expect(items[0]!.findAll('.clock__segment')).toHaveLength(6)
    expect(items[0]!.findAll('.clock__segment--filled')).toHaveLength(2)
    expect(items[1]!.findAll('.clock__segment--filled')).toHaveLength(4)
  })

  it('marks a full clock', () => {
    const wrapper = mount(ClocksCard, { props: { clocks: CLOCKS, hidden: 0 } })
    const items = wrapper.findAll('li')
    expect(items[0]!.classes()).not.toContain('clock--full')
    expect(items[1]!.classes()).toContain('clock--full')
  })

  it('tells screen readers the name and how far along each clock is', () => {
    const wrapper = mount(ClocksCard, { props: { clocks: CLOCKS, hidden: 0 } })
    const items = wrapper.findAll('li')
    expect(items[0]!.get('.sr-only').text()).toBe('2 of 6')
    expect(items[1]!.get('.sr-only').text()).toBe('4 of 4, full')
    expect(items[0]!.get('.clock__segments').attributes('aria-hidden')).toBe('true')
  })

  it('says how many clocks are hidden, with no names', () => {
    const wrapper = mount(ClocksCard, { props: { clocks: [], hidden: 2 } })
    expect(wrapper.text()).toContain('2 hidden')
    expect(wrapper.findAll('li')).toHaveLength(0)
  })

  it('shows visible clocks together with the hidden count', () => {
    const wrapper = mount(ClocksCard, { props: { clocks: CLOCKS, hidden: 1 } })
    expect(wrapper.findAll('li')).toHaveLength(2)
    expect(wrapper.text()).toContain('1 hidden')
  })
})
