import { mount } from '@vue/test-utils'
import type { AgendaItem } from '@/protocol/types'
import AgendaCard from './AgendaCard.vue'

const ITEMS: AgendaItem[] = [
  { id: 'a', title: 'The island', status: 'settled', outcome: 'A station on a ferry line' },
  { id: 'b', title: 'Scene one', status: 'working', outcome: '' },
  { id: 'c', title: 'What Tomasz knows', status: 'waiting', outcome: '' },
  { id: 'd', title: 'The arc', status: 'open', outcome: '' },
  { id: 'e', title: 'A talking dog', status: 'dropped', outcome: 'Too much' },
]

function row(wrapper: ReturnType<typeof mount>, status: string) {
  return wrapper.get(`[data-status="${status}"]`)
}

describe('AgendaCard', () => {
  it('renders nothing when there is nothing on the agenda', () => {
    const wrapper = mount(AgendaCard, { props: { items: [], error: null } })
    expect(wrapper.find('section').exists()).toBe(false)
  })

  it('draws one line per item, each with its own status mark', () => {
    const wrapper = mount(AgendaCard, { props: { items: ITEMS, error: null } })
    expect(wrapper.findAll('li')).toHaveLength(5)
    for (const status of ['open', 'working', 'waiting', 'settled', 'dropped']) {
      expect(row(wrapper, status).find(`svg.mark--${status}`).exists()).toBe(true)
    }
  })

  it('says "waiting on you" for an item waiting on the user, and for no other', () => {
    const wrapper = mount(AgendaCard, { props: { items: ITEMS, error: null } })
    expect(row(wrapper, 'waiting').text()).toContain('waiting on you')
    expect(row(wrapper, 'open').text()).not.toContain('waiting on you')
    expect(row(wrapper, 'working').text()).not.toContain('waiting on you')
  })

  it('shows the outcome of a settled item', () => {
    const wrapper = mount(AgendaCard, { props: { items: ITEMS, error: null } })
    expect(row(wrapper, 'settled').text()).toContain('A station on a ferry line')
  })

  it('marks a dropped item so it can be struck through and dimmed, without its outcome', () => {
    const wrapper = mount(AgendaCard, { props: { items: ITEMS, error: null } })
    const dropped = row(wrapper, 'dropped')
    expect(dropped.classes()).toContain('item--dropped')
    expect(dropped.text()).toContain('A talking dog')
    expect(dropped.text()).not.toContain('Too much')
  })

  it('tells screen readers each item\'s status in words', () => {
    const wrapper = mount(AgendaCard, { props: { items: ITEMS, error: null } })
    expect(row(wrapper, 'open').find('.sr-only').text()).toBe('Open:')
    expect(row(wrapper, 'settled').find('.sr-only').text()).toBe('Settled:')
  })

  it('counts settled items out of those not dropped', () => {
    const wrapper = mount(AgendaCard, { props: { items: ITEMS, error: null } })
    expect(wrapper.text()).toContain('1 of 4 settled')
  })

  it('shows an agenda error even with no items', () => {
    const wrapper = mount(AgendaCard, { props: { items: [], error: 'The agenda file is damaged.' } })
    expect(wrapper.get('[role="alert"]').text()).toBe('The agenda file is damaged.')
  })
})
