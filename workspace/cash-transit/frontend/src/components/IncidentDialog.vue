<template>
  <el-dialog v-model="visible" title="上报押运异常" width="520px">
    <el-form label-width="92px">
      <el-form-item label="异常类型" required>
        <el-select v-model="form.category" placeholder="选择异常类型" style="width:100%">
          <el-option v-for="(label, key) in INCIDENT_CATEGORY" :key="key"
                     :value="key" :label="label" />
        </el-select>
      </el-form-item>
      <el-form-item label="严重程度">
        <el-radio-group v-model="form.severity">
          <el-radio v-for="(s, k) in SEVERITY" :key="k" :value="k">
            <el-tag :type="s.type" size="small">{{ s.label }}</el-tag>
          </el-radio>
        </el-radio-group>
      </el-form-item>
      <el-form-item label="关联停靠点">
        <el-select v-model="form.stop" clearable placeholder="可选" style="width:100%">
          <el-option v-for="s in stops" :key="s.id" :value="s.id"
                     :label="`${s.sequence}. ${s.branch_name}`" />
        </el-select>
      </el-form-item>
      <el-form-item label="情况描述" required>
        <el-input v-model="form.description" type="textarea" :rows="4"
                  maxlength="500" show-word-limit
                  placeholder="描述异常经过、现场处置和影响" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="danger" :loading="saving" @click="save">确认上报</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../api/http'
import { INCIDENT_CATEGORY, SEVERITY } from '../constants'

const props = defineProps({
  modelValue: Boolean,
  taskId: Number,
  stops: { type: Array, default: () => [] },
})
const emit = defineEmits(['update:modelValue', 'saved'])
const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})
const saving = ref(false)
const form = reactive({ category: 'traffic', severity: 'low', stop: null,
  description: '' })

watch(() => props.modelValue, (open) => {
  if (open) Object.assign(form, { category: 'traffic', severity: 'low',
    stop: props.stops.find((s) => ['arrived', 'en_route'].includes(s.status))?.id || null,
    description: '' })
})

async function save() {
  if (!form.category || !form.description.trim()) {
    ElMessage.warning('请填写异常类型和情况描述')
    return
  }
  saving.value = true
  try {
    await api.post(`/api/tasks/${props.taskId}/incidents/`, { ...form })
    ElMessage.success('异常已上报，任务已挂起')
    visible.value = false
    emit('saved')
  } finally {
    saving.value = false
  }
}
</script>
