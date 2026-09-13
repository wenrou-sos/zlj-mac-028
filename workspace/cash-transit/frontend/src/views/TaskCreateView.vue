<template>
  <div class="page-container">
    <h2 class="page-title">安排押运任务</h2>
    <el-row :gutter="14">
      <el-col :span="16">
        <el-card>
          <template #header><span class="card-header">任务信息</span></template>
          <el-form label-width="92px">
            <el-row :gutter="10">
              <el-col :span="12">
                <el-form-item label="任务方向" required>
                  <el-radio-group v-model="form.direction">
                    <el-radio value="outbound">下解（金库→网点）</el-radio>
                    <el-radio value="inbound">上收（网点→金库）</el-radio>
                  </el-radio-group>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="计划日期" required>
                  <el-date-picker v-model="form.planned_date" type="date"
                                  value-format="YYYY-MM-DD" style="width:100%" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="10">
              <el-col :span="12">
                <el-form-item label="押运线路" required>
                  <el-select v-model="form.route_id" filterable placeholder="选择线路"
                             style="width:100%" @change="onRouteChange">
                    <el-option v-for="r in routes" :key="r.id" :value="r.id"
                               :label="`${r.code} ${r.name}`">
                      <span>{{ r.code }} {{ r.name }}</span>
                      <span style="float:right;color:#909399;font-size:12px">{{ r.stop_count }}站</span>
                    </el-option>
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="押运车辆" required>
                  <el-select v-model="form.vehicle_id" filterable placeholder="选择车辆"
                             style="width:100%">
                    <el-option v-for="v in vehicles" :key="v.id" :value="v.id"
                               :disabled="!isVehicleOk(v)"
                               :label="vehicleLabel(v)">
                      <span>{{ v.plate }} {{ v.model }}</span>
                      <span style="float:right;font-size:12px"
                            :style="isVehicleOk(v) ? 'color:#909399' : 'color:#f56c6c'">
                        {{ isVehicleOk(v)
                          ? `${v.status_display} · ${v.capacity}箱`
                          : vehicleReason(v) }}
                      </span>
                    </el-option>
                  </el-select>
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="10">
              <el-col :span="12">
                <el-form-item label="计划出发">
                  <el-time-picker v-model="form.planned_depart" format="HH:mm"
                                  value-format="HH:mm:ss" placeholder="出发时间"
                                  style="width:100%" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="计划返回">
                  <el-time-picker v-model="form.planned_return" format="HH:mm"
                                  value-format="HH:mm:ss" placeholder="返回时间"
                                  style="width:100%" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-form-item label="备注">
              <el-input v-model="form.notes" maxlength="200" />
            </el-form-item>
          </el-form>
        </el-card>

        <el-card style="margin-top:14px">
          <template #header>
            <span class="card-header">
              车组人员（车长 1 名、押运员 ≥1 名、驾驶员 1 名）
            </span>
          </template>
          <div class="crew-row" v-for="(role, idx) in crewSlots" :key="role.key">
            <el-tag :type="role.type" style="width:88px;text-align:center">{{ role.label }}</el-tag>
            <el-select v-model="crewAssign[role.key]" filterable
                       :placeholder="`选择${role.label}`" style="flex:1">
              <el-option v-for="s in staff" :key="s.id" :value="s.id"
                         :disabled="isPicked(s.id, role.key) || !isStaffOk(s)"
                         :label="`${s.name}（${s.employee_no}）${s.phone}`">
                <span :class="{ 'dim-option': !isStaffOk(s) }">
                  {{ s.name }}（{{ s.employee_no }}）
                  {{ isStaffOk(s) ? s.phone : '｜' + staffReason(s) }}
                </span>
              </el-option>
            </el-select>
            <el-button text type="danger" v-if="role.removable"
                       @click="removeSlot(idx)"><el-icon><Delete /></el-icon></el-button>
          </div>
          <el-button size="small" plain style="margin-top:10px"
                     @click="addGuardSlot"><el-icon><Plus /></el-icon>增加押运员</el-button>
        </el-card>

        <el-card style="margin-top:14px">
          <template #header>
            <span class="card-header">
              款箱分配（{{ form.direction === 'outbound' ? '送达停靠点' : '上收取款点' }}）
              <span style="color:#909399;font-weight:400;font-size:12px">
                共 {{ chosenBoxes.length }} 箱 /
                ¥{{ totalAmount.toLocaleString() }}
              </span>
            </span>
          </template>
          <el-table :data="chosenRows" size="small">
            <el-table-column label="款箱" min-width="150">
              <template #default="{ row }">
                <span class="mono">{{ row.box_no }}</span>
              </template>
            </el-table-column>
            <el-table-column label="箱型" width="100">
              <template #default="{ row }">{{ row.box_type_display }}</template>
            </el-table-column>
            <el-table-column label="归属网点" min-width="120">
              <template #default="{ row }">{{ row.owner_branch_name }}</template>
            </el-table-column>
            <el-table-column label="金额(元)" width="110" align="right">
              <template #default="{ row }">
                {{ Number(row.cash_amount).toLocaleString() }}
              </template>
            </el-table-column>
            <el-table-column :label="form.direction === 'outbound' ? '送至' : '取于'" width="160">
              <template #default="{ row }">
                <el-select v-model="row.seq" size="small" style="width:130px">
                  <el-option v-for="s in selectedRoute?.stops || []" :key="s.sequence"
                             :value="s.sequence"
                             :label="`${s.sequence}.${s.branch_short || s.branch_name}`" />
                </el-select>
              </template>
            </el-table-column>
            <el-table-column width="70">
              <template #default="{ $index }">
                <el-button link type="danger" @click="chosenBoxes.splice($index,1)">移除</el-button>
              </template>
            </el-table-column>
          </el-table>

          <el-divider style="margin:12px 0">
            {{ form.direction === 'outbound'
              ? '从在库空闲款箱中添加（出库下解）'
              : '从已送达网点的款箱中添加（回收上收）' }}
          </el-divider>
          <el-select v-model="pickedBoxIds" multiple filterable collapse-tags
                     collapse-tags-tooltip
                     :placeholder="form.direction === 'outbound'
                       ? '选择在库空闲款箱' : '选择已送达网点、待回收款箱'"
                     style="width:100%" @change="syncChosen">
            <el-option v-for="b in availableBoxes" :key="b.id" :value="b.id"
                       :label="`${b.box_no} ${b.box_type_display} ${b.owner_branch_name}`">
              <span class="mono">{{ b.box_no }}</span>
              {{ b.owner_branch_name }}
              <span style="float:right;color:#b8860b;font-size:12px">
                ¥{{ Number(b.cash_amount).toLocaleString() }}
              </span>
            </el-option>
          </el-select>
          <el-alert v-if="form.direction === 'inbound'" type="info" :closable="false"
                    show-icon style="margin-top:10px"
                    title="上收款箱将在其归属网点办理移交，款箱需与所选停靠网点一致" />
        </el-card>
      </el-col>

      <el-col :span="8">
        <el-card class="sticky-card">
          <template #header><span class="card-header">线路停靠顺序</span></template>
          <el-empty v-if="!selectedRoute" description="请先选择线路" :image-size="70" />
          <el-timeline v-else>
            <el-timeline-item :timestamp="`${selectedRoute.depot_name} 出发`"
                              placement="top" type="primary" hollow>
              <el-tag size="small" type="info">{{ selectedRoute.depot_name }}</el-tag>
            </el-timeline-item>
            <el-timeline-item v-for="s in selectedRoute.stops" :key="s.id"
                              :timestamp="s.planned_arrival || '—'"
                              placement="top" :type="stopCount(s.sequence) ? 'primary' : 'info'">
              <strong>{{ s.sequence }}. {{ s.branch_short || s.branch_name }}</strong>
              <el-tag size="small" round style="margin-left:6px">{{ stopCount(s.sequence) }} 箱</el-tag>
            </el-timeline-item>
            <el-timeline-item :timestamp="`预计${selectedRoute.est_minutes}分钟 / ${selectedRoute.distance_km}km`"
                              placement="top" type="success">
              返回 {{ selectedRoute.depot_name }}
            </el-timeline-item>
          </el-timeline>

          <el-divider />
          <el-space wrap>
            <el-button type="primary" :loading="submitting" @click="submit">派车</el-button>
            <el-button @click="$router.back()">取消</el-button>
          </el-space>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '../api/http'

