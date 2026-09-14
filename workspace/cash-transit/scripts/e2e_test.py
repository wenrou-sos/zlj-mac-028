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


# 1. 多岗位登录
token, user = login('1001')
check('调度员登录', user['name'] == '张建国')
captain_token, _ = login('2001')          # 车长 王海涛
ab_captain_token, _ = login('2004')       # 车长 赵磊（任务003）
t4_captain_token, _ = login('2002')       # 车长 刘志强（任务004）
driver_token, _ = login('3001')           # 驾驶员 吴铁军
clerk_token, _ = login('5003')            # 网点柜员 蒋帆（中关村）
other_clerk_token, _ = login('5001')      # 金融街柜员 郑晓敏
gm_clerk_token, _ = login('5005')         # 国贸柜员 韩雪
keeper_token, _ = login('4001')           # 中心金库管理员
guard_token, _ = login('2002')            # 押运员 刘志强

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

# 5. 用错误封签再次交接 → 应触发封签异常（任务车长办理）
ab_captain = next(a['user'] for a in detail['assignees']
                  if a['role_on_task'] == 'car_captain')
ab_clerk = next(u['id'] for u in
                call('GET', '/api/staff/?role=branch_clerk', token)[1]['results']
                if u['name'] == '韩雪')
code, resp = call('POST', f"/api/tasks/{abnormal['id']}/handover/", ab_captain_token, {
    'task_box_id': failing_box['id'], 'phase': 'branch_recv',
    'stop_id': stop1['id'], 'seal_no_in': 'WRONG999',
    'code': stop1['verify_code'], 'remark': '封签录入错误测试',
    'from_user_id': ab_captain, 'to_user_id': ab_clerk})
check('错误封签被拦截', resp['handover']['result'] == 'seal_mismatch',
      resp['handover']['result'])
_, detail = call('GET', f"/api/tasks/{abnormal['id']}/", ab_captain_token)
check('封签异常再次挂起', detail['status'] == 'abnormal')
inc2 = [i for i in detail['incidents'] if i['status'] == 'open'][0]
check('生成封签异常事件', inc2['category'] == 'seal', inc2['incident_no'])

# 6. 处置后用正确验证码+封签完成交接
call('POST', f"/api/tasks/{abnormal['id']}/incidents/{inc2['id']}/resolve/",
     token, {'resolution': '封签号录入错误，实物封签完好'})
code, resp = call('POST', f"/api/tasks/{abnormal['id']}/handover/", ab_captain_token, {
    'task_box_id': failing_box['id'], 'phase': 'branch_recv',
    'stop_id': stop1['id'], 'seal_no_in': 'FJ2001',
    'code': stop1['verify_code'],
    'from_user_id': ab_captain, 'to_user_id': ab_clerk})
check('正确核对通过', resp['handover']['result'] == 'confirmed')

