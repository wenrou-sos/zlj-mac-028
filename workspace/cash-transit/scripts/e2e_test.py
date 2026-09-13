"""端到端业务流验证（通过 HTTP API）。"""
import json
import urllib.request

BASE = 'http://127.0.0.1:8000'


def call(method, path, token=None, data=None):
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(BASE + path, data=body, method=method)
    req.add_header('Content-Type', 'application/json')
    if token:
        req.add_header('Authorization', f'Bearer {token}')
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def login(username, password='cash123456'):
    _, d = call('POST', '/api/auth/login/', data={'username': username,
                                                    'password': password})
    return d['access'], d['user']


def errmsg(resp):
    if isinstance(resp, dict):
        return resp.get('detail', '')
    return str(resp)[:80]


results = []


def check(name, cond, detail=''):
    results.append((name, cond, detail))
    print(('PASS' if cond else 'FAIL'), name, detail)


# 1. 调度员登录
token, user = login('1001')
check('调度员登录', user['name'] == '张建国')

# 2. 找到异常挂起任务（种子任务3）
_, tasks = call('GET', '/api/tasks/?status=abnormal', token)
abnormal = tasks['results'][0]
check('存在异常挂起任务', abnormal['status'] == 'abnormal', abnormal['task_no'])

# 3. 查看任务详情：异常款箱、验证码
_, detail = call('GET', f"/api/tasks/{abnormal['id']}/", token)
stop1 = detail['stops'][0]
failing_box = next(b for b in stop1['task_boxes']
                   if b['box_no'] == 'KX-GM-01')
inc = detail['incidents'][0]
check('异常款箱已标记', failing_box['exception_flag'] is True)
check('存在未处置异常', inc['status'] == 'open', inc['incident_no'])

# 4. 处置异常
code, _ = call('POST',
               f"/api/tasks/{abnormal['id']}/incidents/{inc['id']}/resolve/",
               token, {'resolution': '经双人核实身份与调令，重新录入正确验证码交接'})
check('处置异常返回200', code == 200)
_, detail = call('GET', f"/api/tasks/{abnormal['id']}/", token)
check('处置后任务恢复押运', detail['status'] == 'in_transit', detail['status'])

# 5. 用错误封签再次交接 → 应触发封签异常
ab_captain = next(a['user'] for a in detail['assignees']
                  if a['role_on_task'] == 'car_captain')
ab_clerk = next(u['id'] for u in
                call('GET', '/api/staff/?role=branch_clerk', token)[1]['results']
                if u['name'] == '韩雪')
code, resp = call('POST', f"/api/tasks/{abnormal['id']}/handover/", token, {
    'task_box_id': failing_box['id'], 'phase': 'branch_recv',
    'stop_id': stop1['id'], 'seal_no_in': 'WRONG999',
    'code': stop1['verify_code'], 'remark': '封签录入错误测试',
    'from_user_id': ab_captain, 'to_user_id': ab_clerk})
check('错误封签被拦截', resp['handover']['result'] == 'seal_mismatch',
      resp['handover']['result'])
_, detail = call('GET', f"/api/tasks/{abnormal['id']}/", token)
check('封签异常再次挂起', detail['status'] == 'abnormal')
inc2 = [i for i in detail['incidents'] if i['status'] == 'open'][0]
check('生成封签异常事件', inc2['category'] == 'seal', inc2['incident_no'])

# 6. 处置后用正确验证码+封签完成交接
call('POST', f"/api/tasks/{abnormal['id']}/incidents/{inc2['id']}/resolve/",
     token, {'resolution': '封签号录入错误，实物封签完好'})
code, resp = call('POST', f"/api/tasks/{abnormal['id']}/handover/", token, {
    'task_box_id': failing_box['id'], 'phase': 'branch_recv',
    'stop_id': stop1['id'], 'seal_no_in': 'FJ2001',
    'code': stop1['verify_code'],
    'from_user_id': ab_captain, 'to_user_id': ab_clerk})
check('正确核对通过', resp['handover']['result'] == 'confirmed')

