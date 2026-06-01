<template>
  <h2>Настройки</h2>
  <form @submit.prevent="save">
    <label>Домен: <input v-model="domain" placeholder="vpn.example.com" /></label>
    <button>Сохранить</button>
    <p v-if="saved" style="color:green">Сохранено (Caddy перезапущен)</p>
  </form>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api'

const domain = ref(''), saved = ref(false)
onMounted(async () => { domain.value = (await api.getSettings()).domain })
async function save() { await api.putSettings(domain.value); saved.value = true }
</script>
