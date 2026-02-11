import './assets/main.css'

import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import ui from '@nuxt/ui/vue-plugin'
import App from './App.vue'
import CharacterSelectionView from './views/CharacterSelectionView.vue'
import CharacterPageView from './views/CharacterPageView.vue'
import ChatView from './views/ChatView.vue'
import CharacterCreationView from './views/CharacterCreationView.vue'
import ScenarioCreationView from './views/ScenarioCreationView.vue'
import CreationHubView from './views/CreationHubView.vue'
import ScenarioLibraryView from './views/ScenarioLibraryView.vue'
import WorldLoreLibraryView from './views/WorldLoreLibraryView.vue'
import WorldLoreCreationView from './views/WorldLoreCreationView.vue'
import { clerkPlugin } from '@clerk/vue'

const PUBLISHABLE_KEY = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY
const DEV_AUTH_BYPASS = import.meta.env.VITE_DEV_AUTH_BYPASS === 'true'

const routes = [
  {
    path: '/',
    name: 'start',
    component: CharacterSelectionView,
  },
  {
    path: '/character/:characterId',
    name: 'character',
    component: CharacterPageView,
    props: true,
  },
  {
    path: '/chat/:characterId/:sessionId',
    name: 'chat',
    component: ChatView,
    props: true,
  },
  {
    path: '/create',
    name: 'create',
    component: CreationHubView,
  },
  {
    path: '/create/character',
    name: 'create-character',
    component: CharacterCreationView,
  },
  {
    path: '/create/scenario',
    name: 'create-scenario-global',
    component: ScenarioCreationView,
  },
  {
    path: '/library/scenarios',
    name: 'library-scenarios',
    component: ScenarioLibraryView,
  },
  {
    path: '/library/world-lore',
    name: 'library-world-lore',
    component: WorldLoreLibraryView,
  },
  {
    path: '/create/world-lore',
    name: 'create-world-lore',
    component: WorldLoreCreationView,
  },
  {
    path: '/character/:characterId/edit',
    name: 'edit-character',
    component: CharacterCreationView,
    props: true,
  },
  {
    path: '/character/:characterId/create-scenario',
    name: 'create-scenario',
    component: ScenarioCreationView,
    props: true,
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

const app = createApp(App)
app.use(router)
app.use(ui)
if (!DEV_AUTH_BYPASS && PUBLISHABLE_KEY) {
  app.use(clerkPlugin, { publishableKey: PUBLISHABLE_KEY, appearance: { cssLayerName: 'clerk' } })
}
app.mount('#app')
