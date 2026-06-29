import { createRouter, createWebHashHistory } from 'vue-router'

const routes = [
  { path: '/', name: 'dashboard', component: () => import('../views/Dashboard.vue') },
  { path: '/projects', name: 'projects', component: () => import('../views/Projects.vue') },
  { path: '/logs', name: 'logs', component: () => import('../views/Logs.vue') },
  { path: '/docs/:id', name: 'docs', component: () => import('../views/Docs.vue') },
  { path: '/self', name: 'self', component: () => import('../views/Self.vue') },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

export default router