# 7. 交接其余国贸站款箱，完成本站
_, detail = call('GET', f"/api/tasks/{abnormal['id']}/", token)
stop1 = detail['stops'][0]
captain_id = ab_captain
clerk_id = ab_clerk
for tb in stop1['task_boxes']:
    if tb['status'] == 'in_transit':
        seal = {'KX-GM-02': 'FJ2002'}.get(tb['box_no'], 'FJ2001')
        code, resp = call('POST', f"/api/tasks/{abnormal['id']}/handover/", token, {
            'task_box_id': tb['id'], 'phase': 'branch_recv',
            'stop_id': stop1['id'], 'seal_no_in': seal,
            'code': stop1['verify_code'],
            'from_user_id': captain_id, 'to_user_id': clerk_id})
        check(f"{tb['box_no']} 交接通过", resp['handover']['result'] == 'confirmed')

# 8. 核对表
_, rec = call('GET', f"/api/tasks/{abnormal['id']}/reconcile/", token)
gm_rows = [r for r in rec['rows'] if r['box_no'].startswith('KX-GM')]
check('国贸款箱已送达',
      all(r['status'] == 'delivered' for r in gm_rows))
check('国贸款箱交接环节完整',
      all(r['phases_complete'] for r in gm_rows))

# 9. 未完成任务不能办结（还有 ATM/望京站）
code, resp = call('POST', f"/api/tasks/{abnormal['id']}/complete/", token)
check('未完成任务禁止办结', code == 400, errmsg(resp))

# 10. 新建一个上收任务（种子任务4：回收已送达城西各网点的款箱）
_, planned = call('GET', '/api/tasks/?status=planned&direction=inbound', token)
t4 = planned['results'][0]
check('上收任务为已派车待出发', t4['status'] == 'planned', t4['task_no'])
code, _ = call('POST', f"/api/tasks/{t4['id']}/depart/", token)
check('上收任务出发', code == 200)
seals = {'KX-JRJ-01': 'FJ3001', 'KX-JRJ-02': 'FJ3002', 'KX-XZM-01': 'FJ3003',
         'KX-XZM-02': 'FJ3004', 'KX-XYL-01': 'FJ3005'}
t4_captain = None
while True:
    _, d4 = call('GET', f"/api/tasks/{t4['id']}/", token)
    t4_captain = next(a['user'] for a in d4['assignees']
                      if a['role_on_task'] == 'car_captain')
    stop = next((s for s in d4['stops'] if s['status'] == 'en_route'), None)
    if not stop:
        break
    code, _ = call('POST', f"/api/tasks/{t4['id']}/arrive/", token,
                   {'stop_id': stop['id']})
    check(f"到达 {stop['branch_name']}", code == 200)
    _, d4 = call('GET', f"/api/tasks/{t4['id']}/", token)
    stop = next(s for s in d4['stops'] if s['id'] == stop['id'])
    clerk = next((u['id'] for u in
                  call('GET', '/api/staff/?role=branch_clerk', token)[1]['results']
                  if u['branch'] == stop['branch']), None)
    for tb in stop['task_boxes']:
        code, resp = call('POST', f"/api/tasks/{t4['id']}/handover/", token, {
            'task_box_id': tb['id'], 'phase': 'branch_pickup',
            'stop_id': stop['id'], 'seal_no_in': seals[tb['box_no']],
            'code': stop['verify_code'],
            'from_user_id': clerk, 'to_user_id': t4_captain})
        check(f"{tb['box_no']} 网点移交", resp['handover']['result'] == 'confirmed')

# 回库（最后一站完成后款箱全部在途）
_, d4 = call('GET', f"/api/tasks/{t4['id']}/", token)
vault = next(u['id'] for u in
             call('GET', '/api/staff/?role=vault_keeper', token)[1]['results']
             if u['branch'] == d4.get('depot') or True)
tbs = [b for s in d4['stops'] for b in s['task_boxes']]
for tb in tbs:
    code, resp = call('POST', f"/api/tasks/{t4['id']}/handover/", token, {
        'task_box_id': tb['id'], 'phase': 'vault_return',
        'seal_no_in': seals[tb['box_no']],
        'from_user_id': t4_captain, 'to_user_id': vault})
    check(f"{tb['box_no']} 回库", resp['handover']['result'] == 'confirmed')
