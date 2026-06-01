<template>
  <h2>Клиенты</h2>
  <form @submit.prevent="add">
    <input v-model="label" placeholder="Имя клиента" />
    <button>Добавить</button>
  </form>
  <table border="1" cellpadding="6">
    <tr><th>Имя</th><th>Логин</th><th>Подписка</th><th>Вкл</th><th></th></tr>
    <tr v-for="c in clients" :key="c.id">
      <td>{{ c.label }}</td>
      <td>{{ c.username }}</td>
      <td><a :href="subUrl(c)" target="_blank">ссылка</a></td>
      <td><input type="checkbox" :checked="c.enabled" @change="toggle(c)" /></td>
      <td><button @click="remove(c)">Удалить</button></td>
    </tr>
  </table>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api'

const clients = ref([]), label = ref('')
async function load() { clients.value = await api.clients() }
async function add() { if (label.value) { await api.createClient(label.value); label.value = ''; await load() } }
async function toggle(c) { await api.updateClient(c.id, { enabled: !c.enabled }); await load() }
async function remove(c) { await api.deleteClient(c.id); await load() }
function subUrl(c) { return `${location.origin}/sub/${c.sub_uuid}` }
onMounted(load)
</script>
