export const TASK_STATUS = {
  draft: { label: '草稿', type: 'info' },
  planned: { label: '已派车', type: 'primary' },
  in_transit: { label: '押运中', type: 'warning' },
  abnormal: { label: '异常挂起', type: 'danger' },
  completed: { label: '已完成', type: 'success' },
  cancelled: { label: '已取消', type: 'info' },
}

export const STOP_STATUS = {
  pending: { label: '待到达', type: 'info' },
  en_route: { label: '前往中', type: 'warning' },
  arrived: { label: '已到达', type: 'primary' },
  done: { label: '交接完成', type: 'success' },
  skipped: { label: '跳过', type: 'info' },
}

export const BOX_TASK_STATUS = {
  pending_out: { label: '待出库', type: 'info' },
  in_transit: { label: '在途', type: 'warning' },
  delivered: { label: '已送达', type: 'success' },
  in_return: { label: '返程在途', type: 'warning' },
  returned: { label: '已回库', type: 'success' },
  exception: { label: '异常', type: 'danger' },
}

export const BRANCH_TYPE = {
  head_vault: '中心金库',
  sub_vault: '分金库',
  branch: '营业网点',
  self_bank: '自助银行',
}

export const INCIDENT_CATEGORY = {
  traffic: '交通延误', seal: '封签异常', box_damage: '款箱破损',
  box_missing: '款箱短少', personnel: '人员异常', vehicle: '车辆故障',
  weather: '天气原因', security: '安全事件', other: '其他',
}

export const SEVERITY = {
  low: { label: '一般', type: 'info' },
  medium: { label: '较重', type: 'warning' },
  high: { label: '严重', type: 'danger' },
}

export const INCIDENT_STATUS = {
  open: { label: '待处理', type: 'danger' },
  processing: { label: '处理中', type: 'warning' },
  resolved: { label: '已处置', type: 'success' },
}

export const DIRECTION = {
  outbound: '下解（金库→网点）',
  inbound: '上收（网点→金库）',
}

export const PHASE = {
  vault_out: '金库出库',
  branch_recv: '网点接收',
  branch_pickup: '网点移交',
  vault_return: '金库回库',
}

export const VEHICLE_STATUS = {
  idle: { label: '待命', type: 'success' },
  on_duty: { label: '执行任务', type: 'warning' },
  maintenance: { label: '维修中', type: 'info' },
}
