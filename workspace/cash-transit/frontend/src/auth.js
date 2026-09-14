// 岗位权限：菜单、按钮与数据范围
export const ROLE = {
  DISPATCHER: 'dispatcher',
  GUARD: 'guard',
  DRIVER: 'driver',
  BRANCH_CLERK: 'branch_clerk',
  VAULT_KEEPER: 'vault_keeper',
  ADMIN: 'admin',
}

export function isAdmin(u) {
  return u?.role === ROLE.ADMIN
}
export function isDispatcher(u) {
  return u?.role === ROLE.DISPATCHER || isAdmin(u)
}
export function isGuard(u) {
  return u?.role === ROLE.GUARD
}
export function isDriver(u) {
  return u?.role === ROLE.DRIVER
}
export function isKeeper(u) {
  return u?.role === ROLE.VAULT_KEEPER
}
export function isClerk(u) {
  return u?.role === ROLE.BRANCH_CLERK
}

// 菜单 key 按岗位显隐；admin 可见全部
export function canShowMenu(user, key) {
  if (!user) return false
  if (isAdmin(user)) return true
  switch (user.role) {
    case ROLE.DISPATCHER:
      return true
    case ROLE.VAULT_KEEPER:
      return ['tasks', 'handovers'].includes(key)
    case ROLE.GUARD:
      return ['tasks', 'incidents', 'handovers'].includes(key)
    case ROLE.DRIVER:
      return ['tasks'].includes(key)
    case ROLE.BRANCH_CLERK:
      return ['tasks', 'handovers'].includes(key)
    default:
      return false
  }
}