_, d4 = call('GET', f"/api/tasks/{t4['id']}/", token)
check('上收任务自动办结', d4['status'] == 'completed', d4['status'])
_, rec4 = call('GET', f"/api/tasks/{t4['id']}/reconcile/", token)
check('上收核对表全部一致', rec4['all_clear'] is True)

# 回库后款箱恢复空闲，可再次安排下解（日循环）
_, box = call('GET', f"/api/boxes/?page_size=300", token)
jrj1 = next(b for b in box['results'] if b['box_no'] == 'KX-JRJ-01')
check('上收回库后款箱恢复在库空闲', jrj1['status'] == 'idle', jrj1['status_display'])

# 11. 车辆当天冲突校验：对在途任务的车辆重复派车应被拦截
_, in_transit = call('GET', '/api/tasks/?status=in_transit', token)
busy_task = in_transit['results'][0]
_, busy_detail = call('GET', f"/api/tasks/{busy_task['id']}/", token)
code, resp = call('POST', '/api/tasks/', token, {
    'direction': 'outbound',
    'route_id': busy_detail['route'], 'vehicle_id': busy_detail['vehicle'],
    'planned_date': busy_detail['planned_date'],
    'assignees': [
        {'user_id': next(a['user'] for a in busy_detail['assignees']
                         if a['role_on_task'] == 'car_captain'),
         'role_on_task': 'car_captain'},
        {'user_id': next(a['user'] for a in busy_detail['assignees']
                         if a['role_on_task'] == 'guard'),
         'role_on_task': 'guard'},
        {'user_id': next(a['user'] for a in busy_detail['assignees']
                         if a['role_on_task'] == 'driver'),
         'role_on_task': 'driver'}],
    'boxes': [{'box_id': jrj1['id'], 'target_stop_sequence': 1}]})
check('车辆当天冲突被拦截', code == 400, errmsg(resp))

# 12. 已被未完成任务占用的款箱不能重复排班
_, zgc_task = call('GET', '/api/tasks/?status=in_transit', token)
zt = next(t for t in zgc_task['results'] if t['task_no'].endswith('002'))
_, ztd = call('GET', f"/api/tasks/{zt['id']}/", token)
# 预先算出当前完全空闲的车组，后续多个用例复用
_, staff_all = call('GET', '/api/staff/?page_size=300', token)
used_user_ids = set()
for t in call('GET', '/api/tasks/?page_size=50', token)[1]['results']:
    _, tdx = call('GET', f"/api/tasks/{t['id']}/", token)
    if tdx['status'] not in ('completed', 'cancelled'):
        used_user_ids.update(a['user'] for a in tdx['assignees'])
free_staff = [u for u in staff_all['results']
              if u['id'] not in used_user_ids and u['active_duty']]
free_captain = next(u['id'] for u in free_staff if u['position'] == 'car_captain')
free_guard = next(u['id'] for u in free_staff if u['position'] == 'escort_guard')
free_driver = next(u['id'] for u in free_staff if u['role'] == 'driver')
code, resp = call('POST', '/api/tasks/', token, {
    'direction': 'outbound', 'route_id': ztd['route'],
    'vehicle_id': next(v['id'] for v in
                       call('GET', '/api/vehicles/', token)[1]['results']
                       if v['status'] == 'idle'),
    'planned_date': ztd['planned_date'],
    'assignees': [
        {'user_id': free_captain, 'role_on_task': 'car_captain'},
        {'user_id': free_guard, 'role_on_task': 'guard'},
        {'user_id': free_driver, 'role_on_task': 'driver'}],
    'boxes': [{'box_id': next(b['id'] for b in
                              call('GET', '/api/boxes/', token)[1]['results']
                              if b['box_no'] == 'KX-ZGC-02'),
               'target_stop_sequence': 1}]})
check('占用款箱重复排班被拦截', code == 400 and 'KX-ZGC-02' in errmsg(resp),
      errmsg(resp))

