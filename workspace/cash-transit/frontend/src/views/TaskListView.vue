<template>
  <div class="page-container">
    <h2 class="page-title">押运任务</h2>
    <el-card>
      <div class="toolbar">
        <el-radio-group v-model="filters.status" @change="load">
          <el-radio-button value="">全部</el-radio-button>
          <el-radio-button v-for="(s, k) in TASK_STATUS" :key="k" :value="k">
            {{ s.label }}
          </el-radio-button>
        </el-radio-group>
        <div style="flex:1"></div>
        <el-date-picker v-model="filters.date" type="date" value-format="YYYY-MM-DD"
                        placeholder="按日期筛选" clearable style="width:150px"
                        @change="load" />
        <el-input v-model="filters.keyword" placeholder="任务编号" clearable
                  style="width:170px" @keyup.enter="load" @clear="load" />
        <el-button type="primary" @click="$router.push('/tasks/new')">
          <el-icon><Plus /></el-icon>安排任务
        </el-button>
      </div>

      <el-table :data="rows" v-loading="loading" stripe>
        <el-table-column prop="task_no" label="任务编号" width="160" class-name="mono">
          <template #default="{ row }">
            <el-link type="primary" @click="$router.push(`/tasks/${row.id}`)">{{ row.task_no }}</el-link>
          </template>
        </el-table-column>
        <el-table-column label="方向" width="150">
          <template #default="{ row }">
            <el-tag size="small" :type="row.direction === 'outbound' ? 'primary' : 'warning'" effect="plain">
              {{ row.direction_display }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="route_name" label="线路" min-width="170" />
        <el-table-column prop="vehicle_plate" label="车辆" width="100" />
        <el-table-column label="车组" min-width="200">
          <template #default="{ row }">
            <span v-for="(a, i) in row.assignees_brief" :key="i">
              {{ a }}<span v-if="i < row.assignees_brief.length - 1" class="sep">、</span>
            </span>
          </template>
        </el-table-column>
        <el-table-column label="款箱/金额" width="130">
          <template #default="{ row }">
            {{ row.box_count }} 箱<br />
            <span class="amount">¥{{ formatAmount(row.total_amount) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="进度" width="90">
          <template #default="{ row }">{{ row.finished_box_count }}/{{ row.box_count }}</template>
        </el-table-column>
        <el-table-column prop="planned_date" label="计划日期" width="110" />
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="TASK_STATUS[row.status]?.type" size="small">{{ row.status_display }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="80" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="$router.push(`/tasks/${row.id}`)">追踪</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination style="margin-top:14px;justify-content:flex-end"
                     background layout="total, prev, pager, next"
                     :total="total" :page-size="pageSize" :current-page="page"
                     @current-change="onPage" />
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import api from '../api/http'
import { TASK_STATUS } from '../constants'

const rows = ref([])
const loading = ref(false)
const total = ref(0)
const page = ref(1)
const pageSize = 20
const filters = reactive({ status: '', date: '', keyword: '' })

async function load() {
  loading.value = true
  try {
    const params = { page: page.value }
    if (filters.status) params.status = filters.status
    if (filters.date) params.date = filters.date
    if (filters.keyword) params.keyword = filters.keyword
    const data = await api.get('/api/tasks/', { params })
    rows.value = data.results
    total.value = data.count
  } finally {
    loading.value = false
  }
}
function onPage(p) { page.value = p; load() }
function formatAmount(v) {
  return Number(v || 0).toLocaleString('zh-CN', { maximumFractionDigits: 0 })
}
onMounted(load)
</script>

<style scoped>
.toolbar { display: flex; gap: 10px; margin-bottom: 14px; align-items: center; }
.sep { margin: 0 2px; }
.amount { color: #b8860b; font-size: 12px; }
</style>
