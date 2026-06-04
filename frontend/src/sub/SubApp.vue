<script setup>
import { ref, onMounted, computed } from 'vue'
import QRCode from 'qrcode'

const sub = window.__SUB__ || { label: '', sub_url: '', platform: 'desktop', deeplinks: {} }
const qr = ref('')
const copied = ref(false)

const buttons = computed(() => {
  const d = sub.deeplinks
  if (sub.platform === 'mobile') {
    return [
      { label: 'Karing', href: d.karing },
      { label: 'sing-box', href: d.singbox },
    ]
  }
  return [
    { label: 'Hiddify', href: d.hiddify },
    { label: 'Karing', href: d.karing },
    { label: 'sing-box', href: d.singbox },
  ]
})

async function copyLink() {
  await navigator.clipboard.writeText(sub.sub_url)
  copied.value = true
  setTimeout(() => (copied.value = false), 1500)
}

onMounted(async () => {
  if (sub.sub_url) qr.value = await QRCode.toDataURL(sub.sub_url, { width: 240, margin: 1 })
})
</script>

<template>
  <main class="mx-auto max-w-md px-4 py-10">
    <div class="card text-center">
      <h1 class="text-xl font-semibold">{{ sub.label }}</h1>
      <p class="mt-1 text-sm text-neutral-500">Подписка для подключения</p>

      <img v-if="qr" :src="qr" alt="QR" class="mx-auto mt-6 rounded-lg bg-white p-2" />

      <div class="mt-6 flex flex-col gap-2">
        <a v-for="b in buttons" :key="b.label" class="btn" :href="b.href">
          Импорт в {{ b.label }}
        </a>
        <button class="btn-ghost mt-1" @click="copyLink">
          {{ copied ? 'Скопировано!' : 'Скопировать ссылку' }}
        </button>
      </div>
    </div>

    <div class="card mt-6 text-sm leading-relaxed">
      <h2 class="mb-2 font-semibold">Как подключиться</h2>
      <ol class="list-decimal space-y-1 pl-5">
        <li>Установи клиент:
          <span v-if="sub.platform === 'mobile'">Karing или sing-box</span>
          <span v-else>Hiddify, Karing или sing-box</span>.
        </li>
        <li>Нажми кнопку «Импорт» выше — профиль добавится автоматически.</li>
        <li>Если импорт не сработал — скопируй ссылку и добавь подписку вручную.</li>
        <li>Включи подключение в клиенте.</li>
      </ol>
    </div>
  </main>
</template>