# 13. 交接缺少交出/接收人应被拒绝（任务002中关村站有待核对款箱）
_, at = call('GET', '/api/tasks/?status=in_transit', token)
t002 = next(t for t in at['results'] if t['task_no'].endswith('002'))
_, atd = call('GET', f"/api/tasks/{t002['id']}/", token)
arrived_stop = next(s for s in atd['stops'] if s['status'] == 'arrived')
tb = next(b for b in arrived_stop['task_boxes'] if b['status'] == 'in_transit')
code, resp = call('POST', f"/api/tasks/{t002['id']}/handover/", token, {
    'task_box_id': tb['id'], 'phase': 'branch_recv',
    'stop_id': arrived_stop['id'], 'seal_no_in': 'FJ1002',
    'code': arrived_stop['verify_code']})
check('交接缺少双方人员被拦截', code == 400, errmsg(resp))

# 14. 已办结任务不能上报异常
code, resp = call('POST', f"/api/tasks/{t4['id']}/incidents/", token, {
    'category': 'other', 'severity': 'low',
    'description': '尝试对已办结任务补报异常'})
check('已办结任务禁止上报异常', code == 400, errmsg(resp))

# 15. 未出发任务上报异常，处置后恢复为「已派车」而非「押运中」
v_idle = next(v['id'] for v in
              call('GET', '/api/vehicles/', token)[1]['results']
              if v['status'] == 'idle')
_, routes_list = call('GET', '/api/routes/', token)
l04 = next(r for r in routes_list['results'] if r['code'] == 'L04')
idle2 = next(b for b in call('GET', '/api/boxes/?status=idle&page_size=300',
                             token)[1]['results']
             if b['owner_branch_name'] == '亚运村支行')
new_task = call('POST', '/api/tasks/', token, {
    'direction': 'outbound', 'route_id': l04['id'], 'vehicle_id': v_idle,
    'planned_date': atd['planned_date'],
    'assignees': [
        {'user_id': free_captain, 'role_on_task': 'car_captain'},
        {'user_id': free_guard, 'role_on_task': 'guard'},
        {'user_id': free_driver, 'role_on_task': 'driver'}],
    'boxes': [{'box_id': idle2['id'], 'target_stop_sequence': 1}]})[1]
check('新任务为已派车', new_task['status'] == 'planned', new_task['status'])
inc_new = call('POST', f"/api/tasks/{new_task['id']}/incidents/", token, {
    'category': 'vehicle', 'severity': 'medium',
    'description': '出车前发现胎压异常'})[1]
_, nd = call('GET', f"/api/tasks/{new_task['id']}/", token)
check('未出发任务异常挂起', nd['status'] == 'abnormal')
code, _ = call('POST',
               f"/api/tasks/{new_task['id']}/incidents/{inc_new['id']}/resolve/",
               token, {'resolution': '更换车辆后恢复排班'})
_, nd = call('GET', f"/api/tasks/{new_task['id']}/", token)
check('处置后恢复已派车（非押运中）', nd['status'] == 'planned', nd['status'])

# 16. 车辆送修 / 复归待命 + 留痕（选无任务占用的待命车）
_, vlist = call('GET', '/api/vehicles/?page_size=100', token)
idle_v = next(v for v in vlist['results']
              if v['status'] == 'idle' and not v['busy_task_no'])
code, resp = call('POST', f"/api/vehicles/{idle_v['id']}/repair/", token,
                  {'reason': '刹车异响送修'})
check('车辆送修成功', code == 200 and resp['vehicle']['status'] == 'maintenance')
code, resp = call('POST', f"/api/vehicles/{idle_v['id']}/repair/", token,
                  {'reason': '重复送修'})
check('维修车重复送修被拦截', code == 400, errmsg(resp))
code, logs = call('GET', f"/api/vehicles/{idle_v['id']}/status-logs/", token)
check('车辆变更留痕', code == 200 and logs[0]['reason'] == '刹车异响送修'
      and logs[0]['operator_name'] == '张建国')
