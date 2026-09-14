<template>
  <div class="page-container" v-if="task">
    <!-- 头部 -->
    <el-card style="margin-bottom:14px">
      <div class="head">
        <div>
          <div class="title-line">
            <el-tag :type="TASK_STATUS[task.status].type" effect="dark" size="large">
              {{ task.status_display }}
            </el-tag>
            <span class="task-no mono">{{ task.task_no }}</span>
            <span class="task-name">{{ task.name }}</span>
            <el-tag size="small" :type="task.direction === 'outbound' ? 'primary' : 'warning'"
                    effect="plain">{{ task.direction_display }}</el-tag>
          </div>
          <div class="meta">
            <span><el-icon><Position /></el-icon> {{ task.route_name }}</span>
            <span><el-icon><Van /></el-icon> {{ task.vehicle_plate }}</span>
            <span><el-icon><Calendar /></el-icon> {{ task.planned_date }}
              {{ task.planned_depart?.slice(0, 5) }} 出发</span>
            <span><el-icon><Wallet /></el-icon>
              {{ task.box_count }} 箱 / ¥{{ formatAmount(task.total_amount) }}</span>
            <span><el-icon><User /></el-icon>
              <template v-for="a in task.assignees" :key="a.id">
                {{ a.user_name }}（{{ a.role_display }}）、
              </template>
            </span>
          </div>
        </div>
        <div class="head-actions">
          <template v-if="task.status === 'planned'">
            <el-button v-if="canCaptain && task.direction === 'outbound' && pendingOutCount > 0"
                       type="warning" plain disabled>
              待出库 {{ pendingOutCount }}/{{ task.box_count }}
            </el-button>
            <el-button v-if="canKeeper && task.direction === 'outbound' && pendingOutCount === 0"
                       type="success" plain>
              <el-icon><CircleCheck /></el-icon> 出库核对完成
            </el-button>
            <el-button v-if="canCaptain" type="primary" :loading="acting" @click="doDepart">
              <el-icon><Promotion /></el-icon> 出发
            </el-button>
          </template>
          <template v-if="['planned', 'in_transit', 'abnormal'].includes(task.status)">
            <el-button v-if="canReportIncident" type="danger" plain @click="incDialog = true">
              <el-icon><Warning /></el-icon> 上报异常
            </el-button>
            <el-button v-if="isDispatcher && task.status === 'in_transit'" type="success"
                       @click="doComplete">
              <el-icon><Flag /></el-icon> 办结任务
            </el-button>
          </template>
          <el-button v-if="isDispatcher && !['completed','cancelled'].includes(task.status)"
                     type="info" plain @click="askCancel">取消任务</el-button>
        </div>
      </div>
      <el-alert v-if="task.status === 'abnormal'" type="error" show-icon
                :closable="false" style="margin-top:12px">
        <template #title>
          任务因异常已挂起，请先在「异常事件」页签处置全部异常；处置后
          {{ task.actual_depart ? '自动恢复押运' : '恢复为已派车，可重新出发' }}。
          未处置异常 {{ openIncidentCount }} 起。
        </template>
      </el-alert>
      <el-alert v-if="task.notes" type="info" :closable="false" show-icon
                style="margin-top:12px" :title="`备注：${task.notes}`" />
    </el-card>

    <el-row :gutter="14">
      <!-- 左：线路与停靠点 -->
      <el-col :span="15">
        <el-card>
          <template #header><span class="card-header">路线与款箱交接进度</span></template>

          <div class="depot-node">
            <el-icon><OfficeBuilding /></el-icon>
            <b>{{ task.depot_name }}</b>（金库）
            <el-tag size="small" type="info" style="margin-left:8px">
              {{ task.actual_depart ? '已出发 ' + fmt(task.actual_depart)
                : task.planned_depart?.slice(0, 5) + ' 计划出发' }}
            </el-tag>
          </div>

          <el-collapse v-model="activeStops">
            <el-collapse-item v-for="stop in task.stops" :key="stop.id"
                              :name="stop.id">
              <template #title>
                <div class="stop-title" :class="`st-${stop.status}`">
                  <span class="seq-dot" :class="stop.status">{{ stop.sequence }}</span>
                  <b>{{ stop.branch_name }}</b>
                  <el-tag size="small" :type="STOP_STATUS[stop.status].type"
                          style="margin:0 8px">
                    {{ STOP_STATUS[stop.status].label }}
                  </el-tag>
                  <span class="plan-time" v-if="stop.planned_arrival">
                    计划 {{ stop.planned_arrival.slice(11, 16) }}
                  </span>
                  <span class="plan-time ok" v-if="stop.actual_arrival">
                    实际 {{ fmt(stop.actual_arrival) }}
                  </span>
                  <el-tag v-if="stop.status === 'arrived'" size="small" type="danger"
                          effect="plain" class="code-tag mono">
                    验证码 {{ stop.verify_code }}
                  </el-tag>
                </div>
              </template>

              <div style="padding:0 4px 10px 30px">
                <div class="stop-toolbar">
                  <el-button v-if="canCaptain && stop.status === 'en_route' && task.status === 'in_transit'"
                             size="small" type="primary" @click="doArrive(stop)">
                    <el-icon><Location /></el-icon> 到达网点
                  </el-button>
                  <el-button v-if="canCaptain && stop.status === 'arrived'" size="small"
                             type="success" plain @click="doFinishStop(stop)">
                    跳过并办结本站
                  </el-button>
                  <span v-if="stop.actual_departure" class="plan-time ok">
                    {{ fmt(stop.actual_departure) }} 驶离
                  </span>
                </div>
                <el-table :data="stop.task_boxes" size="small" border>
                  <el-table-column prop="box_no" label="款箱编号" width="140"
                                   class-name="mono" />
                  <el-table-column prop="box_type_display" label="箱型" width="96" />
                  <el-table-column prop="cash_amount" label="金额(元)" width="100"
                                   align="right">
                    <template #default="{ row }">
                      {{ Number(row.cash_amount).toLocaleString() }}
                    </template>
                  </el-table-column>
                  <el-table-column label="状态" width="92">
                    <template #default="{ row }">
                      <el-tag size="small" :type="BOX_TASK_STATUS[row.status].type">
                        {{ row.status_display }}
                      </el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column label="封签" width="100">
                    <template #default="{ row }">
                      <span class="mono">{{ row.seal_no || '—' }}</span>
                    </template>
                  </el-table-column>
                  <el-table-column label="交接操作" min-width="120">
                    <template #default="{ row }">
                      <el-button v-if="boxAction(row, stop)" link type="primary"
                                 @click="openHandover(row, stop)">
                        {{ boxAction(row, stop).label }}
                      </el-button>
                      <el-tag v-else-if="row.last_handover?.result === 'confirmed'"
                              size="small" type="success">核对一致</el-tag>
                      <span v-else style="color:#909399;font-size:12px">—</span>
                      <el-icon v-if="row.exception_flag" color="#f56c6c"
                               style="vertical-align:middle;margin-left:4px">
                        <Warning />
                      </el-icon>
                    </template>
                  </el-table-column>
                </el-table>
              </div>
            </el-collapse-item>
          </el-collapse>

          <!-- 上收回库按钮（仅本金库管理员可操作） -->
          <div v-if="task.direction === 'inbound'" class="return-bar">
            <template v-if="canKeeper && inTransitCount > 0">
              <el-button v-for="tb in inboundReturnable" :key="tb.id" size="small"
                         type="primary" plain class="mono"
                         @click="openHandover(tb, null)">
                {{ tb.box_no }} 回库核对
              </el-button>
            </template>
            <span v-else-if="inTransitCount > 0" style="color:#909399">
              {{ inTransitCount }} 个款箱返程在途，等待金库回库核对
            </span>
            <span v-else-if="task.status !== 'planned'" style="color:#67c23a">
              全部款箱已回收入库
            </span>
            <span v-else style="color:#909399">出发后到网点办理移交</span>
          </div>
        </el-card>
      </el-col>

      <!-- 右：页签 -->
      <el-col :span="9">
        <el-card>
          <el-tabs v-model="tab" @tab-change="onTab">
            <el-tab-pane label="交接核对" name="reconcile">
              <el-alert v-if="reconcile" :type="reconcile.all_clear ? 'success' : 'warning'"
                        :closable="false" show-icon style="margin-bottom:10px"
                        :title="reconcile.all_clear
                          ? `全部 ${reconcile.total} 个款箱交接链路核对一致`
                          : `${reconcile.total} 个款箱中存在未完成或异常项`" />
              <el-table :data="reconcile?.rows || []" size="small" max-height="520">
                <el-table-column prop="box_no" label="款箱" width="118"
                                 class-name="mono" />
                <el-table-column label="核对" width="70" align="center">
                  <template #default="{ row }">
                    <el-icon :size="18"
                             :color="row.phases_complete && !row.exception_flag ? '#67c23a' : '#e6a23c'">
                      <CircleCheck v-if="row.phases_complete && !row.exception_flag" />
                      <Clock v-else />
                    </el-icon>
                  </template>
                </el-table-column>
                <el-table-column label="环节" min-width="150">
                  <template #default="{ row }">
                    <el-tag v-for="p in row.phases_done" :key="p.phase" size="small"
                            type="success" style="margin:1px">{{ p.display }}</el-tag>
                    <el-tag v-for="p in row.phases_expected.filter(
                        e => !row.phases_done.some(d => d.phase === e.phase))"
                            :key="p" size="small" type="info" style="margin:1px">
                      {{ p.display }}
                    </el-tag>
                    <div v-if="row.problems.length" style="color:#f56c6c;font-size:12px">
                      {{ row.problems.join('、') }}
                    </div>
                    <div v-if="!row.seal_chain_ok && row.phases_done.length"
                         style="color:#e6a23c;font-size:12px">封签链不一致</div>
                  </template>
                </el-table-column>
              </el-table>
            </el-tab-pane>

            <el-tab-pane :label="`交接记录(${task.handovers.length})`" name="handovers">
              <el-timeline style="max-height:540px;overflow:auto;padding-left:4px">
                <el-timeline-item v-for="h in task.handovers" :key="h.id"
                                  :timestamp="h.created_at" placement="top"
                                  :type="h.result === 'confirmed' ? 'success' : 'danger'">
                  <el-tag size="small">{{ h.phase_display }}</el-tag>
                  <b class="mono" style="margin:0 6px">{{ h.box_no }}</b>
                  <el-tag size="small" :type="h.result === 'confirmed' ? 'success' : 'danger'">
                    {{ h.result_display }}
                  </el-tag>
                  <div class="hl">
                    封签：<span class="mono">{{ h.seal_no_out || '—' }}</span>
                    → <span class="mono">{{ h.seal_no_in || '—' }}</span>
                    <span v-if="h.code_verified !== null">
                      ｜验证码：
                      <b :class="h.code_verified ? 'handover-ok' : 'handover-bad'">
                        {{ h.code_verified ? '相符' : '不符' }}
                      </b>
                    </span>
                  </div>
                  <div class="hl dim">
                    {{ h.from_person_name || '—' }} → {{ h.to_person_name || '—' }}
                    ｜登记 {{ h.operator_name }}
                  </div>
                </el-timeline-item>
              </el-timeline>
              <el-empty v-if="!task.handovers.length" description="暂无交接记录"
                        :image-size="60" />
            </el-tab-pane>

            <el-tab-pane :label="`异常事件(${task.incidents.length})`" name="incidents">
              <div v-for="inc in task.incidents" :key="inc.id" class="inc-card">
                <div class="inc-head">
                  <el-tag size="small" :type="SEVERITY[inc.severity].type">
                    {{ inc.severity_display }}
                  </el-tag>
                  <el-tag size="small" type="info">{{ inc.category_display }}</el-tag>
                  <el-tag size="small" :type="INCIDENT_STATUS[inc.status].type">
                    {{ inc.status_display }}
                  </el-tag>
                  <span class="mono dim">{{ inc.incident_no }}</span>
                </div>
                <div class="inc-desc">{{ inc.description }}</div>
                <div class="hl dim">上报：{{ inc.reported_by_name }} · {{ inc.created_at }}</div>
                <template v-if="inc.status !== 'resolved' && isDispatcher">
                  <el-input v-model="resolveMap[inc.id]" type="textarea" :rows="2"
                            placeholder="处置说明（如：核对身份后重新录入验证码，款箱无误）"
                            style="margin-top:8px" />
                  <el-button size="small" type="success" style="margin-top:6px"
                             @click="doResolve(inc)">处置完成</el-button>
                </template>
                <el-tag v-else-if="inc.status !== 'resolved'" size="small"
                        type="warning" style="margin-top:6px">
                  待调度员处置
                </el-tag>
                <el-alert v-else type="success" :closable="false" show-icon
                          style="margin-top:8px"
                          :title="`已处置：${inc.resolution}（${inc.resolved_by_name} ${fmt(inc.resolved_at)}）`" />
              </div>
              <el-empty v-if="!task.incidents.length" description="暂无异常"
                        :image-size="60" />
            </el-tab-pane>

            <el-tab-pane :label="`全程日志(${task.logs.length})`" name="logs">
              <el-timeline style="max-height:540px;overflow:auto;padding-left:4px">
                <el-timeline-item v-for="l in task.logs" :key="l.id"
                                  :timestamp="l.created_at" placement="top"
                                  :type="logType(l.event)">
                  {{ l.message }}
                  <span class="dim"> — {{ l.actor_name }}</span>
                </el-timeline-item>
              </el-timeline>
            </el-tab-pane>
          </el-tabs>
        </el-card>
      </el-col>
    </el-row>

    <HandoverDialog v-model="hdVisible" :task-id="task.id" :tb="currentTb"
                    :phase="currentPhase" :stop="currentStop"
                    @saved="reload" />
    <IncidentDialog v-model="incDialog" :task-id="task.id" :stops="task.stops"
                    @saved="reload" />
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../api/http'
import { useAuthStore } from '../store/auth'
import { isDispatcher as isDisp } from '../auth'
import {
  BOX_TASK_STATUS, INCIDENT_STATUS, SEVERITY, STOP_STATUS, TASK_STATUS,
} from '../constants'
import HandoverDialog from '../components/HandoverDialog.vue'
import IncidentDialog from '../components/IncidentDialog.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const me = computed(() => auth.user)
const task = ref(null)
const tab = ref('reconcile')
const reconcile = ref(null)
const acting = ref(false)
const activeStops = ref([])
const resolveMap = reactive({})

