<template>
  <div class="page-container">
    <h2 class="page-title">车辆 · 款箱 · 人员</h2>
    <el-card>
      <el-tabs v-model="tab">
        <!-- 车辆 -->
        <el-tab-pane label="押运车辆" name="vehicles">
          <el-table :data="vehicles" size="small" stripe>
            <el-table-column prop="plate" label="车牌号" width="120" />
            <el-table-column prop="model" label="车型" min-width="170" />
            <el-table-column prop="capacity" label="核载(箱)" width="90" />
            <el-table-column prop="gps_device" label="GPS设备" width="110" />
            <el-table-column prop="home_branch_name" label="驻停车库" min-width="150" />
            <el-table-column label="状态" width="100">
              <template #default="{ row }">
                <el-tag size="small" :type="VEHICLE_STATUS[row.status].type">
                  {{ row.status_display }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="note" label="备注" min-width="100" />
          </el-table>
        </el-tab-pane>

        <!-- 款箱 -->
        <el-tab-pane label="款箱" name="boxes">
          <div style="margin-bottom:10px;display:flex;gap:10px">
            <el-input v-model="boxKeyword" placeholder="款箱编号/网点" clearable
                      style="width:220px" />
            <el-select v-model="boxStatus" placeholder="状态" clearable style="width:130px">
              <el-option label="在库空闲" value="idle" />
              <el-option label="在途" value="in_transit" />
              <el-option label="已送达" value="delivered" />
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
            <el-table-column label="状态" width="100">
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
          <el-table :data="staff" size="small" stripe>
            <el-table-column prop="employee_no" label="工号" width="90" />
            <el-table-column prop="name" label="姓名" width="100" />
            <el-table-column label="角色" width="110">
              <template #default="{ row }">
                <el-tag size="small" type="info">{{ row.role_display }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="position_display" label="岗位" width="110" />
            <el-table-column prop="phone" label="电话" width="130" />
            <el-table-column prop="branch_name" label="所属" min-width="160" />
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <el-tag size="small" :type="row.active_duty ? 'success' : 'info'">
                  {{ row.active_duty ? '在岗' : '休息' }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import api from '../api/http'
import { VEHICLE_STATUS } from '../constants'

const tab = ref('vehicles')
const vehicles = ref([])
const boxes = ref([])
const staff = ref([])
const boxKeyword = ref('')
const boxStatus = ref('')

const filteredBoxes = computed(() => boxes.value.filter((b) => {
  const kw = boxKeyword.value.trim()
  const okKw = !kw || b.box_no.includes(kw) || b.owner_branch_name.includes(kw)
  const okSt = !boxStatus.value || b.status === boxStatus.value
  return okKw && okSt
}))

onMounted(async () => {
  const [v, b, s] = await Promise.all([
    api.get('/api/vehicles/', { params: { page_size: 100 } }),
    api.get('/api/boxes/', { params: { page_size: 300 } }),
    api.get('/api/staff/', { params: { page_size: 300 } }),
  ])
  vehicles.value = v.results
  boxes.value = b.results
  staff.value = s.results
})
</script>