code, resp = call('POST', f"/api/vehicles/{idle_v['id']}/return-service/", token)
check('车辆复归待命', code == 200 and resp['vehicle']['status'] == 'idle')

# 17. 执行中任务占用的车辆不能送修
_, in_t = call('GET', '/api/tasks/?status=in_transit', token)
busy_v = next(t for t in in_t['results'] if t['task_no'].endswith('002'))
on_duty_vid = busy_v['vehicle']
code, resp = call('POST', f"/api/vehicles/{on_duty_vid}/repair/", token,
                  {'reason': '强行送修'})
check('任务占用车辆禁止送修', code == 400 and '任务' in errmsg(resp), errmsg(resp))

# 18. 人员请假 / 复岗 + 被任务占用拦截
# 实时挑一个无未完成任务、在岗的押运员
_, stf = call('GET', '/api/staff/?page_size=300', token)
cur_busy = set()
for t in call('GET', '/api/tasks/?page_size=50', token)[1]['results']:
    _, tdx = call('GET', f"/api/tasks/{t['id']}/", token)
    if tdx['status'] not in ('completed', 'cancelled'):
        cur_busy.update(a['user'] for a in tdx['assignees'])
free_guard_u = next(u for u in stf['results']
                    if u['position'] == 'escort_guard'
                    and u['id'] not in cur_busy and u['active_duty'])
code, resp = call('POST', f"/api/staff/{free_guard_u['id']}/leave/", token,
                  {'leave_type': 'vacation', 'reason': '年假两天'})
check('押运员请假成功', code == 200 and resp['staff']['active_duty'] is False
      and resp['staff']['duty_display'] == '休假')
code, logs = call('GET', f"/api/staff/{free_guard_u['id']}/duty-logs/", token)
check('人员变更留痕', logs[0]['reason'] == '年假两天'
      and logs[0]['operator_name'] == '张建国')
# 休假人员在排班候选中被标记为不可用（前端据此禁用），复岗
_, stf2 = call('GET', '/api/staff/?page_size=300', token)
off = next(u for u in stf2['results'] if u['id'] == free_guard_u['id'])
check('休假押运员标记为不可排班', off['schedulable'] is False
      and off['duty_display'] == '休假')
code, _ = call('POST', f"/api/staff/{free_guard_u['id']}/return-duty/", token)
check('押运员复岗成功', code == 200)

# 19. 被任务占用的人员不能请假
busy_guard_id = next(a['user'] for a in ztd['assignees']
                     if a['role_on_task'] == 'guard')
code, resp = call('POST', f"/api/staff/{busy_guard_id}/leave/", token,
                  {'leave_type': 'training', 'reason': '强行请假'})
check('任务占用人员禁止请假', code == 400 and '任务' in errmsg(resp), errmsg(resp))

# 20. 休假柜员不能办理交接：让柜员临时休假，交接应被拒
clerk_han = next(u for u in stf['results'] if u['name'] == '韩雪')
# 韩雪所在任务003正挂起，先确认她无其他在办占用（任务挂起也算占用，改选蒋帆）
clerk = next(u for u in stf['results'] if u['name'] == '蒋帆')
call('POST', f"/api/staff/{clerk['id']}/leave/", token,
     {'leave_type': 'rest', 'reason': '临时调休'})
arrived = next(s for s in ztd['stops'] if s['status'] == 'arrived')
tb_pending = next(b for b in arrived['task_boxes']
                  if b['status'] == 'in_transit')
code, resp = call('POST', f"/api/tasks/{ztd['id']}/handover/", token, {
    'task_box_id': tb_pending['id'], 'phase': 'branch_recv',
    'stop_id': arrived['id'], 'seal_no_in': 'FJ1002',
    'code': arrived['verify_code'],
    'from_user_id': free_captain, 'to_user_id': clerk['id']})
check('休假柜员交接被拦截', code == 400 and '休息' in errmsg(resp), errmsg(resp))
call('POST', f"/api/staff/{clerk['id']}/return-duty/", token)

print(f"\n==== {sum(1 for _, c, _ in results if c)}/{len(results)} passed ====")
assert all(c for _, c, _ in results), '存在失败用例'
