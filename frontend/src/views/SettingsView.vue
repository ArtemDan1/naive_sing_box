<template>
  <h2 class="mb-6 text-2xl font-semibold tracking-tight">Настройки</h2>
  <form @submit.prevent="save" class="card max-w-md space-y-4">
    <label class="block space-y-1.5">
      <span class="text-sm font-medium text-neutral-600 dark:text-neutral-400">Домен</span>
      <input v-model="domain" placeholder="vpn.example.com" class="input" />
    </label>
    <div class="flex items-center gap-3">
      <button class="btn">Сохранить</button>
      <p v-if="saved" class="text-sm text-green-600 dark:text-green-400">Сохранено (Caddy перезапущен)</p>
    </div>
  </form>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api'

const domain = ref(''), saved = ref(false)
onMounted(async () => { domain.value = (await api.getSettings()).domain })
async function save() { await api.putSettings(domain.value); saved.value = true }
</script>
