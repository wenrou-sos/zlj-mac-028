<template>
  <div class="login-wrap">
    <div class="login-card">
      <div class="left-panel">
        <div class="brand">
          <el-icon :size="40"><Shield /></el-icon>
          <h1>银卫押运管理系统</h1>
          <p>银行现金尾箱 · 押运调度 · 全程核对追踪</p>
        </div>
        <ul class="features">
          <li><el-icon><Route /></el-icon> 押运路线与车组人员智能安排</li>
          <li><el-icon><Box /></el-icon> 款箱出库 / 交接 / 送达全程登记</li>
          <li><el-icon><CircleCheck /></el-icon> 验证码 + 封签双人交接核对</li>
          <li><el-icon><Aim /></el-icon> 异常上报处置与任务时间轴追踪</li>
        </ul>
      </div>
      <div class="right-panel">
        <h2>用户登录</h2>
        <el-form @submit.prevent="onLogin">
          <el-form-item>
            <el-input v-model="username" size="large" placeholder="工号 / 账号"
                      :prefix-icon="User" />
          </el-form-item>
          <el-form-item>
            <el-input v-model="password" size="large" type="password" show-password
                      placeholder="密码" :prefix-icon="Lock" @keyup.enter="onLogin" />
          </el-form-item>
          <el-button type="primary" size="large" style="width: 100%"
                     :loading="loading" @click="onLogin">登 录</el-button>
        </el-form>
        <el-divider>演示账号（密码 cash123456）</el-divider>
        <div class="demo-accounts">
          <el-tag v-for="a in accounts" :key="a.u" class="acc-tag"
                  @click="username = a.u; password = 'cash123456'"
                  type="info" effect="plain">
            {{ a.label }} {{ a.u }}
          </el-tag>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, Lock } from '@element-plus/icons-vue'
import { useAuthStore } from '../store/auth'

const auth = useAuthStore()
const router = useRouter()
const username = ref('1001')
const password = ref('cash123456')
const loading = ref(false)

const accounts = [
  { u: '1001', label: '调度员' },
  { u: '4001', label: '金库管理员' },
  { u: '2001', label: '车长' },
  { u: 'admin', label: '系统管理员' },
]

async function onLogin() {
  if (!username.value || !password.value) {
    ElMessage.warning('请输入账号和密码')
    return
  }
  loading.value = true
  try {
    await auth.login(username.value.trim(), password.value)
    ElMessage.success('登录成功')
    router.push('/dashboard')
  } catch (e) {
    // 拦截器已提示
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-wrap {
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #0f2c4f 0%, #1d4e89 55%, #2a6db5 100%);
}
.login-card {
  display: flex;
  width: 860px;
  min-height: 460px;
  background: #fff;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 20px 60px rgba(0, 0, 0, .35);
}
.left-panel {
  flex: 1.1;
  background: linear-gradient(160deg, #143a68, #1d4e89);
  color: #fff;
  padding: 44px 36px;
}
.brand h1 { font-size: 24px; margin: 14px 0 6px; }
.brand p { color: #aac6e6; font-size: 13px; margin: 0 0 36px; }
.features { list-style: none; padding: 0; margin: 0; }
.features li { display: flex; align-items: center; gap: 10px; margin-bottom: 20px; color: #d8e6f6; font-size: 14px; }
.right-panel {
  flex: 1;
  padding: 48px 44px;
}
.right-panel h2 { margin: 0 0 28px; color: #1f2d3d; font-size: 20px; }
.demo-accounts { display: flex; flex-wrap: wrap; gap: 8px; }
.acc-tag { cursor: pointer; }
</style>
