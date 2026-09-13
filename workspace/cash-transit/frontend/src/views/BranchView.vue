<template>
  <div class="page-container">
    <h2 class="page-title">网点金库（内置样例数据）</h2>
    <el-row :gutter="14">
      <el-col :span="14">
        <el-card>
          <template #header>
            <span class="card-header">
              网点清单
              <el-radio-group v-model="typeFilter" size="small" @change="load">
                <el-radio-button value="">全部</el-radio-button>
                <el-radio-button value="head_vault">中心金库</el-radio-button>
                <el-radio-button value="sub_vault">分金库</el-radio-button>
                <el-radio-button value="branch">营业网点</el-radio-button>
                <el-radio-button value="self_bank">自助银行</el-radio-button>
              </el-radio-group>
            </span>
          </template>
          <el-table :data="rows" v-loading="loading" size="small" stripe>
            <el-table-column prop="code" label="编号" width="90" class-name="mono" />
            <el-table-column prop="name" label="名称" min-width="170" />
            <el-table-column label="类型" width="100">
              <template #default="{ row }">
                <el-tag size="small" :type="row.is_vault ? 'warning' : 'primary'">
                  {{ row.branch_type_display }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="address" label="地址" min-width="220" show-overflow-tooltip />
            <el-table-column prop="contact_person" label="联系人" width="90" />
            <el-table-column prop="contact_phone" label="电话" width="120" />
            <el-table-column label="营业时间" width="110">
              <template #default="{ row }">
                {{ time(row.service_start) }}-{{ time(row.service_end) }}
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
      <el-col :span="10">
        <el-card>
          <template #header><span class="card-header">网点分布示意</span></template>
          <div class="map">
            <div v-for="b in allBranches" :key="b.id" class="map-dot"
                 :class="{ vault: b.is_vault }"
                 :style="dotStyle(b)"
                 @click="typeFilter = b.branch_type; load()">
              <el-icon><component :is="b.is_vault ? 'School' : 'Shop'" /></el-icon>
              <span>{{ b.short_name || b.name }}</span>
              <el-tooltip :content="b.name + '｜' + b.address" placement="top">
                <i></i>
              </el-tooltip>
            </div>
            <div class="map-legend">
              <span><i class="lg vault"></i>金库</span>
              <span><i class="lg branch"></i>网点</span>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import api from '../api/http'

const rows = ref([])
const allBranches = ref([])
const loading = ref(false)
const typeFilter = ref('')

async function load() {
  loading.value = true
  try {
    const params = { page_size: 100 }
    if (typeFilter.value) params.branch_type = typeFilter.value
    rows.value = (await api.get('/api/branches/', { params })).results
  } finally { loading.value = false }
}

const bounds = { minLng: 116.30, maxLng: 116.49, minLat: 39.90, maxLat: 40.0 }
function dotStyle(b) {
  if (!b.lng || !b.lat) return { display: 'none' }
  const x = ((Number(b.lng) - bounds.minLng) / (bounds.maxLng - bounds.minLng)) * 92 + 2
  const y = (1 - (Number(b.lat) - bounds.minLat) / (bounds.maxLat - bounds.minLat)) * 88 + 4
  return { left: `${x}%`, top: `${y}%` }
}
function time(t) {
  return t ? t.slice(0, 5) : '—'
}

onMounted(async () => {
  allBranches.value = (await api.get('/api/branches/',
    { params: { page_size: 100 } })).results
  load()
})
</script>

<style scoped>
.map {
  position: relative; height: 460px;
  background: linear-gradient(135deg, #eaf3fb, #f7fbff);
  border: 1px solid #d9e6f5; border-radius: 8px;
  background-image:
    linear-gradient(#dce8f5 1px, transparent 1px),
    linear-gradient(90deg, #dce8f5 1px, transparent 1px);
  background-size: 40px 40px;
}
.map-dot {
  position: absolute; transform: translate(-50%, -50%);
  display: flex; align-items: center; gap: 3px;
  font-size: 11px; color: #1d4e89; cursor: pointer; white-space: nowrap;
}
.map-dot i { position: absolute; left: 8px; top: -14px; width: 10px; height: 10px; }
.map-dot .el-icon {
  background: #67a2dd; color: #fff; border-radius: 50%;
  padding: 4px; font-size: 13px;
  box-shadow: 0 2px 6px rgba(29, 78, 137, .35);
}
.map-dot.vault .el-icon { background: #e6a23c; }
.map-dot.vault { color: #b8860b; font-weight: 600; }
.map-legend {
  position: absolute; right: 10px; bottom: 8px;
  background: rgba(255,255,255,.9); border-radius: 4px; padding: 6px 10px;
  font-size: 12px; color: #606266; display: flex; gap: 12px;
}
.lg { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 3px; }
.lg.vault { background: #e6a23c; }
.lg.branch { background: #67a2dd; }
</style>
