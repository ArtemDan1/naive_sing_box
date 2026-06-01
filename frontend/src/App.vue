<template>
  <nav v-if="$route.path !== '/login'">
    <router-link to="/">Клиенты</router-link> |
    <router-link to="/settings">Настройки</router-link> |
    <a href="#" @click.prevent="doLogout">Выйти</a>
  </nav>
  <router-view />
</template>

<script setup>
import { useRouter } from 'vue-router'
import { logout } from './api'

const router = useRouter()
function doLogout() { logout(); router.push('/login') }
</script>
