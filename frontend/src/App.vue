<template>
  <div class="min-h-screen">
    <nav
      v-if="$route.path !== '/login'"
      class="border-b border-neutral-200 bg-white/80 backdrop-blur dark:border-neutral-800 dark:bg-neutral-900/80"
    >
      <div class="mx-auto flex max-w-4xl items-center gap-1 px-4 py-3">
        <span class="mr-3 font-semibold tracking-tight">Naive&nbsp;Admin</span>
        <router-link to="/" class="btn-ghost" active-class="bg-neutral-200 dark:bg-neutral-800">Клиенты</router-link>
        <router-link to="/settings" class="btn-ghost" active-class="bg-neutral-200 dark:bg-neutral-800">Настройки</router-link>
        <a href="#" class="btn-ghost ml-auto" @click.prevent="doLogout">Выйти</a>
      </div>
    </nav>

    <main class="mx-auto max-w-4xl px-4 py-8">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'
import { logout } from './api'

const router = useRouter()
function doLogout() { logout(); router.push('/login') }
</script>
