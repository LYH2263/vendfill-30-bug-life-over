<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
const sales = ref<any[]>([])
const stats = ref<any[]>([])
onMounted(async () => {
  const data = await api('/sales')
  sales.value = data.sales
  stats.value = data.lane_stats
})
function avgText(v: number) { return (v ?? 0).toFixed(2) }
</script>
<template>
  <h1>销量</h1>
  <p class="sub">近七日销量合计 ÷ 7 = 日均 · 可补上限 = min(缺口, ⌊日均 × 临期可售天数⌋)，与补货单同口径</p>
  <div class="card">
    <table>
      <thead>
        <tr><th>货道</th><th>商品</th><th>近七日销量</th><th>日均</th><th>临期可售天数</th><th>缺口</th><th>可补上限</th></tr>
      </thead>
      <tbody>
        <tr v-for="s in stats" :key="s.lane_id">
          <td>{{ s.slot_no }}</td>
          <td>{{ s.sku_name }}</td>
          <td>{{ s.sales_7d }}</td>
          <td>{{ avgText(s.avg_daily) }}</td>
          <td>{{ s.sellable_days == null ? '不封顶' : s.sellable_days }}</td>
          <td>{{ s.gap }}</td>
          <td><strong>{{ s.fill_cap }}</strong></td>
        </tr>
      </tbody>
    </table>
  </div>
  <h2 style="margin-top:1.5rem">近期出货记录</h2>
  <div class="card">
    <table>
      <thead><tr><th>货道</th><th>商品</th><th>数量</th><th>时间</th></tr></thead>
      <tbody>
        <tr v-for="r in sales" :key="r.id"><td>{{ r.slot_no }}</td><td>{{ r.sku_name }}</td><td>{{ r.qty }}</td><td>{{ r.sold_at }}</td></tr>
      </tbody>
    </table>
  </div>
</template>
