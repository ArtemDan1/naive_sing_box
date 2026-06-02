<template>
  <div class="flex min-h-screen items-center justify-center px-4">
    <form @submit.prevent="submit" class="card w-full max-w-sm space-y-4">
      <h2 class="text-xl font-semibold tracking-tight">Вход</h2>
      <input v-model="username" placeholder="Логин" class="input" />
      <input v-model="password" type="password" placeholder="Пароль" class="input" />
      <button class="btn w-full">Войти</button>
      <p v-if="error" class="text-sm text-red-600 dark:text-red-400">{{ error }}</p>
    </form>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, setToken } from '../api'

const username = ref(''), password = ref(''), error = ref('')
const router = useRouter()
async function submit() {
  try {
    const { access_token } = await api.login(username.value, password.value)
    setToken(access_token); router.push('/')
  } catch { error.value = 'Неверный логин или пароль' }
}
</script>
