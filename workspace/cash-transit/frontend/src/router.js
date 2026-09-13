import { createRouter, createWebHashHistory } from 'vue-router'

const routes = [
  { path: '/login', component: () => import('./views/LoginView.vue'), meta: { public: true } },
  {
    path: '/',
    component: () => import('./layouts/MainLayout.vue'),
    redirect: '/dashboard',
    children: [
      { path: 'dashboard', name: 'dashboard', component: () => import('./views/DashboardView.vue'), meta: { title: '调度总览' } },
      { path: 'tasks', name: 'tasks', component: () => import('./views/TaskListView.vue'), meta: { title: '押运任务' } },
      { path: 'tasks/new', name: 'task-new', component: () => import('./views/TaskCreateView.vue'), meta: { title: '安排押运任务' } },
      { path: 'tasks/:id', name: 'task-detail', component: () => import('./views/TaskDetailView.vue'), meta: { title: '任务追踪' } },
      { path: 'incidents', name: 'incidents', component: () => import('./views/IncidentListView.vue'), meta: { title: '异常情况' } },
      { path: 'handovers', name: 'handovers', component: () => import('./views/HandoverListView.vue'), meta: { title: '交接记录' } },
      { path: 'branches', name: 'branches', component: () => import('./views/BranchView.vue'), meta: { title: '网点金库' } },
      { path: 'resources', name: 'resources', component: () => import('./views/ResourceView.vue'), meta: { title: '车辆款箱人员' } },
      { path: 'routes', name: 'routes', component: () => import('./views/RouteView.vue'), meta: { title: '押运线路' } },
    ],
  },
]

const router = createRouter({ history: createWebHashHistory(), routes })

router.beforeEach((to) => {
  const token = localStorage.getItem('access')
  if (!to.meta.public && !token) return { path: '/login' }
  if (to.path === '/login' && token) return { path: '/' }
})

export default router
