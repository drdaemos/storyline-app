import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import StartView from './views/StartView.vue'
import ChatView from './views/ChatView.vue'
import CharacterCreationView from './views/CharacterCreationView.vue'

const routes = [
  {
    path: '/',
    name: 'start',
    component: StartView
  },
  {
    path: '/chat/:characterName/:sessionId',
    name: 'chat',
    component: ChatView,
    props: true
  },
  {
    path: '/create',
    name: 'create',
    component: CharacterCreationView
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

const app = createApp(App)
app.use(router)
app.mount('#app')