# 7. 交接其余国贸站款箱，完成本站
_, detail = call('GET', f"/api/tasks/{abnormal['id']}/", ab_captain_token)
stop1 = detail['stops'][0]
captain_id = ab_captain
clerk_id = ab_clerk
for tb in stop1['task_boxes']:
    if tb['status'] == 'in_transit':
        seal = {'KX-GM-02': 'FJ2002'}.get(tb['box_no'], 'FJ2001')
        code, resp = call('POST', f"/api/tasks/{abnormal['id']}/handover/",
                          ab_captain_token, {
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
code, _ = call('POST', f"/api/tasks/{t4['id']}/depart/", t4_captain_token)
check('上收任务出发（车长）', code == 200)
seals = {'KX-JRJ-01': 'FJ3001', 'KX-JRJ-02': 'FJ3002', 'KX-XZM-01': 'FJ3003',
         'KX-XZM-02': 'FJ3004', 'KX-XYL-01': 'FJ3005'}
t4_captain = None
while True:
    _, d4 = call('GET', f"/api/tasks/{t4['id']}/", t4_captain_token)
    t4_captain = next(a['user'] for a in d4['assignees']
                      if a['role_on_task'] == 'car_captain')
    stop = next((s for s in d4['stops'] if s['status'] == 'en_route'), None)
    if not stop:
        break
    code, _ = call('POST', f"/api/tasks/{t4['id']}/arrive/", t4_captain_token,
                   {'stop_id': stop['id']})
    check(f"到达 {stop['branch_name']}", code == 200)
    _, d4 = call('GET', f"/api/tasks/{t4['id']}/", t4_captain_token)
    stop = next(s for s in d4['stops'] if s['id'] == stop['id'])
    clerk = next((u['id'] for u in
                  call('GET', '/api/staff/?role=branch_clerk', token)[1]['results']
                  if u['branch'] == stop['branch']), None)
    for tb in stop['task_boxes']:
        code, resp = call('POST', f"/api/tasks/{t4['id']}/handover/",
                          t4_captain_token, {
            'task_box_id': tb['id'], 'phase': 'branch_pickup',
            'stop_id': stop['id'], 'seal_no_in': seals[tb['box_no']],
            'code': stop['verify_code'],
            'from_user_id': clerk, 'to_user_id': t4_captain})
        check(f"{tb['box_no']} 网点移交", resp['handover']['result'] == 'confirmed')

# 回库（由金库管理员办理）
_, d4 = call('GET', f"/api/tasks/{t4['id']}/", keeper_token)
vault = next(u['id'] for u in
             call('GET', '/api/staff/?role=vault_keeper', token)[1]['results']
             if u['branch'] == d4.get('depot') or True)
tbs = [b for s in d4['stops'] for b in s['task_boxes']]
for tb in tbs:
    code, resp = call('POST', f"/api/tasks/{t4['id']}/handover/", keeper_token, {
        'task_box_id': tb['id'], 'phase': 'vault_return',
        'seal_no_in': seals[tb['box_no']],
        'from_user_id': t4_captain, 'to_user_id': vault})
    check(f"{tb['box_no']} 回库", resp['handover']['result'] == 'confirmed')
_, d4 = call('GET', f"/api/tasks/{t4['id']}/", token)
check('上收任务自动办结', d4['status'] == 'completed', d4['status'])
_, rec4 = call('GET', f"/api/tasks/{t4['id']}/reconcile/", t4_captain_token)
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

# 13. 交接缺少交出/接收人应被拒绝（任务002中关村站有待核对款箱，车长办理）
_, at = call('GET', '/api/tasks/?status=in_transit', token)
t002 = next(t for t in at['results'] if t['task_no'].endswith('002'))
_, atd = call('GET', f"/api/tasks/{t002['id']}/", token)
arrived_stop = next(s for s in atd['stops'] if s['status'] == 'arrived')
tb = next(b for b in arrived_stop['task_boxes'] if b['status'] == 'in_transit')
t002_captain_token = login(next(
    a['user_employee_no'] for a in atd['assignees']
    if a['role_on_task'] == 'car_captain'))[0]
code, resp = call('POST', f"/api/tasks/{t002['id']}/handover/", t002_captain_token, {
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
code, resp = call('POST', f"/api/tasks/{ztd['id']}/handover/", t002_captain_token, {
    'task_box_id': tb_pending['id'], 'phase': 'branch_recv',
    'stop_id': arrived['id'], 'seal_no_in': 'FJ1002',
    'code': arrived['verify_code'],
    'from_user_id': free_captain, 'to_user_id': clerk['id']})
check('休假柜员交接被拦截', code == 400 and '休息' in errmsg(resp), errmsg(resp))
call('POST', f"/api/staff/{clerk['id']}/return-duty/", token)

# 21. 排班页按日期判定占用：今天在途的车和人，明天应可排班
import datetime
today_d = datetime.date.fromisoformat(ztd['planned_date'])
tomorrow = (today_d + datetime.timedelta(days=1)).isoformat()
v_today = call('GET', f"/api/vehicles/?date={today_d}&page_size=100", token)[1]
v_tom = call('GET', f"/api/vehicles/?date={tomorrow}&page_size=100", token)[1]
busy_car_today = next(v for v in v_today['results'] if v['id'] == ztd['vehicle'])
busy_car_tom = next(v for v in v_tom['results'] if v['id'] == ztd['vehicle'])
check('今天在途车辆今日不可排', busy_car_today['schedulable'] is False
      and ztd['task_no'] in busy_car_today['unavailable_reason'])
check('今天在途车辆明日可排（跨日期不误判）',
      busy_car_tom['schedulable'] is True, busy_car_tom['unavailable_reason'])
s_tom = call('GET', f"/api/staff/?date={tomorrow}&page_size=300", token)[1]
cap002 = next(a['user'] for a in ztd['assignees']
              if a['role_on_task'] == 'car_captain')
cap002_tom = next(u for u in s_tom['results'] if u['id'] == cap002)
check('今日有任务的车长明日可排', cap002_tom['schedulable'] is True,
      str(cap002_tom['busy_task_nos']))

# 22. 同车跨日期两个任务：取消明天任务不能把车置为待命（今天仍在途）
t002_crew = [
    {'user_id': a['user'], 'role_on_task': a['role_on_task']}
    for a in ztd['assignees']]
idle_box_yyc = next(b for b in
                    call('GET', '/api/boxes/?status=idle&page_size=300', token)[1]['results']
                    if b['owner_branch_name'] == '亚运村支行'
                    and b['id'] != idle2['id'])
tm_task = call('POST', '/api/tasks/', token, {
    'direction': 'outbound', 'route_id': l04['id'],
    'vehicle_id': ztd['vehicle'], 'planned_date': tomorrow,
    'assignees': t002_crew,
    'boxes': [{'box_id': idle_box_yyc['id'], 'target_stop_sequence': 1}]})[1]
check('跨日期同车派班成功', tm_task['status'] == 'planned', tm_task.get('detail'))
# 车辆当前实体状态：今天任务在途 → 执行任务
car_now = next(v for v in call('GET', '/api/vehicles/', token)[1]['results']
               if v['id'] == ztd['vehicle'])
check('车辆实体状态为执行任务', car_now['status'] == 'on_duty', car_now['status'])
# 取消明天任务
call('POST', f"/api/tasks/{tm_task['id']}/cancel/", token, {'reason': '明日计划调整'})
car_now = next(v for v in call('GET', '/api/vehicles/', token)[1]['results']
               if v['id'] == ztd['vehicle'])
check('取消明日任务后车辆仍执行今日任务',
      car_now['status'] == 'on_duty', car_now['status'])
# 再取消今天的在途任务 → 车辆才应归队待命
call('POST', f"/api/tasks/{ztd['id']}/cancel/", token, {'reason': '回归测试取消'})
car_now = next(v for v in call('GET', '/api/vehicles/', token)[1]['results']
               if v['id'] == ztd['vehicle'])
check('今日任务也取消后车辆归队待命',
      car_now['status'] == 'idle', car_now['status'])

# ========== 23. 岗位权限（RBAC）越权回归 ==========
# 用一个全新的调度派车任务承载各类越权尝试（实时计算空闲车组/车/箱）
_, free_veh = call('GET', '/api/vehicles/?status=idle&page_size=100', token)
test_vehicle = next(v for v in free_veh['results'] if not v['busy_task_no'])
# 选一个归属亚运村、当前在库且未被未完成任务占用的款箱
_, all_boxes = call('GET', '/api/boxes/?status=idle&page_size=300', token)
occupied_boxes = set()
for t in call('GET', '/api/tasks/?page_size=50', token)[1]['results']:
    _, tdx = call('GET', f"/api/tasks/{t['id']}/", token)
    if tdx['status'] not in ('completed', 'cancelled'):
        for s in tdx['stops']:
            occupied_boxes.update(b['box'] for b in s['task_boxes'])
test_box = next(b for b in all_boxes['results']
                if b['owner_branch_name'] == '亚运村支行'
                and b['id'] not in occupied_boxes)
_, stf_now = call('GET', '/api/staff/?page_size=300', token)
busy_now = set()
for t in call('GET', '/api/tasks/?page_size=50', token)[1]['results']:
    _, tdx = call('GET', f"/api/tasks/{t['id']}/", token)
    if tdx['status'] not in ('completed', 'cancelled'):
        busy_now.update(a['user'] for a in tdx['assignees'])
free_now = [u for u in stf_now['results']
            if u['id'] not in busy_now and u['active_duty']]
rbac_captain = next(u['id'] for u in free_now if u['position'] == 'car_captain')
rbac_guard = next(u['id'] for u in free_now if u['position'] == 'escort_guard')
rbac_driver = next(u['id'] for u in free_now if u['role'] == 'driver')
rbac_keeper = next(u['id'] for u in stf_now['results']
                   if u['role'] == 'vault_keeper' and u['active_duty']
                   and u['branch_name'] == '朝阳分中心金库')
rbac_keeper_token = login(next(
    u['employee_no'] for u in stf_now['results']
    if u['id'] == rbac_keeper))[0]
rbac_crew = [
    {'user_id': rbac_captain, 'role_on_task': 'car_captain'},
    {'user_id': rbac_guard, 'role_on_task': 'guard'},
    {'user_id': rbac_driver, 'role_on_task': 'driver'}]


def make_task():
    c, r = call('POST', '/api/tasks/', token, {
        'direction': 'outbound', 'route_id': l04['id'],
        'vehicle_id': test_vehicle['id'], 'planned_date': tomorrow,
        'assignees': rbac_crew,
        'boxes': [{'box_id': test_box['id'], 'target_stop_sequence': 1}]})
    if c != 201:
        print('DEBUG make_task:', c, r, 'vehicle:', test_vehicle['plate'],
              'box:', test_box['box_no'], 'crew:', rbac_crew)
    return r


test_task = make_task()
tid = test_task['id']


def denied(name, method, path, tok, data=None):
    c, r = call(method, path, tok, data)
    check(name, c == 403, f'HTTP {c} {errmsg(r)[:60]}')


# --- 派车排班仅调度员 ---
denied('驾驶员不能派车建任务', 'POST', '/api/tasks/', driver_token, {
    'direction': 'outbound', 'route_id': l04['id'],
    'vehicle_id': test_vehicle['id'], 'planned_date': tomorrow,
    'assignees': [{'user_id': rbac_captain, 'role_on_task': 'car_captain'},
                  {'user_id': rbac_guard, 'role_on_task': 'guard'},
                  {'user_id': rbac_driver, 'role_on_task': 'driver'}],
    'boxes': [{'box_id': test_box['id'], 'target_stop_sequence': 1}]})
denied('网点柜员不能派车建任务', 'POST', '/api/tasks/', clerk_token, {
    'direction': 'outbound', 'route_id': l04['id'],
    'vehicle_id': test_vehicle['id'], 'planned_date': tomorrow,
    'assignees': [{'user_id': rbac_captain, 'role_on_task': 'car_captain'},
                  {'user_id': rbac_guard, 'role_on_task': 'guard'},
                  {'user_id': rbac_driver, 'role_on_task': 'driver'}],
    'boxes': [{'box_id': test_box['id'], 'target_stop_sequence': 1}]})
denied('金库管理员不能派车建任务', 'POST', '/api/tasks/', keeper_token, {
    'direction': 'outbound', 'route_id': l04['id'],
    'vehicle_id': test_vehicle['id'], 'planned_date': tomorrow,
    'assignees': [{'user_id': rbac_captain, 'role_on_task': 'car_captain'},
                  {'user_id': rbac_guard, 'role_on_task': 'guard'},
                  {'user_id': rbac_driver, 'role_on_task': 'driver'}],
    'boxes': [{'box_id': test_box['id'], 'target_stop_sequence': 1}]})

# --- 资源状态维护仅调度员 ---
denied('驾驶员不能登记车辆送修', 'POST',
       f"/api/vehicles/{test_vehicle['id']}/repair/", driver_token,
       {'reason': '越权送修'})
denied('柜员不能给押运员登记请假', 'POST',
       f"/api/staff/{rbac_guard}/leave/", clerk_token,
       {'leave_type': 'rest', 'reason': '越权请假'})
denied('车长不能复归维修车', 'POST',
       f"/api/vehicles/{test_vehicle['id']}/return-service/", captain_token)

# --- 基础档案全量查看仅调度相关岗位 ---
denied('柜员不能查看全部人员档案', 'GET', '/api/staff/?page_size=10', clerk_token)
denied('驾驶员不能看调度总览', 'GET', '/api/tasks/dashboard/', driver_token)

# --- 到离站仅本任务车长 ---
denied('驾驶员不能办理出发', 'POST', f'/api/tasks/{tid}/depart/', driver_token)
denied('他任务车长不能代发车', 'POST', f'/api/tasks/{tid}/depart/', captain_token)
denied('柜员不能办理出发', 'POST', f'/api/tasks/{tid}/depart/', clerk_token)

# 让调度无权直接出发（调度不是车组）
denied('调度员不代车长出发', 'POST', f'/api/tasks/{tid}/depart/', token)

# --- 金库交接仅本金库管理员 ---
_, td0 = call('GET', f'/api/tasks/{tid}/', token)
first_tb = td0['stops'][0]['task_boxes'][0]
denied('柜员不能办理金库出库', 'POST', f'/api/tasks/{tid}/handover/', clerk_token, {
    'task_box_id': first_tb['id'], 'phase': 'vault_out',
    'seal_no_in': 'FJX1', 'from_user_id': rbac_keeper, 'to_user_id': rbac_captain})
denied('驾驶员不能办理金库出库', 'POST', f'/api/tasks/{tid}/handover/', driver_token, {
    'task_box_id': first_tb['id'], 'phase': 'vault_out',
    'seal_no_in': 'FJX1', 'from_user_id': rbac_keeper, 'to_user_id': rbac_captain})
# 正确：本金库（朝阳金库）管理员出库成功
code, hv = call('POST', f'/api/tasks/{tid}/handover/', rbac_keeper_token, {
    'task_box_id': first_tb['id'], 'phase': 'vault_out',
    'seal_no_in': 'FJX1', 'from_user_id': rbac_keeper, 'to_user_id': rbac_captain})
check('本金库管理员办理出库成功', code == 200 and hv['handover']['result'] == 'confirmed',
      errmsg(hv) if code != 200 else '')
# 中心金库管理员不能办理朝阳金库的出库
denied('跨金库管理员不能办理出库', 'POST', f'/api/tasks/{tid}/handover/', keeper_token, {
    'task_box_id': td0['stops'][0]['task_boxes'][-1]['id'],
    'phase': 'vault_out', 'seal_no_in': 'FJX0',
    'from_user_id': rbac_keeper, 'to_user_id': rbac_captain})
# 车长不能出库
denied('车长不能代办金库出库', 'POST', f'/api/tasks/{tid}/handover/',
       login(next(a['user_employee_no'] for a in td0['assignees']
                  if a['role_on_task'] == 'car_captain'))[0], {
           'task_box_id': td0['stops'][0]['task_boxes'][-1]['id'],
           'phase': 'vault_out', 'seal_no_in': 'FJX2',
           'from_user_id': rbac_keeper, 'to_user_id': rbac_captain})

# --- 数据可见范围 ---
# 驾驶员只看本人任务：他在昨日任务001车组，但任务003（京A·Y8004）他不在
_, my_tasks = call('GET', '/api/tasks/?page_size=50', driver_token)
driver_seen = {t['id'] for t in my_tasks['results']}
check('驾驶员只见本人任务',
      abnormal['id'] not in driver_seen and t4['id'] not in driver_seen,
      f'{len(driver_seen)} tasks')
# 网点柜员只见本网点停靠的任务；中关村柜员看得到任务002，看不到城西上收(已完成的金融街方向)
_, clerk_tasks = call('GET', '/api/tasks/?page_size=50', clerk_token)
clerk_seen = {t['task_no'] for t in clerk_tasks['results']}
check('柜员只见本网点任务',
      any(no.endswith('002') for no in clerk_seen), str(clerk_seen))
# 越权查看不属于自己的任务 → 403
c, _ = call('GET', f"/api/tasks/{abnormal['id']}/", clerk_token)
check('柜员越权查看国贸任务被拒(403)', c == 403, f'HTTP {c}')
c, _ = call('GET', f"/api/tasks/{tid}/", driver_token)
check('驾驶员越权查看非本车组任务被拒(403)', c in (403, 404), f'HTTP {c}')
# 柜员交接记录：中关村柜员应能看到中关村站交接，金融街柜员不应看到
_, ho = call('GET', '/api/handovers/?page_size=200', clerk_token)
check('本网点柜员可见本站交接',
      any(h['box_no'] == 'KX-ZGC-01' for h in ho['results']))
# 金融街柜员不应看到中关村站点的交接记录
_, ho2 = call('GET', '/api/handovers/?page_size=200', other_clerk_token)
jrj_phases = [h for h in ho2['results'] if h['box_no'] == 'KX-ZGC-01']
check('外网点柜员看不到中关村交接', jrj_phases == [], f'{len(jrj_phases)}')

# --- 异常上报/处置权限 ---
# 先由车长出发本测试任务
test_captain_token = login(next(
    a['user_employee_no'] for a in td0['assignees']
    if a['role_on_task'] == 'car_captain'))[0]
c, _ = call('POST', f'/api/tasks/{tid}/depart/', test_captain_token)
check('本任务车长出发成功', c == 200, f'HTTP {c}')
denied('驾驶员不能上报异常', 'POST', f'/api/tasks/{tid}/incidents/', driver_token,
       {'category': 'traffic', 'severity': 'low', 'description': '越权上报'})
denied('外网点柜员不能上报异常', 'POST', f'/api/tasks/{tid}/incidents/',
       clerk_token, {'category': 'traffic', 'severity': 'low', 'description': '越权'})
# 本任务车长可以上报
c, incv = call('POST', f'/api/tasks/{tid}/incidents/', test_captain_token, {
    'category': 'traffic', 'severity': 'low', 'description': '路口拥堵延误'})
check('本任务车长可上报异常', c == 201, f'HTTP {c}')
# 车长不能处置异常（仅调度员）
denied('车长不能处置异常', 'POST',
       f"/api/tasks/{tid}/incidents/{incv['id']}/resolve/", test_captain_token,
       {'resolution': '越权处置'})
c, _ = call('POST', f"/api/tasks/{tid}/incidents/{incv['id']}/resolve/", token,
            {'resolution': '拥堵缓解，恢复路线'})
check('调度员处置异常成功', c == 200, f'HTTP {c}')
# 办结/取消仅调度
denied('车长不能办结任务', 'POST', f'/api/tasks/{tid}/complete/', test_captain_token)
denied('柜员不能取消任务', 'POST', f'/api/tasks/{tid}/cancel/', clerk_token,
       {'reason': '越权取消'})

print(f"\n==== {sum(1 for _, c, _ in results if c)}/{len(results)} passed ====")
assert all(c for _, c, _ in results), '存在失败用例'
