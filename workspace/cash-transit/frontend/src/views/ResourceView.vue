<template>
  <div class="page-container">
    <h2 class="page-title">车辆 · 款箱 · 人员</h2>
    <el-card>
      <el-tabs v-model="tab">
        <!-- 车辆 -->
        <el-tab-pane label="押运车辆" name="vehicles">
          <el-alert type="info" :closable="false" show-icon style="margin-bottom:10px">
            <template #title>
              每日排班前在此登记车辆送修 / 复归；执行未完成任务的车辆不能送修。
            </template>
          </el-alert>
          <el-table :data="vehicles" size="small" stripe>
            <el-table-column prop="plate" label="车牌号" width="110" />
            <el-table-column prop="model" label="车型" min-width="160" />
            <el-table-column prop="capacity" label="核载(箱)" width="90" />
            <el-table-column prop="gps_device" label="GPS设备" width="105" />
            <el-table-column prop="home_branch_name" label="驻停车库" min-width="130" />
            <el-table-column label="状态" width="150">
              <template #default="{ row }">
                <el-tag size="small" :type="VEHICLE_STATUS[row.status].type">
                  {{ row.status_display }}
                </el-tag>
                <el-link v-if="row.busy_task_no" type="warning"
                         @click="$router.push(`/tasks?keyword=${row.busy_task_no}`)"
                         style="margin-left:6px;font-size:12px">
                  {{ row.busy_task_no }}
                </el-link>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="200" fixed="right">
              <template #default="{ row }">
                <el-button v-if="row.status === 'idle'" link type="warning"
                           @click="openRepair(row)">登记送修</el-button>
                <el-button v-if="row.status === 'maintenance'" link type="success"
                           @click="doReturnVehicle(row)">复归待命</el-button>
                <el-button v-if="row.status === 'on_duty'" link disabled
                           title="任务完成后自动归队">任务占用</el-button>
                <el-button link type="primary" @click="openVehicleLogs(row)">
                  变更记录
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <!-- 款箱 -->
        <el-tab-pane label="款箱" name="boxes">
          <div style="margin-bottom:10px;display:flex;gap:10px">
            <el-input v-model="boxKeyword" placeholder="款箱编号/网点" clearable
                      style="width:220px" />
            <el-select v-model="boxStatus" placeholder="状态" clearable style="width:150px">
              <el-option label="在库空闲" value="idle" />
              <el-option label="在途" value="in_transit" />
              <el-option label="已送达网点" value="delivered" />
            </el-select>
          </div>
          <el-table :data="filteredBoxes" size="small" stripe>
            <el-table-column prop="box_no" label="款箱编号" width="150" class-name="mono" />
            <el-table-column label="箱型" width="110">
              <template #default="{ row }">
                <el-tag size="small">{{ row.box_type_display }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="owner_branch_name" label="归属网点" min-width="150" />
            <el-table-column label="面额合计(元)" width="140" align="right">
              <template #default="{ row }">
                {{ Number(row.cash_amount).toLocaleString() }}
              </template>
            </el-table-column>
            <el-table-column label="状态" width="110">
              <template #default="{ row }">
                <el-tag size="small"
                        :type="{ idle: 'success', in_transit: 'warning',
                                 delivered: 'primary' }[row.status]">
                  {{ row.status_display }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="note" label="备注" min-width="120" />
          </el-table>
        </el-tab-pane>

        <!-- 人员 -->
        <el-tab-pane label="押运人员" name="staff">
          <el-alert type="info" :closable="false" show-icon style="margin-bottom:10px">
            <template #title>
              每日排班前在此登记请假 / 培训 / 复岗；有未完成任务的人员不能请假。
              缺勤人员不会出现在排班候选中，也不能办理交接、下单。
            </template>
          </el-alert>
          <el-table :data="staff" size="small" stripe>
            <el-table-column prop="employee_no" label="工号" width="80" />
            <el-table-column prop="name" label="姓名" width="90" />
            <el-table-column label="角色" width="100">
              <template #default="{ row }">
                <el-tag size="small" type="info">{{ row.role_display }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="position_display" label="岗位" width="105" />
            <el-table-column prop="phone" label="电话" width="120" />
            <el-table-column prop="branch_name" label="所属" min-width="140" />
            <el-table-column label="今日状态" width="150">
              <template #default="{ row }">
                <el-tag size="small" :type="row.active_duty ? 'success' : 'danger'">
                  {{ row.duty_display }}
                </el-tag>
                <el-link v-if="row.busy_task_nos?.length" type="warning"
                         @click="$router.push(`/tasks?keyword=${row.busy_task_nos[0]}`)"
                         style="margin-left:6px;font-size:12px">
                  {{ row.busy_task_nos[0] }}
                </el-link>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="170" fixed="right">
              <template #default="{ row }">
                <el-button v-if="row.active_duty" link type="warning"
                           @click="openLeave(row)">登记请假</el-button>
                <el-button v-else link type="success"
                           @click="doReturnDuty(row)">复岗</el-button>
                <el-button link type="primary" @click="openStaffLogs(row)">
                  变更记录
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 车辆送修对话框 -->
    <el-dialog v-model="repairDialog" title="车辆登记送修" width="440px">
      <el-descriptions :column="1" border size="small" style="margin-bottom:14px">
        <el-descriptions-item label="车辆">
          {{ repairRow?.plate }} {{ repairRow?.model }}
        </el-descriptions-item>
      </el-descriptions>
      <el-input v-model="repairReason" type="textarea" :rows="3"
                placeholder="送修原因，如：例行防弹钢板检修，预计两日" maxlength="200"
                show-word-limit />
      <template #footer>
        <el-button @click="repairDialog = false">取消</el-button>
        <el-button type="warning" :loading="acting" @click="confirmRepair">确认送修</el-button>
      </template>
    </el-dialog>

    <!-- 人员请假对话框 -->
    <el-dialog v-model="leaveDialog" title="人员登记缺勤" width="440px">
      <el-descriptions :column="1" border size="small" style="margin-bottom:14px">
        <el-descriptions-item label="人员">
          {{ leaveRow?.name }}（{{ leaveRow?.employee_no }}）
          {{ leaveRow?.position_display }}
        </el-descriptions-item>
      </el-descriptions>
      <el-form label-width="72px">
        <el-form-item label="类型">
          <el-radio-group v-model="leaveType">
            <el-radio v-for="(label, key) in LEAVE_TYPE" :key="key" :value="key">
              {{ label }}
            </el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="事由">
          <el-input v-model="leaveReason" type="textarea" :rows="3"
                    placeholder="如：参加武装押运员年度复训两天" maxlength="200"
                    show-word-limit />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="leaveDialog = false">取消</el-button>
        <el-button type="warning" :loading="acting" @click="confirmLeave">确认</el-button>
      </template>
    </el-dialog>

    <!-- 变更记录抽屉 -->
    <el-drawer v-model="logDrawer" :title="logDrawerTitle" size="520px">
      <el-timeline style="padding-left:6px">
        <el-timeline-item v-for="l in statusLogs" :key="l.id"
                          :timestamp="l.created_at" placement="top"
                          :type="logItemType(l)">
          <template v-if="logKind === 'vehicle'">
            <el-tag size="small">{{ l.from_status_display || '—' }}</el-tag>
            <el-icon style="margin:0 4px"><Right /></el-icon>
            <el-tag size="small" type="warning">{{ l.to_status_display }}</el-tag>
            <div class="log-reason">{{ l.reason }}</div>
            <div class="log-op">操作人：{{ l.operator_name }}</div>
          </template>
          <template v-else>
            <el-tag size="small" :type="l.active_duty ? 'success' : 'danger'">
              {{ l.leave_type_display }}
            </el-tag>
            <div class="log-reason">{{ l.reason }}</div>
            <div class="log-op">操作人：{{ l.operator_name }}</div>
          </template>
        </el-timeline-item>
      </el-timeline>
      <el-empty v-if="!statusLogs.length" description="暂无变更记录" />
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../api/http'
import { LEAVE_TYPE, VEHICLE_STATUS } from '../constants'

const tab = ref('vehicles')
const vehicles = ref([])
const boxes = ref([])
const staff = ref([])
const boxKeyword = ref('')
const boxStatus = ref('')
const acting = ref(false)

const repairDialog = ref(false)
const repairRow = ref(null)
const repairReason = ref('')
const leaveDialog = ref(false)
const leaveRow = ref(null)
const leaveType = ref('vacation')
const leaveReason = ref('')

const logDrawer = ref(false)
const logKind = ref('vehicle')
const statusLogs = ref([])
const logDrawerTitle = ref('')

const filteredBoxes = computed(() => boxes.value.filter((b) => {
  const kw = boxKeyword.value.trim()
  const okKw = !kw || b.box_no.includes(kw) || b.owner_branch_name.includes(kw)
  const okSt = !boxStatus.value || b.status === boxStatus.value
  return okKw && okSt
}))

async function loadVehicles() {
  vehicles.value = (await api.get('/api/vehicles/',
    { params: { page_size: 100 } })).results
}
async function loadStaff() {
  staff.value = (await api.get('/api/staff/',
    { params: { page_size: 300 } })).results
}

function openRepair(row) {
  repairRow.value = row
  repairReason.value = ''
  repairDialog.value = true
}
async function confirmRepair() {
  if (!repairReason.value.trim()) {
    ElMessage.warning('请填写送修原因')
    return
  }
  acting.value = true
  try {
    await api.post(`/api/vehicles/${repairRow.value.id}/repair/`,
      { reason: repairReason.value })
    ElMessage.success(`${repairRow.value.plate} 已登记送修`)
    repairDialog.value = false
    await loadVehicles()
  } finally { acting.value = false }
}
async function doReturnVehicle(row) {
  try {
    await ElMessageBox.confirm(`确认 ${row.plate} 维修完成、复归待命？`, '复归确认',
      { type: 'success' })
  } catch { return }
  await api.post(`/api/vehicles/${row.id}/return-service/`)
  ElMessage.success(`${row.plate} 已复归待命`)
  await loadVehicles()
}

function openLeave(row) {
  leaveRow.value = row
  leaveType.value = 'vacation'
  leaveReason.value = ''
  leaveDialog.value = true
}
async function confirmLeave() {
  if (!leaveReason.value.trim()) {
    ElMessage.warning('请填写事由')
    return
  }
  acting.value = true
  try {
    await api.post(`/api/staff/${leaveRow.value.id}/leave/`, {
      leave_type: leaveType.value, reason: leaveReason.value,
    })
    ElMessage.success(`${leaveRow.value.name} 已登记${LEAVE_TYPE[leaveType.value]}`)
    leaveDialog.value = false
    await loadStaff()
  } finally { acting.value = false }
}
async function doReturnDuty(row) {
  await api.post(`/api/staff/${row.id}/return-duty/`)
  ElMessage.success(`${row.name} 已复岗`)
  await loadStaff()
}

async function openVehicleLogs(row) {
  logKind.value = 'vehicle'
  logDrawerTitle.value = `${row.plate} 状态变更记录`
  statusLogs.value = await api.get(`/api/vehicles/${row.id}/status-logs/`)
  logDrawer.value = true
}
async function openStaffLogs(row) {
  logKind.value = 'staff'
  logDrawerTitle.value = `${row.name} 在岗状态变更记录`
  statusLogs.value = await api.get(`/api/staff/${row.id}/duty-logs/`)
  logDrawer.value = true
}
function logItemType(l) {
  if (logKind.value === 'vehicle') {
    return { idle: 'success', on_duty: 'warning', maintenance: 'info' }[l.to_status]
  }
  return l.active_duty ? 'success' : 'danger'
}

onMounted(async () => {
  await Promise.all([
    loadVehicles(),
    loadStaff(),
    api.get('/api/boxes/', { params: { page_size: 300 } })
      .then((d) => { boxes.value = d.results }),
  ])
})
</script>

<style scoped>
.log-reason { margin-top: 6px; color: #303133; font-size: 13px; }
.log-op { color: #909399; font-size: 12px; margin-top: 2px; }
.mono { font-family: monospace; }
</style>
