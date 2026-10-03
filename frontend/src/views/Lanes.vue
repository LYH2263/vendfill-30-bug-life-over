<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
const rows = ref<any[]>([])
const refill = ref<any>(null)
const drafts = ref<Record<number, string>>({})
const saving = ref<number | null>(null)
const error = ref('')

onMounted(async () => {
  rows.value = await api('/lanes')
  syncDrafts()
  try { refill.value = await api('/refills/run?location_id=1', { method: 'POST' }) } catch { /* */ }
})

function syncDrafts() {
  for (const r of rows.value) drafts.value[r.id] = r.sellable_days == null ? '' : String(r.sellable_days)
}

function avgText(v: number | null | undefined) { return (v ?? 0).toFixed(2) }

async function saveDays(r: any) {
  error.value = ''
  const raw = drafts.value[r.id]?.trim() ?? ''
  const days = raw === '' ? null : Number(raw)
  if (days !== null && (!Number.isInteger(days) || days <= 0)) {
    drafts.value[r.id] = r.sellable_days == null ? '' : String(r.sellable_days) // 拒绝：保持改前
    error.value = `${r.slot_no} 临期可售天数必须为大于 0 的整数（留空为不封顶）`
    return
  }
  saving.value = r.id
  try {
    const updated = await api(`/lanes/${r.id}`, {
      method: 'PATCH', body: JSON.stringify({ sellable_days: days }),
    })
    Object.assign(r, updated)
    drafts.value[r.id] = updated.sellable_days == null ? '' : String(updated.sellable_days)
    refill.value = await api('/refills/run?location_id=1', { method: 'POST' })
  } catch (e: any) {
    drafts.value[r.id] = r.sellable_days == null ? '' : String(r.sellable_days) // 后端拒绝：保持改前
    error.value = e?.message ? String(e.message).replace(/[{}"]/g, '') : '保存失败'
  } finally {
    saving.value = null
  }
}
</script>
<template>
  <h1>货道格子</h1>
  <p class="sub">机面货道网格 · 格内库存条 · 右侧补货小票 · 临期可售天数留空 = 不封顶</p>
  <p v-if="error" class="vf-err">{{ error }}</p>
  <div class="vf-machine-layout">
    <div class="vf-slot-grid">
      <div v-for="r in rows" :key="r.id" class="vf-slot">
        <div class="vf-slot-no">{{ r.slot_no }}</div>
        <div class="vf-slot-sku">{{ r.sku_name }}</div>
        <div class="vf-slot-bar">
          <div
            class="vf-slot-fill"
            :class="{ 'vf-need': r.gap > 0 }"
            :style="{ width: Math.min(r.fill_pct, 100) + '%' }"
          />
        </div>
        <div class="vf-slot-meta">{{ r.stock }}/{{ r.capacity }} · 缺 {{ r.gap }}</div>
        <div class="vf-slot-meta">日均 {{ avgText(r.avg_daily) }} · 可补上限 {{ r.fill_cap }}</div>
        <label class="vf-days">
          临期可售天数
          <input
            v-model="drafts[r.id]"
            type="number" min="1" step="1" placeholder="不封顶"
            @keyup.enter="saveDays(r)"
          />
          <button class="btn vf-days-save" :disabled="saving === r.id" @click="saveDays(r)">保存</button>
        </label>
      </div>
    </div>
    <aside class="vf-receipt" v-if="refill">
      <h2>*** 补货建议单 ***</h2>
      <div class="vf-receipt-line" v-for="l in refill.lines" :key="l.lane_id">
        <span>{{ l.slot_no }} {{ l.sku_name }}</span>
        <span>x{{ l.fill_qty }}<small v-if="l.reason">（{{ l.reason }}）</small></span>
      </div>
      <p class="muted" style="margin:0.75rem 0 0;font-size:0.72rem;color:#6a5e48;text-align:center">
        — 机面打印预览 —
      </p>
    </aside>
  </div>
</template>
