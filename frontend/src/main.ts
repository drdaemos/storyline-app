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
import { clerkPlugin } from '@clerk/vue'

const PUBLISHABLE_KEY = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY

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
    component: CharacterCreationView,
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
app.use(clerkPlugin, { publishableKey: PUBLISHABLE_KEY, appearance: { cssLayerName: 'clerk' } })
app.mount('#app')