const hdVisible = ref(false)
const incDialog = ref(false)
const currentTb = ref(null)
const currentPhase = ref('')
const currentStop = ref(null)

const isDispatcher = computed(() => isDisp(me.value))
const myCrewRole = computed(() => {
  if (!task.value || !me.value) return null
  return task.value.assignees.find((a) => a.user === me.value.id)?.role_on_task || null
})
const isTaskCaptain = computed(() => myCrewRole.value === 'car_captain')
const isTaskGuard = computed(() =>
  ['car_captain', 'guard'].includes(myCrewRole.value))
const canCaptain = computed(() => isTaskCaptain.value)
const canKeeper = computed(() =>
  me.value?.role === 'vault_keeper' && task.value
  && me.value.branch === task.value.depot)
const canReportIncident = computed(() =>
  isDispatcher.value || isTaskGuard.value)

const pendingOutCount = computed(() =>
  task.value.stops.reduce((n, s) =>
    n + s.task_boxes.filter((b) => b.status === 'pending_out').length, 0))
const inTransitCount = computed(() =>
  task.value.stops.reduce((n, s) =>
    n + s.task_boxes.filter((b) => b.status === 'in_transit').length, 0))
const inboundReturnable = computed(() =>
  task.value.stops.flatMap((s) =>
    s.task_boxes.filter((b) => b.status === 'in_transit')))
