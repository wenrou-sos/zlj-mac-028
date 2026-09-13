<template>
  <div class="page-container">
    <h2 class="page-title">调度总览</h2>

    <el-row :gutter="14">
      <el-col :span="6" v-for="c in cards" :key="c.label">
        <el-card class="stat-card" :body-style="{ background: c.bg }">
          <div style="display:flex;justify-content:space-between;align-items:center">
            <div>
              <div style="font-size:13px;opacity:.85">{{ c.label }}</div>
              <div style="font-size:30px;font-weight:700;margin-top:4px">{{ c.value }}</div>
            </div>
            <el-icon :size="42" style="opacity:.55"><component :is="c.icon" /></el-icon>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="14" style="margin-top:14px">
      <el-col :span="14">
        <el-card>
          <template #header><span class="card-header">今日任务动态</span></template>
          <el-table :data="dash.recent || []" size="small" stripe @row-click="go"
                    style="cursor:pointer">
            <el-table-column prop="task_no" label="任务编号" width="150" class-name="mono" />
            <el-table-column prop="route_name" label="线路" min-width="150" />
            <el-table-column prop="vehicle_plate" label="车辆" width="100" />
            <el-table-column label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="TASK_STATUS[row.status]?.type" size="small">
                  {{ row.status_display }}
                </el-tag>
                <el-badge v-if="row.incident_open" :value="row.incident_open"
                          class="inc-badge" type="danger" />
              </template>
            </el-table-column>
            <el-table-column label="款箱" width="70">
              <template #default="{ row }">{{ row.finished_box_count }}/{{ row.box_count }}</template>
            </el-table-column>
            <el-table-column prop="planned_date" label="日期" width="110" />
          </el-table>
        </el-card>
      </el-col>
      <el-col :span="10">
        <el-card style="margin-bottom:14px">
          <template #header><span class="card-header">任务状态分布</span></template>
          <div class="dist">
            <div v-for="(s, key) in TASK_STATUS" :key="key" class="dist-row">
              <el-tag :type="s.type" size="small" style="width:78px;text-align:center">{{ s.label }}</el-tag>
              <el-progress :percentage="pct(dash.by_status?.[key])"
                           :stroke-width="14" :color="progressColor(s.type)" />
              <span class="dist-num">{{ dash.by_status?.[key] || 0 }}</span>
            </div>
          </div>
        </el-card>
        <el-card>
          <template #header>
            <span class="card-header">
              待处置异常
              <el-button link type="primary" @click="$router.push('/incidents')">全部 →</el-button>
            </span>
          </template>
          <el-empty v-if="!dash.open_incidents" description="暂无未处置异常" :image-size="60" />
          <div v-else style="text-align:center;padding:8px 0">
            <el-statistic :value="dash.open_incidents" title="未处置异常事件" />
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api/http'
import { TASK_STATUS } from '../constants'

const router = useRouter()
const dash = reactive({ by_status: {}, recent: [], open_incidents: 0,
  today_total: 0, today_in_transit: 0, vehicles_on_duty: 0 })

const totalTasks = computed(() =>
  Object.values(dash.by_status || {}).reduce((a, b) => a + (b || 0), 0))

const cards = computed(() => [
  { label: '今日任务', value: dash.today_total, icon: 'Van', bg: 'linear-gradient(135deg,#1d4e89,#2a6db5)' },
  { label: '押运/挂起中', value: dash.today_in_transit, icon: 'Position', bg: 'linear-gradient(135deg,#b8860b,#e6a23c)' },
  { label: '在外车辆', value: dash.vehicles_on_duty, icon: 'AlarmClock', bg: 'linear-gradient(135deg,#2e7d6b,#67c23a)' },
  { label: '待处置异常', value: dash.open_incidents, icon: 'Warning', bg: 'linear-gradient(135deg,#a33,#f56c6c)' },
])

function pct(n) {
  if (!totalTasks.value) return 0
  return Math.round(((n || 0) / totalTasks.value) * 100)
}
function progressColor(type) {
  return { info: '#909399', primary: '#1d4e89', warning: '#e6a23c',
    danger: '#f56c6c', success: '#67c23a' }[type] || '#1d4e89'
}
function go(row) { router.push(`/tasks/${row.id}`) }

onMounted(async () => {
  const data = await api.get('/api/tasks/dashboard/')
  Object.assign(dash, data)
})
</script>

<style scoped>
.inc-badge { margin-left: 6px; }
.dist-row { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; }
.dist-row .el-progress { flex: 1; }
.dist-num { width: 28px; text-align: right; font-weight: 600; color: #606266; }
</style>
