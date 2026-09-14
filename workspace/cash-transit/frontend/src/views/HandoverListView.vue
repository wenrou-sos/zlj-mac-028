<template>
  <div class="page-container">
    <h2 class="page-title">交接记录</h2>
    <el-alert type="info" :closable="false" show-icon style="margin-bottom:12px"
              :title="scopeHint" />
    <el-card>
      <div class="toolbar">
        <el-select v-model="filters.phase" placeholder="交接环节" clearable
                   style="width:150px" @change="load">
          <el-option v-for="(label, key) in PHASE" :key="key" :value="key" :label="label" />
        </el-select>
        <el-select v-model="filters.result" placeholder="核对结果" clearable
                   style="width:150px" @change="load">
          <el-option label="核对一致" value="confirmed" />
          <el-option label="封签异常" value="seal_mismatch" />
          <el-option label="验证码不符" value="code_mismatch" />
          <el-option label="款箱短少" value="box_missing" />
        </el-select>
      </div>
      <el-table :data="rows" v-loading="loading" stripe>
        <el-table-column prop="created_at" label="交接时间" width="170" />
        <el-table-column label="款箱" width="130">
          <template #default="{ row }"><span class="mono">{{ row.box_no }}</span></template>
        </el-table-column>
        <el-table-column label="环节" width="110">
          <template #default="{ row }">
            <el-tag size="small">{{ row.phase_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="核对结果" width="120">
          <template #default="{ row }">
            <el-tag size="small" :type="row.result === 'confirmed' ? 'success' : 'danger'">
              {{ row.result_display }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="封签号 交出→接收" width="220">
          <template #default="{ row }">
            <span class="mono">{{ row.seal_no_out || '—' }}</span>
            <el-icon style="margin:0 4px"><Right /></el-icon>
            <span class="mono">{{ row.seal_no_in || '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="封签/验证码" width="120">
          <template #default="{ row }">
            <el-tag size="small" :type="row.seal_intact ? 'success' : 'danger'">
              {{ row.seal_intact ? '封签完好' : '封签破损' }}
            </el-tag>
            <el-tag v-if="row.code_verified !== null" size="small"
                    :type="row.code_verified ? 'success' : 'danger'" style="margin-top:2px">
              验证码{{ row.code_verified ? '相符' : '不符' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="交出人 → 接收人" min-width="170">
          <template #default="{ row }">
            {{ row.from_person_name || '—' }} → {{ row.to_person_name || '—' }}
          </template>
        </el-table-column>
        <el-table-column prop="operator_name" label="登记人" width="100" />
        <el-table-column prop="remark" label="备注" min-width="140" show-overflow-tooltip />
      </el-table>
      <el-pagination style="margin-top:14px;justify-content:flex-end" background
                     layout="total, prev, pager, next" :total="total"
                     :page-size="20" :current-page="page" @current-change="onPage" />
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref, computed } from 'vue'
import api from '../api/http'
import { PHASE } from '../constants'
import { useAuthStore } from '../store/auth'

const auth = useAuthStore()
const scopeHint = computed(() => ({
  dispatcher: '全部任务的款箱交接记录',
  admin: '全部任务的款箱交接记录',
  vault_keeper: '仅本金库出入库交接记录',
  guard: '仅本人随车任务的交接记录',
  driver: '仅本人随车任务的交接记录（只读）',
  branch_clerk: '仅本网点停靠交接记录',
}[auth.user?.role] || '交接记录'))

const rows = ref([])
const loading = ref(false)
const total = ref(0)
const page = ref(1)
const filters = reactive({ phase: '', result: '' })

async function load() {
  loading.value = true
  try {
    const params = { page: page.value, ordering: '-created_at' }
    if (filters.phase) params.phase = filters.phase
    if (filters.result) params.result = filters.result
    const data = await api.get('/api/handovers/', { params })
    rows.value = data.results
    total.value = data.count
  } finally { loading.value = false }
}
function onPage(p) { page.value = p; load() }
onMounted(load)
</script>

<style scoped>
.toolbar { display: flex; gap: 10px; margin-bottom: 14px; }
.mono { font-family: monospace; }
</style>
