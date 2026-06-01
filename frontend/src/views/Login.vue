<template>
  <form @submit.prevent="submit">
    <h2>Вход</h2>
    <input v-model="username" placeholder="Логин" />
    <input v-model="password" type="password" placeholder="Пароль" />
    <button>Войти</button>
    <p v-if="error" style="color:red">{{ error }}</p>
  </form>
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
