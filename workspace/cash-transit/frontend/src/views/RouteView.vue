<template>
  <div class="page-container">
    <h2 class="page-title">押运线路</h2>
    <el-row :gutter="14" v-loading="loading">
      <el-col :span="9" v-for="r in routes" :key="r.id">
        <el-card class="route-card">
          <template #header>
            <span class="card-header">
              <span>
                <el-tag type="primary">{{ r.code }}</el-tag>
                <b style="margin-left:8px">{{ r.name }}</b>
              </span>
              <el-tag size="small" type="info">{{ r.depot_name }}始发</el-tag>
            </span>
          </template>
          <el-timeline>
            <el-timeline-item type="primary" hollow :timestamp="`${r.depot_name} 出发`">
              <b>{{ r.depot_name }}</b>
            </el-timeline-item>
            <el-timeline-item v-for="s in r.stops" :key="s.id"
                              :timestamp="s.planned_arrival ? `${s.planned_arrival.slice(0,5)} 到 / 停留${s.dwell_minutes}分` : ''"
                              placement="top" type="primary">
              <b>{{ s.sequence }}. {{ s.branch_short || s.branch_name }}</b>
            </el-timeline-item>
            <el-timeline-item type="success"
                              :timestamp="`全程 ${r.distance_km} 公里 / 约 ${r.est_minutes} 分钟`">
              返回 {{ r.depot_name }}
            </el-timeline-item>
          </el-timeline>
          <el-button v-if="canDispatch" type="primary" plain size="small"
                     style="width:100%" @click="arrangeTask(r)">
            <el-icon><Plus /></el-icon> 按此线路安排任务
          </el-button>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { onMounted, ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api/http'
import { useAuthStore } from '../store/auth'
import { isDispatcher } from '../auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const canDispatch = computed(() => isDispatcher(auth.user))
const routes = ref([])
const loading = ref(false)

function arrangeTask(r) {
  router.push({ path: '/tasks/new', query: { route: r.id } })
}

onMounted(async () => {
  loading.value = true
  try {
    // 视图集非分页读取全部（page_size 调大）
    routes.value = (await api.get('/api/routes/',
      { params: { page_size: 100 } })).results
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.route-card { margin-bottom: 14px; }
</style>