const route = useRoute()
const router = useRouter()
const routes = ref([])
const vehicles = ref([])
const staff = ref([])
const idleBoxes = ref([])
const deliveredBoxes = ref([])
const pickedBoxIds = ref([])
const chosenBoxes = ref([])
const submitting = ref(false)

const availableBoxes = computed(() =>
  form.direction === 'outbound' ? idleBoxes.value : deliveredBoxes.value)

const form = reactive({
  direction: 'outbound', route_id: null, vehicle_id: null,
  planned_date: new Date().toISOString().slice(0, 10),
  planned_depart: '08:00:00', planned_return: '', notes: '',
})

// 切换下解/上收：可选款箱状态不同，清空已选
watch(() => form.direction, () => {
  pickedBoxIds.value = []
  chosenBoxes.value = []
})

const crewSlots = ref([
  { key: 'car_captain', label: '车长', type: 'danger', removable: false },
  { key: 'guard_0', label: '押运员', type: 'warning', removable: false },
  { key: 'driver', label: '驾驶员', type: 'primary', removable: false },
])
const crewAssign = reactive({})
let guardN = 1

const selectedRoute = computed(() => routes.value.find((r) => r.id === form.route_id))
const chosenRows = computed(() =>
  chosenBoxes.value.map((b) => ({ ...b, seq: b.seq || selectedRoute.value?.stops?.[0]?.sequence })))
