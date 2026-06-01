import { createRouter, createWebHashHistory } from 'vue-router'
import Login from './views/Login.vue'
import Clients from './views/Clients.vue'
import SettingsView from './views/SettingsView.vue'
import { getToken } from './api'

const routes = [
  { path: '/login', component: Login },
  { path: '/', component: Clients },
  { path: '/settings', component: SettingsView },
]

const router = createRouter({ history: createWebHashHistory(), routes })
router.beforeEach((to) => {
  if (to.path !== '/login' && !getToken()) return '/login'
})
export default router