const openIncidentCount = computed(() =>
  task.value.incidents.filter((i) => i.status !== 'resolved').length)

async function reload() {
  task.value = await api.get(`/api/tasks/${route.params.id}/`)
  if (tab.value === 'reconcile') await loadReconcile()
  // 自动展开进行中的站
  activeStops.value = task.value.stops
    .filter((s) => ['arrived', 'en_route'].includes(s.status)).map((s) => s.id)
}
async function loadReconcile() {
  reconcile.value = await api.get(`/api/tasks/${route.params.id}/reconcile/`)
}
async function onTab(name) {
  if (name === 'reconcile') await loadReconcile()
}

// 仅当当前登录人有权办理该环节时，才显示交接按钮。
// phase + 目标停靠点共同决定权限：柜员只能办自己网点那一站。
function canRecord(phase, stop = null) {
  // 调度员只指挥不亲手办交接；驾驶员/其他岗位无交接权
  if (phase === 'vault_out' || phase === 'vault_return') {
    return canKeeper.value
  }
  if (isTaskGuard.value) return true
  if (me.value?.role === 'branch_clerk' && stop) {
    // 柜员只能办理本人所属网点停靠点的交接
    const stopBranchId = stop.branch
    return me.value.branch === stopBranchId
  }
  return false
}

