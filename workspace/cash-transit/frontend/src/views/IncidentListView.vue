<template>
  <div class="page-container">
    <h2 class="page-title">异常情况</h2>
    <el-card>
      <div class="toolbar">
        <el-radio-group v-model="filters.status" @change="load">
          <el-radio-button value="">全部</el-radio-button>
          <el-radio-button v-for="(s, k) in INCIDENT_STATUS" :key="k" :value="k">
            {{ s.label }}
          </el-radio-button>
        </el-radio-group>
        <el-select v-model="filters.category" placeholder="异常类型" clearable
                   style="width:150px" @change="load">
          <el-option v-for="(label, key) in INCIDENT_CATEGORY" :key="key"
                     :value="key" :label="label" />
        </el-select>
      </div>
      <el-table :data="rows" v-loading="loading" stripe>
        <el-table-column prop="incident_no" label="异常编号" width="160" class-name="mono" />
        <el-table-column label="任务" width="160">
          <template #default="{ row }">
            <el-link type="primary" @click="$router.push(`/tasks/${row.task}`)">
              {{ row.task_no }}
            </el-link>
          </template>
        </el-table-column>
        <el-table-column label="类型/程度" width="150">
          <template #default="{ row }">
            <el-tag size="small" type="info">{{ row.category_display }}</el-tag>
            <el-tag size="small" :type="SEVERITY[row.severity].type"
                    style="margin-left:4px">{{ row.severity_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="情况描述" min-width="240" show-overflow-tooltip />
        <el-table-column label="款箱" width="120">
          <template #default="{ row }">
            <span class="mono">{{ row.box_no || '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag size="small" :type="INCIDENT_STATUS[row.status].type">
              {{ row.status_display }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="reported_by_name" label="上报人" width="90" />
        <el-table-column prop="created_at" label="上报时间" width="160" />
        <el-table-column label="处置" min-width="200">
          <template #default="{ row }">
            <span v-if="row.resolution" class="resolved">{{ row.resolution }}
              （{{ row.resolved_by_name }}）</span>
            <el-button v-else link type="primary"
                       @click="$router.push(`/tasks/${row.task}`)">
              去任务处置 →
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination style="margin-top:14px;justify-content:flex-end" background
                     layout="total, prev, pager, next" :total="total"
                     :page-size="20" :current-page="page" @current-change="onPage" />
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import api from '../api/http'
import { INCIDENT_CATEGORY, INCIDENT_STATUS, SEVERITY } from '../constants'

const rows = ref([])
const loading = ref(false)
const total = ref(0)
const page = ref(1)
const filters = reactive({ status: '', category: '' })

async function load() {
  loading.value = true
  try {
    const params = { page: page.value }
    if (filters.status) params.status = filters.status
    if (filters.category) params.category = filters.category
    const data = await api.get('/api/incidents/', { params })
    rows.value = data.results
    total.value = data.count
  } finally { loading.value = false }
}
function onPage(p) { page.value = p; load() }
onMounted(load)
</script>

<style scoped>
.toolbar { display: flex; gap: 10px; margin-bottom: 14px; }
.resolved { color: #67c23a; font-size: 12px; }
.mono { font-family: monospace; }
</style>
