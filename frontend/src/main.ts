import './assets/main.css'

import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import ui from '@nuxt/ui/vue-plugin'
import App from './App.vue'
import CharacterLibraryView from './views/CharacterLibraryView.vue'
import CharacterCreateView from './views/CharacterCreateView.vue'
import CharacterDetailView from './views/CharacterDetailView.vue'
import HomeView from './views/HomeView.vue'
import HubView from './views/HubView.vue'
import PlaySessionView from './views/PlaySessionView.vue'
import RulesetCreateView from './views/RulesetCreateView.vue'
import RulesetLibraryView from './views/RulesetLibraryView.vue'
import ScenarioCreateView from './views/ScenarioCreateView.vue'
import ScenarioDetailView from './views/ScenarioDetailView.vue'
import ScenarioLibraryView from './views/ScenarioLibraryView.vue'
import SessionDetailView from './views/SessionDetailView.vue'
import SessionsView from './views/SessionsView.vue'
import WorldLoreCreateView from './views/WorldLoreCreateView.vue'
import WorldLoreLibraryView from './views/WorldLoreLibraryView.vue'
import CharacterSelectionView from './views/CharacterSelectionView.vue'
import CharacterPageView from './views/CharacterPageView.vue'
import ChatView from './views/ChatView.vue'
import CharacterCreationView from './views/CharacterCreationView.vue'
import StylePreviewView from './views/StylePreviewView.vue'
import { clerkPlugin } from '@clerk/vue'

const PUBLISHABLE_KEY = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY
const AUTH_BYPASS = ['true', '1', 'yes'].includes(
  String(import.meta.env.VITE_AUTH_BYPASS || '').toLowerCase()
)

const routes = [
  {
    path: '/',
    name: 'home',
    component: HomeView,
    meta: { layout: 'modern' },
  },
  {
    path: '/hub',
    name: 'hub',
    component: HubView,
    meta: { layout: 'modern' },
  },
  {
    path: '/sessions',
    name: 'sessions',
    component: SessionsView,
    meta: { layout: 'modern' },
  },
  {
    path: '/sessions/:sessionId',
    name: 'session-detail',
    component: SessionDetailView,
    props: true,
    meta: { layout: 'modern' },
  },
  {
    path: '/play/:sessionId',
    name: 'play-session',
    component: PlaySessionView,
    props: true,
    meta: { layout: 'modern' },
  },
  {
    path: '/library/characters',
    name: 'character-library',
    component: CharacterLibraryView,
    meta: { layout: 'modern' },
  },
  {
    path: '/library/personas',
    name: 'persona-library',
    component: CharacterLibraryView,
    props: { initialFilter: 'personas' },
    meta: { layout: 'modern' },
  },
  {
    path: '/characters/new',
    name: 'character-create',
    component: CharacterCreateView,
    meta: { layout: 'modern' },
  },
  {
    path: '/characters/:characterId',
    name: 'character-detail',
    component: CharacterDetailView,
    props: true,
    meta: { layout: 'modern' },
  },
  {
    path: '/characters/:characterId/edit',
    name: 'character-edit',
    component: CharacterCreateView,
    props: true,
    meta: { layout: 'modern' },
  },
  {
    path: '/personas/new',
    name: 'persona-create',
    component: CharacterCreateView,
    props: { personaMode: true },
    meta: { layout: 'modern' },
  },
  {
    path: '/library/rulesets',
    name: 'ruleset-library',
    component: RulesetLibraryView,
    meta: { layout: 'modern' },
  },
  {
    path: '/rulesets/new',
    name: 'ruleset-create',
    component: RulesetCreateView,
    meta: { layout: 'modern' },
  },
  {
    path: '/scenarios/new',
    name: 'scenario-create-modern',
    component: ScenarioCreateView,
    meta: { layout: 'modern' },
  },
  {
    path: '/library/scenarios',
    name: 'scenario-library',
    component: ScenarioLibraryView,
    meta: { layout: 'modern' },
  },
  {
    path: '/scenarios/:scenarioId',
    name: 'scenario-detail',
    component: ScenarioDetailView,
    props: true,
    meta: { layout: 'modern' },
  },
  {
    path: '/world-lore/new',
    name: 'world-lore-create',
    component: WorldLoreCreateView,
    meta: { layout: 'modern' },
  },
  {
    path: '/library/world-lore',
    name: 'world-lore-library',
    component: WorldLoreLibraryView,
    meta: { layout: 'modern' },
  },
  {
    path: '/legacy/characters',
    name: 'start',
    component: CharacterSelectionView,
    meta: { layout: 'legacy' },
  },
  {
    path: '/character/:characterId',
    name: 'character',
    component: CharacterPageView,
    props: true,
    meta: { layout: 'legacy' },
  },
  {
    path: '/chat/:characterId/:sessionId',
    name: 'chat',
    component: ChatView,
    props: true,
    meta: { layout: 'legacy' },
  },
  {
    path: '/create',
    name: 'create',
    component: CharacterCreationView,
    meta: { layout: 'legacy' },
  },
  {
    path: '/character/:characterId/edit',
    name: 'edit-character',
    component: CharacterCreationView,
    props: true,
    meta: { layout: 'legacy' },
  },
  {
    path: '/style-lab',
    name: 'style-lab',
    component: StylePreviewView,
    meta: { layout: 'bare' },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

const app = createApp(App)
app.use(router)
app.use(ui)

if (!AUTH_BYPASS) {
  app.use(clerkPlugin, { publishableKey: PUBLISHABLE_KEY, appearance: { cssLayerName: 'clerk' } })
}

app.mount('#app')
