import { createRouter, createWebHistory } from 'vue-router'
import RoomView from '@/views/RoomView.vue'
import ShelfView from '@/views/ShelfView.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'shelf', component: ShelfView },
    { path: '/stories/:name', name: 'room', component: RoomView, props: true },
    { path: '/:rest(.*)*', redirect: '/' },
  ],
})
