import { createRouter, createWebHashHistory } from 'vue-router'

// 各岗位默认落地页
const HOME_BY_ROLE = {
  dispatcher: '/dashboard',
  admin: '/dashboard',
  vault_keeper: '/tasks',
  guard: '/tasks',
  driver: '/tasks',
  branch_clerk: '/tasks',
}
// 各岗位允许访问的页面 key（与 MainLayout 菜单一致）
const ALLOWED_BY_ROLE = {
  dispatcher: ['dashboard', 'tasks', 'task-new', 'task-detail', 'incidents',
    'handovers', 'branches', 'resources', 'routes'],
  admin: ['dashboard', 'tasks', 'task-new', 'task-detail', 'incidents',
    'handovers', 'branches', 'resources', 'routes'],
  vault_keeper: ['tasks', 'task-detail', 'handovers'],
  guard: ['tasks', 'task-detail', 'incidents', 'handovers'],
  driver: ['tasks', 'task-detail'],
  branch_clerk: ['tasks', 'task-detail', 'handovers'],
}

const routes = [
  { path: '/login', component: () => import('./views/LoginView.vue'), meta: { public: true } },
  {
    path: '/',
    component: () => import('./layouts/MainLayout.vue'),
    redirect: () => {
      const u = JSON.parse(localStorage.getItem('user') || 'null')
      return (u && HOME_BY_ROLE[u.role]) || '/tasks'
    },
    children: [
      { path: 'dashboard', name: 'dashboard', component: () => import('./views/DashboardView.vue'), meta: { title: '调度总览', key: 'dashboard' } },
      { path: 'tasks', name: 'tasks', component: () => import('./views/TaskListView.vue'), meta: { title: '押运任务', key: 'tasks' } },
      { path: 'tasks/new', name: 'task-new', component: () => import('./views/TaskCreateView.vue'), meta: { title: '安排押运任务', key: 'task-new' } },
      { path: 'tasks/:id', name: 'task-detail', component: () => import('./views/TaskDetailView.vue'), meta: { title: '任务追踪', key: 'task-detail' } },
      { path: 'incidents', name: 'incidents', component: () => import('./views/IncidentListView.vue'), meta: { title: '异常情况', key: 'incidents' } },
      { path: 'handovers', name: 'handovers', component: () => import('./views/HandoverListView.vue'), meta: { title: '交接记录', key: 'handovers' } },
      { path: 'branches', name: 'branches', component: () => import('./views/BranchView.vue'), meta: { title: '网点金库', key: 'branches' } },
      { path: 'resources', name: 'resources', component: () => import('./views/ResourceView.vue'), meta: { title: '车辆款箱人员', key: 'resources' } },
      { path: 'routes', name: 'routes', component: () => import('./views/RouteView.vue'), meta: { title: '押运线路', key: 'routes' } },
    ],
  },
]

const router = createRouter({ history: createWebHashHistory(), routes })

router.beforeEach((to) => {
  const token = localStorage.getItem('access')
  if (!to.meta.public && !token) return { path: '/login' }
  if (to.path === '/login' && token) return { path: '/' }
  // 岗位页面越权访问 → 回到本人首页
  if (token && to.meta.key) {
    const u = JSON.parse(localStorage.getItem('user') || 'null')
    const allowed = u && ALLOWED_BY_ROLE[u.role]
    if (allowed && !allowed.includes(to.meta.key)) {
      return { path: (u && HOME_BY_ROLE[u.role]) || '/tasks' }
    }
  }
})

export default router
