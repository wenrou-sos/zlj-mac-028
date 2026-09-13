<template>
  <el-dialog v-model="visible" :title="title" width="520px" @closed="onClosed">
    <el-descriptions :column="2" border size="small" style="margin-bottom:16px">
      <el-descriptions-item label="款箱编号">
        <span class="mono">{{ tb?.box_no }}</span>
      </el-descriptions-item>
      <el-descriptions-item label="箱型">{{ tb?.box_type_display }}</el-descriptions-item>
      <el-descriptions-item label="当前状态">
        <el-tag size="small" :type="BOX_TASK_STATUS[tb?.status]?.type">
          {{ tb?.status_display }}
        </el-tag>
      </el-descriptions-item>
      <el-descriptions-item v-if="stop" label="停靠网点">{{ stop.branch_name }}</el-descriptions-item>
    </el-descriptions>

    <el-alert v-if="needCode" type="warning" :closable="false" show-icon style="margin-bottom:14px">
      <template #title>
        网点交接验证码：
        <b class="mono" style="font-size:18px;letter-spacing:3px;color:#f56c6c">
          {{ stop?.verify_code }}
        </b>
        <span style="margin-left:8px;font-size:12px">请与接收方双人核对后录入</span>
      </template>
    </el-alert>

    <el-form label-width="104px">
      <el-form-item v-if="needCode" label="验证码" required>
        <el-input v-model="form.code" placeholder="请输入4位交接验证码" maxlength="6"
                  class="mono" />
      </el-form-item>
      <el-form-item :label="sealLabel">
        <el-input v-model="form.seal_no_in" :placeholder="sealPlaceholder"
                  maxlength="30" class="mono" />
      </el-form-item>
      <el-form-item v-if="needCode" label="封签外观">
        <el-switch v-model="form.seal_intact" active-text="完好" inactive-text="破损" />
      </el-form-item>
      <el-form-item label="交出人">
        <el-select v-model="form.from_user_id" filterable clearable placeholder="选择交出人"
                   style="width:100%">
          <el-option v-for="u in fromOptions" :key="u.id" :value="u.id"
                     :label="`${u.name}（${u.employee_no}）`" />
        </el-select>
      </el-form-item>
      <el-form-item label="接收人">
        <el-select v-model="toUserId" filterable clearable placeholder="选择接收人"
                   style="width:100%" @update:model-value="form.to_user_id = $event">
          <el-option v-for="u in toOptions" :key="u.id" :value="u.id"
                     :label="`${u.name}（${u.employee_no}）`" />
        </el-select>
      </el-form-item>
      <el-form-item label="备注">
        <el-input v-model="form.remark" type="textarea" :rows="2" maxlength="200" />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="save">确认交接</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../api/http'
import { BOX_TASK_STATUS } from '../constants'

const props = defineProps({
  modelValue: Boolean,
  taskId: Number,
  tb: Object,
  phase: String,
  stop: Object,
  staff: { type: Array, default: () => [] },
})
const emit = defineEmits(['update:modelValue', 'saved'])

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})
const saving = ref(false)
const toUserId = ref(null)
const form = reactive({ code: '', seal_no_in: '', seal_intact: true,
  from_user_id: null, to_user_id: null, remark: '' })

const PHASE_TITLE = {
  vault_out: '金库出库核对',
  branch_recv: '网点接收核对',
  branch_pickup: '网点移交核对（上收）',
  vault_return: '金库回库核对',
}
const title = computed(() => PHASE_TITLE[props.phase] || '交接核对')
const needCode = computed(() =>
  ['branch_recv', 'branch_pickup'].includes(props.phase))
const sealLabel = computed(() => {
  if (props.phase === 'vault_out') return '出库封签号'
  if (props.phase === 'vault_return') return '回库封签号'
  return '封签号核对'
})
const sealPlaceholder = computed(() => {
  if (props.phase === 'branch_recv') return '录入款箱封签号与出库记录核对'
  if (props.phase === 'branch_pickup') return '录入网点加封号'
  if (props.phase === 'vault_out') return '录入金库封签号'
  return '录入封签号（留空不核对）'
})

const fromOptions = computed(() => {
  if (props.phase === 'vault_out')
    return props.staff.filter((u) => u.role === 'vault_keeper')
  // 车长交出
  return props.staff.filter((u) => u.position === 'car_captain')
})
const toOptions = computed(() => {
  if (props.phase === 'branch_recv' || props.phase === 'branch_pickup') {
    const bid = props.stop?.branch
    return props.staff.filter((u) => u.role === 'branch_clerk' &&
      (!bid || u.branch === bid))
  }
  if (props.phase === 'vault_return')
    return props.staff.filter((u) => u.role === 'vault_keeper')
  // 出库接收 = 车长
  return props.staff.filter((u) => u.position === 'car_captain')
})

watch(() => props.modelValue, (open) => {
  if (!open) return
  Object.assign(form, { code: '', seal_no_in: '', seal_intact: true,
    from_user_id: null, to_user_id: null, remark: '' })
  toUserId.value = null
  // 预填默认人员
  if (props.phase === 'vault_out') {
    form.from_user_id = fromOptions.value[0]?.id || null
    form.to_user_id = toOptions.value[0]?.id || null
    toUserId.value = form.to_user_id
  } else if (props.phase === 'vault_return') {
    form.from_user_id = fromOptions.value[0]?.id || null
    form.to_user_id = toOptions.value[0]?.id || null
    toUserId.value = form.to_user_id
  } else if (needCode.value) {
    form.from_user_id = fromOptions.value[0]?.id || null
    form.to_user_id = toOptions.value[0]?.id || null
    toUserId.value = form.to_user_id
  }
})

async function save() {
  if (needCode.value && !form.code) {
    ElMessage.warning('请输入交接验证码')
    return
  }
  if (props.phase === 'vault_out' && !form.seal_no_in) {
    ElMessage.warning('请录入出库封签号')
    return
  }
  saving.value = true
  try {
    const resp = await api.post(`/api/tasks/${props.taskId}/handover/`, {
      task_box_id: props.tb.id,
      phase: props.phase,
      stop_id: props.stop?.id,
      ...JSON.parse(JSON.stringify(form)),
    })
    if (resp.handover.result === 'confirmed') {
      ElMessage.success('交接核对一致')
    } else {
      ElMessage.error(`核对未通过：${resp.handover.result_display}，已生成异常事件并挂起任务`)
    }
    visible.value = false
    emit('saved')
  } catch (e) {
    // 拦截器提示
  } finally {
    saving.value = false
  }
}
function onClosed() {
  form.code = ''
}
</script>

<style scoped>
.mono { font-family: monospace; }
</style>
