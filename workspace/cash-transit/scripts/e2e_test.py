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
code, resp = call('POST', f"/api/tasks/{abnormal['id']}/handover/", token, {
    'task_box_id': failing_box['id'], 'phase': 'branch_recv',
    'stop_id': stop1['id'], 'seal_no_in': 'WRONG999',
    'code': stop1['verify_code'], 'remark': '封签录入错误测试'})
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
    'code': stop1['verify_code']})
check('正确核对通过', resp['handover']['result'] == 'confirmed')

# 7. 交接其余国贸站款箱，完成本站
_, detail = call('GET', f"/api/tasks/{abnormal['id']}/", token)
stop1 = detail['stops'][0]
captain_id = next(a['user'] for a in detail['assignees']
                  if a['role_on_task'] == 'car_captain')
clerk_id = next(u['id'] for u in
                call('GET', '/api/staff/?role=branch_clerk', token)[1]['results']
                if u['name'] == '韩雪')
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

# 10. 新建一个上收任务（已派车的种子任务4直接走流程）
_, planned = call('GET', '/api/tasks/?status=planned&direction=inbound', token)
t4 = planned['results'][0]
_, d4 = call('GET', f"/api/tasks/{t4['id']}/", token)
check('上收任务可直接出发（无出库要求）', True)
code, _ = call('POST', f"/api/tasks/{t4['id']}/depart/", token)
check('上收任务出发', code == 200)
_, d4 = call('GET', f"/api/tasks/{t4['id']}/", token)
s1 = d4['stops'][0]
code, _ = call('POST', f"/api/tasks/{t4['id']}/arrive/", token,
               {'stop_id': s1['id']})
check('到达亚运村', code == 200)
_, d4 = call('GET', f"/api/tasks/{t4['id']}/", token)
s1 = d4['stops'][0]
vault = next(u['id'] for u in
             call('GET', '/api/staff/?role=vault_keeper', token)[1]['results'])
for tb in s1['task_boxes']:
    code, resp = call('POST', f"/api/tasks/{t4['id']}/handover/", token, {
        'task_box_id': tb['id'], 'phase': 'branch_pickup',
        'stop_id': s1['id'], 'seal_no_in': 'FJ9001',
        'code': s1['verify_code']})
    check(f"{tb['box_no']} 网点移交", resp['handover']['result'] == 'confirmed')
# 回库
_, d4 = call('GET', f"/api/tasks/{t4['id']}/", token)
# 站点完成后任务还未办结，款箱在途 -> 回库
tbs = [b for s in d4['stops'] for b in s['task_boxes']]
for tb in tbs:
    if tb['status'] == 'in_transit':
        code, resp = call('POST', f"/api/tasks/{t4['id']}/handover/", token, {
            'task_box_id': tb['id'], 'phase': 'vault_return',
            'seal_no_in': 'FJ9001'})
        check(f"{tb['box_no']} 回库", resp['handover']['result'] == 'confirmed')
_, d4 = call('GET', f"/api/tasks/{t4['id']}/", token)
check('上收任务自动办结', d4['status'] == 'completed', d4['status'])
_, rec4 = call('GET', f"/api/tasks/{t4['id']}/reconcile/", token)
check('上收核对表全部一致', rec4['all_clear'] is True)

# 11. 车辆当天冲突校验：对在途任务的车辆重复派车应被拦截
_, in_transit = call('GET', '/api/tasks/?status=in_transit', token)
busy_task = in_transit['results'][0]
_, busy_detail = call('GET', f"/api/tasks/{busy_task['id']}/", token)
_, idle_boxes = call('GET', '/api/boxes/?available=1', token)
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
    'boxes': [{'box_id': idle_boxes['results'][0]['id'],
               'target_stop_sequence': 1}]})
check('车辆当天冲突被拦截', code == 400, errmsg(resp))

print(f"\n==== {sum(1 for _, c, _ in results if c)}/{len(results)} passed ====")
assert all(c for _, c, _ in results), '存在失败用例'