function boxAction(tb, stop) {
  const t = task.value
  if (t.status === 'abnormal') return null
  if (t.direction === 'outbound') {
    if (tb.status === 'pending_out' && t.status === 'planned') {
      const phase = 'vault_out'
      return canRecord(phase) ? { phase, label: '金库出库' } : null
    }
    if (tb.status === 'in_transit' && stop.status === 'arrived') {
      const phase = 'branch_recv'
      return canRecord(phase, stop) ? { phase, label: '网点接收' } : null
    }
  } else {
    if (tb.status === 'pending_out' && stop.status === 'arrived') {
      const phase = 'branch_pickup'
      return canRecord(phase, stop) ? { phase, label: '网点移交' } : null
    }
    if (tb.status === 'in_transit') {
      const phase = 'vault_return'
      return canRecord(phase) ? { phase, label: '金库回库' } : null
    }
  }
  return null
}

function openHandover(tb, stop) {
  const action = boxAction(tb, stop)
  if (!action) return
  currentTb.value = tb
  currentPhase.value = action.phase
  currentStop.value = stop
  hdVisible.value = true
}

async function doDepart() {
  acting.value = true
  try {
    await api.post(`/api/tasks/${task.value.id}/depart/`)
    ElMessage.success('任务出发，开始押运')
    await reload()
  } finally { acting.value = false }
}
async function doArrive(stop) {
  await api.post(`/api/tasks/${task.value.id}/arrive/`, { stop_id: stop.id })
  ElMessage.success(`已到达 ${stop.branch_name}`)
  await reload()
}
async function doFinishStop(stop) {
  await api.post(`/api/tasks/${task.value.id}/finish-stop/`, { stop_id: stop.id })
  ElMessage.success(`${stop.branch_name} 已办结`)
  await reload()
}
async function doComplete() {
  try {
    await ElMessageBox.confirm('确认全部交接完成，办结本次押运任务？', '办结确认',
      { type: 'warning' })
  } catch { return }
  try {
    await api.post(`/api/tasks/${task.value.id}/complete/`)
    ElMessage.success('任务已完成，车辆归队')
    await reload()
  } catch { /* 400 已提示 */ }
}
async function askCancel() {
  try {
    const { value } = await ElMessageBox.prompt('请填写取消原因', '取消任务', {
      confirmButtonText: '确认取消', cancelButtonText: '再想想', type: 'warning',
    })
    await api.post(`/api/tasks/${task.value.id}/cancel/`, { reason: value })
    ElMessage.success('任务已取消')
    await reload()
  } catch { /* 取消 */ }
}
async function doResolve(inc) {
  const resolution = (resolveMap[inc.id] || '').trim()
  if (!resolution) { ElMessage.warning('请填写处置说明'); return }
  await api.post(
    `/api/tasks/${task.value.id}/incidents/${inc.id}/resolve/`, { resolution })
  ElMessage.success('异常已处置')
  await reload()
}