const totalAmount = computed(() =>
  chosenBoxes.value.reduce((s, b) => s + Number(b.cash_amount), 0))

function isPicked(id, currentKey) {
  return Object.entries(crewAssign).some(([k, v]) => k !== currentKey && v === id)
}

// 车辆可用性：维修 / 有未完成任务占用均不可选
function isVehicleOk(v) {
  return v.status !== 'maintenance' && !v.busy_task_no
}
function vehicleReason(v) {
  if (v.status === 'maintenance') return '维修中'
  if (v.busy_task_no) return `任务 ${v.busy_task_no} 占用`
  if (v.status === 'on_duty') return '执行任务中'
  return ''
}
function vehicleLabel(v) {
  return `${v.plate} ${isVehicleOk(v) ? '' : '（' + vehicleReason(v) + '）'}`
}

// 人员可用性：缺勤（休假/培训/休息）/ 被未完成任务占用不可选
function isStaffOk(s) {
  return s.schedulable !== false && !(s.busy_task_nos && s.busy_task_nos.length)
}
function staffReason(s) {
  if (!s.active_duty) return s.duty_display || '缺勤'
  if (s.busy_task_nos?.length) return `被任务 ${s.busy_task_nos[0]} 占用`
  return ''
}
function addGuardSlot() {
  crewSlots.value.splice(crewSlots.value.length - 1, 0,
    { key: `guard_${guardN}`, label: '押运员', type: 'warning', removable: true })
  guardN += 1
}
function removeSlot(i) {
  const slot = crewSlots.value[i]
  delete crewAssign[slot.key]
  crewSlots.value.splice(i, 1)
}
function stopCount(seq) {
  return chosenBoxes.value.filter((b) => (b.seq || selectedRoute.value?.stops?.[0]?.sequence) === seq).length
}
function onRouteChange() {
  const firstSeq = selectedRoute.value?.stops?.[0]?.sequence
  chosenBoxes.value.forEach((b) => { b.seq = firstSeq })
}
function syncChosen(ids) {
  chosenBoxes.value = availableBoxes.value
    .filter((b) => ids.includes(b.id))
    .map((b) => ({ ...b, seq: firstStopForBox(b) }))
}

// 款箱归属网点匹配线路停靠点，自动选站
function firstStopForBox(b) {
  const stops = selectedRoute.value?.stops || []
  return stops.find((s) => s.branch_name === b.owner_branch_name)?.sequence
    || stops[0]?.sequence || 1
}

async function submit() {
  const assignees = []
  for (const slot of crewSlots.value) {
    const uid = crewAssign[slot.key]
    if (!uid) {
      ElMessage.warning(`请安排${slot.label}`)
      return
    }
    const role = slot.key.startsWith('guard') ? 'guard' : slot.key
    assignees.push({ user_id: uid, role_on_task: role })
  }
  if (!form.route_id || !form.vehicle_id) {
    ElMessage.warning('请选择线路和车辆')
    return
  }
  if (!chosenBoxes.value.length) {
    ElMessage.warning('至少分配一个款箱')
    return
  }
  const payload = {
    ...form,
    assignees,
    boxes: chosenBoxes.value.map((b) => ({
      box_id: b.id,
      target_stop_sequence: b.seq || selectedRoute.value.stops[0].sequence,
    })),
  }
  submitting.value = true
  try {
    const task = await api.post('/api/tasks/', payload)
    ElMessage.success(`任务 ${task.task_no} 已派车`)
    router.push(`/tasks/${task.id}`)
  } catch (e) {
    // 拦截器提示
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  const [rs, vs, ss, idleResp, deliveredResp] = await Promise.all([
    api.get('/api/routes/', { params: { page_size: 100, active: true } }),
    api.get('/api/vehicles/', { params: { page_size: 100 } }),
    api.get('/api/staff/', { params: { page_size: 200 } }),
    api.get('/api/boxes/', { params: { page_size: 300, status: 'idle' } }),
    api.get('/api/boxes/', { params: { page_size: 300, status: 'delivered' } }),
  ])
  routes.value = rs.results
  vehicles.value = vs.results
  staff.value = ss.results.filter((u) =>
    ['guard', 'driver'].includes(u.role))
  idleBoxes.value = idleResp.results
  deliveredBoxes.value = deliveredResp.results
  if (route.query.route) {
    form.route_id = Number(route.query.route)
    onRouteChange()
  }
})
</script>

<style scoped>
.crew-row { display: flex; gap: 10px; align-items: center; margin-bottom: 10px; }
.sticky-card { position: sticky; top: 8px; }
.mono { font-family: monospace; }
.dim-option { color: #f56c6c; }
</style>
