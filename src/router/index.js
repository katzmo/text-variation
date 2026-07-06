import { createRouter, createWebHistory } from 'vue-router'
import SequenceView from '@/views/SequenceView.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'home',
      component: SequenceView,
    },
  ],
})

export default router