function fmt(dt) {
  return dt ? dt.slice(5, 16).replace('T', ' ') : ''
}
function formatAmount(v) {
  return Number(v || 0).toLocaleString('zh-CN', { maximumFractionDigits: 0 })
}
function logType(event) {
  if (event === 'incident' || event === 'handover_fail') return 'danger'
  if (['incident_resolved', 'completed', 'stop_done', 'handover'].includes(event))
    return 'success'
  return 'primary'
}

onMounted(reload)
</script>

<style scoped>
.head { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; }
.title-line { display: flex; align-items: center; gap: 10px; }
.task-no { font-size: 17px; font-weight: 700; color: #1d4e89; }
.task-name { font-size: 14px; color: #606266; }
.meta { display: flex; flex-wrap: wrap; gap: 18px; margin-top: 10px; color: #606266; font-size: 13px; }
.meta span { display: inline-flex; align-items: center; gap: 4px; }
.head-actions { white-space: nowrap; }
.depot-node { display: flex; align-items: center; gap: 6px; padding: 4px 0 12px; color: #1d4e89; }
.stop-title { display: flex; align-items: center; width: 100%; }
.seq-dot {
  display: inline-flex; align-items: center; justify-content: center;
  width: 22px; height: 22px; border-radius: 50%; margin-right: 8px;
  background: #c0c4cc; color: #fff; font-size: 12px;
}
.seq-dot.arrived { background: #1d4e89; }
.seq-dot.en_route { background: #e6a23c; }
.seq-dot.done { background: #67c23a; }
.plan-time { color: #909399; font-size: 12px; }
.plan-time.ok { color: #67c23a; }
.code-tag { margin-left: auto; letter-spacing: 2px; }
.stop-toolbar { margin-bottom: 8px; }
.return-bar { border-top: 1px dashed #dcdfe6; padding: 12px 0 4px 30px; display: flex; flex-wrap: wrap; gap: 8px; }
.inc-card { border: 1px solid #f5d0d0; background: #fff8f8; border-radius: 6px; padding: 10px; margin-bottom: 10px; }
.inc-head { display: flex; gap: 6px; align-items: center; }
.inc-desc { margin: 8px 0 4px; font-size: 13px; color: #303133; }
.hl { font-size: 12px; color: #606266; margin-top: 3px; }
.dim { color: #909399; }
.mono { font-family: monospace; }
</style>
