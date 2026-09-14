<template>
  <el-container style="height: 100vh">
    <el-aside width="220px" class="aside">
      <div class="logo">
        <el-icon :size="24"><Shield /></el-icon>
        <div>
          <div class="logo-name">银卫押运</div>
          <div class="logo-sub">CASH-IN-TRANSIT</div>
        </div>
      </div>
      <el-menu :default-active="$route.path" router class="menu"
               background-color="transparent" text-color="#c5d4e8"
               active-text-color="#ffffff">
        <el-menu-item v-if="canShowMenu(auth.user, 'dashboard')" index="/dashboard">
          <el-icon><DataLine /></el-icon><span>调度总览</span>
        </el-menu-item>
        <el-sub-menu v-if="canShowMenu(auth.user, 'tasks')" index="task">
          <template #title><el-icon><Van /></el-icon><span>押运任务</span></template>
          <el-menu-item v-if="isDispatcher(auth.user)" index="/tasks">任务列表</el-menu-item>
          <el-menu-item v-if="isDispatcher(auth.user)" index="/tasks/new">安排任务</el-menu-item>
          <el-menu-item v-if="!isDispatcher(auth.user)" index="/tasks">我的任务</el-menu-item>
        </el-sub-menu>
        <el-menu-item v-if="canShowMenu(auth.user, 'incidents')" index="/incidents">
          <el-icon><Warning /></el-icon><span>异常情况</span>
        </el-menu-item>
        <el-menu-item v-if="canShowMenu(auth.user, 'handovers')" index="/handovers">
          <el-icon><DocumentChecked /></el-icon><span>交接记录</span>
        </el-menu-item>
        <el-menu-item v-if="isDispatcher(auth.user)" index="/routes">
          <el-icon><Position /></el-icon><span>押运线路</span>
        </el-menu-item>
        <el-menu-item v-if="isDispatcher(auth.user)" index="/branches">
          <el-icon><OfficeBuilding /></el-icon><span>网点金库</span>
        </el-menu-item>
        <el-menu-item v-if="isDispatcher(auth.user)" index="/resources">
          <el-icon><User /></el-icon><span>车辆款箱人员</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="header">
        <div class="crumb">
          <span class="bank-name">城市商业银行 · 现金营运中心</span>
          <el-divider direction="vertical" />
          <span>{{ $route.meta.title }}</span>
        </div>
        <div class="user-box">
          <el-tag type="primary" effect="plain" round>{{ auth.roleText }}</el-tag>
          <el-dropdown @command="onCommand">
            <span class="user-name">
              {{ auth.user?.name }}（{{ auth.user?.employee_no }}）
              <el-icon><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="logout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>
      <el-main class="main">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { useRouter } from 'vue-router'
import { useAuthStore } from '../store/auth'
import { canShowMenu, isDispatcher } from '../auth'

const auth = useAuthStore()
const router = useRouter()

function onCommand(cmd) {
  if (cmd === 'logout') {
    auth.logout()
    router.push('/login')
  }
}
</script>

<style scoped>
.aside {
  background: linear-gradient(180deg, #143a68 0%, #1d4e89 100%);
  display: flex;
  flex-direction: column;
}
.logo {
  height: 64px;
  display: flex;
  align-items: center;
  gap: 10px;
  color: #fff;
  padding: 0 18px;
}
.logo-name { font-size: 19px; font-weight: 700; letter-spacing: 2px; }
.logo-sub { font-size: 9px; color: #8fb4dd; letter-spacing: 1px; }
.menu { border-right: none; flex: 1; }
.menu :deep(.el-sub-menu__title:hover), .menu :deep(.el-menu-item:hover) {
  background-color: rgba(255, 255, 255, 0.08) !important;
}
.menu :deep(.el-menu-item.is-active) { background-color: rgba(255,255,255,.14) !important; }
.header {
  background: #fff;
  border-bottom: 1px solid #e4e7ed;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 22px;
}
.crumb { color: #606266; font-size: 14px; display: flex; align-items: center; }
.bank-name { color: #1d4e89; font-weight: 600; }
.user-box { display: flex; align-items: center; gap: 12px; }
.user-name { cursor: pointer; color: #303133; font-size: 14px; display: flex; align-items: center; gap: 4px; }
.main { background: #f0f2f5; padding: 0; }
.fade-enter-active, .fade-leave-active { transition: opacity .15s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
