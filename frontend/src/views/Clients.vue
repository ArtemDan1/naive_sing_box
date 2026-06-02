<template>
  <h2>Клиенты</h2>
  <form @submit.prevent="add">
    <input v-model="label" placeholder="Имя клиента" />
    <button>Добавить</button>
  </form>
  <table border="1" cellpadding="6">
    <tr><th>Имя</th><th>Логин</th><th>Подписка</th><th>Вкл</th><th></th></tr>
    <template v-for="c in clients" :key="c.id">
      <tr>
        <td>{{ c.label }}</td>
        <td>{{ c.username }}</td>
        <td>
          <a :href="subUrl(c)" target="_blank">ссылка</a>
          <button type="button" @click="copy(c)">Копировать</button>
          <a :href="singboxLink(c)">sing-box</a>
          <a :href="hiddifyLink(c)">Hiddify</a>
          <button type="button" @click="toggleQr(c)">QR</button>
        </td>
        <td><input type="checkbox" :checked="c.enabled" @change="toggle(c)" /></td>
        <td><button @click="remove(c)">Удалить</button></td>
      </tr>
      <tr v-if="qrFor === c.id">
        <td colspan="5"><img :src="qrData" alt="QR" /></td>
      </tr>
    </template>
  </table>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import QRCode from 'qrcode'
import { api } from '../api'

const clients = ref([]), label = ref('')
const qrFor = ref(null), qrData = ref('')

async function load() { clients.value = await api.clients() }
async function add() { if (label.value) { await api.createClient(label.value); label.value = ''; await load() } }
async function toggle(c) { await api.updateClient(c.id, { enabled: !c.enabled }); await load() }
async function remove(c) { await api.deleteClient(c.id); await load() }

function subUrl(c) { return `${location.origin}/sub/${c.sub_uuid}` }
function singboxLink(c) {
  return `sing-box://import-remote-profile?url=${encodeURIComponent(subUrl(c))}#${encodeURIComponent(c.label)}`
}
function hiddifyLink(c) {
  return `hiddify://import/${subUrl(c)}#${encodeURIComponent(c.label)}`
}
async function copy(c) { await navigator.clipboard.writeText(subUrl(c)) }
async function toggleQr(c) {
  if (qrFor.value === c.id) { qrFor.value = null; return }
  qrData.value = await QRCode.toDataURL(singboxLink(c))
  qrFor.value = c.id
}
onMounted(load)
</script>
