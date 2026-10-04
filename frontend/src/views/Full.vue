<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
const lanes = ref<any[]>([])
onMounted(async () => {
  // 满仓页只列缺口为 0 的满仓行；被临期上限压到补 0 的行仍是待补，不在此页。
  const body = await api('/refills/full?location_id=1')
  lanes.value = body.lanes || []
})
</script>
<template>
  <h1>满仓</h1>
  <p class="sub">缺口为 0 的货道（无需补货）</p>
  <div class="card">
    <table>
      <thead><tr><th>货道</th><th>商品</th><th>库存</th><th>在途</th><th>容量</th></tr></thead>
      <tbody>
        <tr v-for="l in lanes" :key="l.lane_id">
          <td>{{ l.slot_no }}</td><td>{{ l.sku_name }}</td><td>{{ l.stock }}</td><td>{{ l.in_transit }}</td><td>{{ l.capacity }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
