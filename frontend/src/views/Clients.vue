<template>
  <div class="mb-6 flex flex-wrap items-center justify-between gap-4">
    <h2 class="text-2xl font-semibold tracking-tight">Клиенты</h2>
    <form @submit.prevent="add" class="flex gap-2">
      <input v-model="label" placeholder="Имя клиента" class="input w-56" />
      <button class="btn whitespace-nowrap">Добавить</button>
    </form>
  </div>

  <div class="card overflow-hidden p-0">
    <table class="w-full text-sm">
      <thead>
        <tr class="border-b border-neutral-200 text-left text-xs uppercase tracking-wide text-neutral-500 dark:border-neutral-800 dark:text-neutral-400">
          <th class="px-4 py-3 font-medium">Имя</th>
          <th class="px-4 py-3 font-medium">Логин</th>
          <th class="px-4 py-3 font-medium">Подписка</th>
          <th class="px-4 py-3 font-medium">Вкл</th>
          <th class="px-4 py-3"></th>
        </tr>
      </thead>
      <tbody>
        <template v-for="c in clients" :key="c.id">
          <tr class="border-b border-neutral-100 last:border-0 dark:border-neutral-800/60">
            <td class="px-4 py-3 font-medium">{{ c.label }}</td>
            <td class="px-4 py-3 font-mono text-xs text-neutral-500 dark:text-neutral-400">{{ c.username }}</td>
            <td class="px-4 py-3">
              <div class="flex flex-wrap items-center gap-1">
                <a :href="subUrl(c)" target="_blank" class="btn-ghost">Ссылка</a>
                <button type="button" class="btn-ghost" @click="copy(c)">
                  {{ copied === c.id ? 'Скопировано' : 'Копировать' }}
                </button>
                <a :href="singboxLink(c)" class="btn-ghost">sing-box</a>
                <a :href="hiddifyLink(c)" class="btn-ghost">Hiddify</a>
                <button type="button" class="btn-ghost" @click="toggleQr(c)">QR</button>
              </div>
            </td>
            <td class="px-4 py-3">
              <input
                type="checkbox"
                class="h-4 w-4 accent-indigo-600"
                :checked="c.enabled"
                @change="toggle(c)"
              />
            </td>
            <td class="px-4 py-3 text-right">
              <button type="button" class="btn-ghost btn-danger" @click="remove(c)">Удалить</button>
            </td>
          </tr>
          <tr v-if="qrFor === c.id">
            <td colspan="5" class="bg-neutral-50 px-4 py-4 dark:bg-neutral-950/40">
              <img :src="qrData" alt="QR" class="rounded-lg bg-white p-2 shadow-sm" width="200" height="200" />
            </td>
          </tr>
        </template>
        <tr v-if="!clients.length">
          <td colspan="5" class="px-4 py-8 text-center text-neutral-500 dark:text-neutral-400">
            Пока нет клиентов — добавьте первого.
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import QRCode from 'qrcode'
import { api } from '../api'

const clients = ref([]), label = ref('')
const qrFor = ref(null), qrData = ref('')
const copied = ref(null)

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
async function copy(c) {
  await navigator.clipboard.writeText(subUrl(c))
  copied.value = c.id
  setTimeout(() => { if (copied.value === c.id) copied.value = null }, 1500)
}
async function toggleQr(c) {
  if (qrFor.value === c.id) { qrFor.value = null; return }
  qrData.value = await QRCode.toDataURL(singboxLink(c))
  qrFor.value = c.id
}
onMounted(load)
</script>
