import { createRouter, createWebHistory } from 'vue-router'
import AppLayout from '@/layouts/AppLayout.vue'
import { useAuthStore } from '@/stores/auth'

const routes = [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/LoginView.vue'),
    meta: { public: true },
  },
  {
    path: '/',
    component: AppLayout,
    redirect: '/experts',
    children: [
      { path: 'experts', name: 'experts', component: () => import('@/views/ExpertsView.vue') },
      { path: 'users', name: 'users', meta: { adminOnly: true }, component: () => import('@/views/UsersView.vue') },
      { path: 'kb', name: 'kb', meta: { adminOnly: true }, component: () => import('@/views/KbListView.vue') },
      { path: 'kb/:id', name: 'kbDetail', meta: { adminOnly: true }, component: () => import('@/views/KbDetailView.vue') },
      { path: 'chat', name: 'chat', meta: { adminOnly: true }, component: () => import('@/views/ChatListView.vue') },
      { path: 'chat/:id', name: 'chatDetail', meta: { consultantOk: true }, component: () => import('@/views/ChatDetailView.vue') },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

const ADMIN_ROUTES = new Set(['kb', 'kbDetail', 'chat', 'users'])

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  auth.restore()
  if (to.meta.public) {
    if (auth.isLoggedIn && to.name === 'login') {
      return { path: '/experts' }
    }
    return true
  }
  if (!auth.isLoggedIn) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (auth.isLoggedIn && !auth.role) {
    await auth.fetchMe()
  }
  if (!auth.isAdmin) {
    if (to.meta.adminOnly || ADMIN_ROUTES.has(to.name)) {
      return { path: '/experts' }
    }
    if (to.name === 'chatDetail' && to.query.tab === 'settings') {
      return { name: 'chatDetail', params: to.params, query: { tab: 'dialog' } }
    }
    if (to.path === '/' || to.path === '') {
      return { path: '/experts' }
    }
  }
  return true
})

export default router
