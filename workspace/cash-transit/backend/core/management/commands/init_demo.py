"""内置样例数据：网点/金库、车辆、人员、款箱、线路，并生成不同状态的押运任务。

运行：python manage.py init_demo
幂等：已存在同编号数据则跳过基础档案；任务全部重新生成。
"""
from datetime import time, timedelta

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import Position, Role, User
from core.models import (Branch, CashBox, Route, RouteStop, Task,
                         TaskAssignee, TaskBox, TaskStop, Vehicle)
from core.services import TaskService

PASSWORD = 'cash123456'


# ---------- 网点（北京城区，经纬度为示意坐标） ----------
BRANCHES = [
    # code, 名称, 简称, 类型, 地址, 联系人, 电话, lng, lat, 营业起止
    ('JK001', '总行现金营运中心金库', '中心金库', 'head_vault',
     '北京市西城区金融大街25号', '周金库', '010-66001001',
     116.3547, 39.9078, time(7, 0), time(19, 0)),
    ('JK002', '朝阳分中心金库', '朝阳金库', 'sub_vault',
     '北京市朝阳区建国路88号', '吴库管', '010-66001002',
     116.4625, 39.9087, time(7, 30), time(18, 30)),
    ('WD001', '金融街支行', '金融街', 'branch',
     '北京市西城区金融大街19号富凯大厦', '郑晓敏', '010-66002001',
     116.3560, 39.9150, time(9, 0), time(17, 0)),
    ('WD002', '西直门支行', '西直门', 'branch',
     '北京市西城区西直门外大街1号', '冯丽', '010-66002002',
     116.3558, 39.9418, time(9, 0), time(17, 0)),
    ('WD003', '中关村支行', '中关村', 'branch',
     '北京市海淀区中关村大街15号', '蒋帆', '010-66002003',
     116.3168, 39.9836, time(9, 0), time(17, 0)),
    ('WD004', '学院路支行', '学院路', 'branch',
     '北京市海淀区学院路30号', '沈悦', '010-66002004',
     116.3547, 39.9918, time(9, 0), time(17, 0)),
    ('ZZ001', '国贸支行', '国贸', 'branch',
     '北京市朝阳区建国门外大街1号', '韩雪', '010-66003001',
     116.4588, 39.9085, time(9, 0), time(17, 0)),
    ('ZZ002', '望京支行', '望京', 'branch',
     '北京市朝阳区望京街8号', '杨万里', '010-66003002',
     116.4725, 39.9655, time(9, 0), time(17, 0)),
    ('ZZ003', '三里屯自助银行', '三里屯ATM', 'self_bank',
     '北京市朝阳区三里屯路19号', '自动值守', '010-66003003',
     116.4537, 39.9370, time(0, 0), time(23, 59)),
    ('ZZ004', '亚运村支行', '亚运村', 'branch',
     '北京市朝阳区北辰东路8号', '朱琳', '010-66003004',
     116.3980, 39.9906, time(9, 0), time(17, 0)),
]

# ---------- 车辆 ----------
VEHICLES = [
    # 车牌, 车型, 容量, GPS, 状态, 驻停金库code
    ('京A·Y8001', '防弹运钞车(江铃)', 48, 'GPS-8001', 'idle', 'JK001'),
    ('京A·Y8002', '防弹运钞车(依维柯)', 56, 'GPS-8002', 'idle', 'JK001'),
    ('京A·Y8003', '防弹运钞车(江铃)', 48, 'GPS-8003', 'idle', 'JK001'),
    ('京A·Y8004', '防弹运钞车(全顺)', 60, 'GPS-8004', 'idle', 'JK002'),
    ('京A·Y8005', '防弹运钞车(全顺)', 60, 'GPS-8005', 'maintenance', 'JK002'),
]

# ---------- 人员（username=工号） ----------
# 工号, 姓名, 角色, 岗位, 电话, 所属网点code
STAFF = [
    ('1001', '张建国', 'dispatcher', 'dispatcher', '13800001001', 'JK001'),
    ('1002', '李调度', 'dispatcher', 'dispatcher', '13800001002', 'JK002'),
    ('2001', '王海涛', 'guard', 'car_captain', '13800002001', 'JK001'),
    ('2002', '刘志强', 'guard', 'escort_guard', '13800002002', 'JK001'),
    ('2003', '陈建军', 'guard', 'escort_guard', '13800002003', 'JK001'),
    ('2004', '赵磊', 'guard', 'car_captain', '13800002004', 'JK002'),
    ('2005', '孙鹏', 'guard', 'escort_guard', '13800002005', 'JK002'),
    ('2006', '周勇', 'guard', 'escort_guard', '13800002006', 'JK002'),
    ('2007', '徐刚', 'guard', 'car_captain', '13800002007', 'JK001'),
    ('2008', '马骏', 'guard', 'escort_guard', '13800002008', 'JK002'),
    ('3001', '吴铁军', 'driver', 'driver', '13800003001', 'JK001'),
    ('3002', '郑凯', 'driver', 'driver', '13800003002', 'JK001'),
    ('3003', '钱进宝', 'driver', 'driver', '13800003003', 'JK001'),
    ('3004', '冯远征', 'driver', 'driver', '13800003004', 'JK002'),
    ('3005', '卫国民', 'driver', 'driver', '13800003005', 'JK002'),
    ('4001', '周金库', 'vault_keeper', 'vault_keeper', '13800004001', 'JK001'),
    ('4002', '吴库管', 'vault_keeper', 'vault_keeper', '13800004002', 'JK002'),
    ('5001', '郑晓敏', 'branch_clerk', 'clerk', '13900005001', 'WD001'),
    ('5002', '冯丽', 'branch_clerk', 'clerk', '13900005002', 'WD002'),
    ('5003', '蒋帆', 'branch_clerk', 'clerk', '13900005003', 'WD003'),
    ('5004', '沈悦', 'branch_clerk', 'clerk', '13900005004', 'WD004'),
    ('5005', '韩雪', 'branch_clerk', 'clerk', '13900005005', 'ZZ001'),
    ('5006', '杨万里', 'branch_clerk', 'clerk', '13900005006', 'ZZ002'),
    ('5007', '朱琳', 'branch_clerk', 'clerk', '13900005007', 'ZZ004'),
    ('5008', '马晓康', 'branch_clerk', 'clerk', '13900005008', 'ZZ003'),
]

# ---------- 款箱 ----------
# 编号, 箱型, 归属网点code, 金额
BOXES = [
    ('KX-JRJ-01', 'teller', 'WD001', 280000),
    ('KX-JRJ-02', 'teller', 'WD001', 150000),
    ('KX-XZM-01', 'teller', 'WD002', 180000),
    ('KX-XZM-02', 'cash', 'WD002', 320000),
    ('KX-ZGC-01', 'teller', 'WD003', 260000),
    ('KX-ZGC-02', 'teller', 'WD003', 140000),
    ('KX-XYL-01', 'cash', 'WD004', 220000),
    ('KX-XYL-02', 'teller', 'WD004', 120000),
    ('KX-GM-01', 'teller', 'ZZ001', 350000),
    ('KX-GM-02', 'voucher', 'ZZ001', 0),
    ('KX-WJ-01', 'teller', 'ZZ002', 190000),
    ('KX-SLT-ATM1', 'atm', 'ZZ003', 400000),
    ('KX-SLT-ATM2', 'atm', 'ZZ003', 400000),
    ('KX-YYC-01', 'teller', 'ZZ004', 170000),
    ('KX-YYC-02', 'cash', 'ZZ004', 240000),
]

# ---------- 线路：编号, 名称, 金库, 里程, 分钟, [(网点code, 计划到达, 停留)] ----------
ROUTES = [
    ('L01', '城西线（金融街-西直门-学院路）', 'JK001', 38.5, 150, [
        ('WD001', time(8, 20), 20),
        ('WD002', time(8, 55), 15),
        ('WD004', time(9, 30), 15),
    ]),
    ('L02', '海淀线（中关村-学院路）', 'JK001', 52.0, 180, [
        ('WD003', time(8, 30), 20),
        ('WD004', time(9, 20), 15),
    ]),
    ('L03', '朝阳环线（国贸-三里屯-望京）', 'JK002', 46.0, 170, [
        ('ZZ001', time(8, 25), 20),
        ('ZZ003', time(9, 0), 25),
        ('ZZ002', time(9, 40), 15),
    ]),
    ('L04', '亚运村线', 'JK002', 30.0, 120, [
        ('ZZ004', time(8, 30), 20),
    ]),
]


class Command(BaseCommand):
    help = '初始化内置样例数据并生成演示任务'

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true',
                            help='清空全部业务数据后重建')

    def handle(self, *args, **opts):
        if opts['reset']:
            self.stdout.write('清空旧数据...')
            for model in (Task, TaskStop, TaskAssignee, TaskBox,
                          CashBox, RouteStop, Route, Vehicle, Branch):
                model.objects.all().delete()
            User.objects.exclude(is_superuser=True).delete()

        branches = self._seed_branches()
        self._seed_vehicles(branches)
        users = self._seed_staff(branches)
        boxes = self._seed_boxes(branches)
        routes = self._seed_routes(branches)
        self._seed_admin(users)
        self._seed_resource_status(branches, users)
        self._seed_tasks(routes, boxes, users)

        self.stdout.write(self.style.SUCCESS('\n样例数据初始化完成！'))
        self.stdout.write('登录账号（密码均为 %s）：' % PASSWORD)
        self.stdout.write('  调度员 1001 / 金库 4001 / 车长 2001 / 驾驶员 3001 / admin')

    # ---------- 基础档案 ----------
    def _seed_branches(self):
        m = {}
        for (code, name, short, btype, addr, person, phone,
             lng, lat, st, en) in BRANCHES:
            obj, _ = Branch.objects.get_or_create(
                code=code,
                defaults=dict(name=name, short_name=short, branch_type=btype,
                              address=addr, contact_person=person,
                              contact_phone=phone, lng=lng, lat=lat,
                              service_start=st, service_end=en))
            m[code] = obj
        self.stdout.write(f'网点/金库 {len(m)} 个')
        return m

    def _seed_vehicles(self, branches):
        for plate, model, cap, gps, status, depot_code in VEHICLES:
            Vehicle.objects.get_or_create(
                plate=plate,
                defaults=dict(model=model, capacity=cap, gps_device=gps,
                              status=status, home_branch=branches[depot_code]))

    def _seed_staff(self, branches):
        m = {}
        for emp, name, role, position, phone, bcode in STAFF:
            user, created = User.objects.get_or_create(
                username=emp,
                defaults=dict(employee_no=emp, name=name, role=role,
                              position=position, phone=phone,
                              branch=branches.get(bcode),
                              active_duty=True, is_staff=True,
                              password=make_password(PASSWORD)))
            m[emp] = user
        self.stdout.write(f'人员 {len(m)} 名')
        return m

    def _seed_boxes(self, branches):
        m = {}
        for no, btype, bcode, amount in BOXES:
            obj, _ = CashBox.objects.get_or_create(
                box_no=no,
                defaults=dict(box_type=btype, owner_branch=branches[bcode],
                              cash_amount=amount, status=CashBox.Status.IDLE))
            m[no] = obj
        return m

    def _seed_routes(self, branches):
        m = {}
        for code, name, depot, km, minutes, stops in ROUTES:
            route, created = Route.objects.get_or_create(
                code=code,
                defaults=dict(name=name, depot=branches[depot],
                              distance_km=km, est_minutes=minutes))
            if created:
                for i, (bcode, arr, dwell) in enumerate(stops, start=1):
                    RouteStop.objects.create(
                        route=route, sequence=i, branch=branches[bcode],
                        planned_arrival=arr, dwell_minutes=dwell)
            m[code] = route
        return m

    def _seed_admin(self, users):
        admin = User.objects.filter(username='admin').first()
        if not admin:
            User.objects.create_superuser(
                'admin', password=PASSWORD,
                employee_no='9001', name='管理员',
                role=Role.ADMIN, position='', phone='13800009001')

    def _seed_resource_status(self, branches, users):
        """维修车与培训押运员的初始状态及历史留痕（仅全新数据时）。"""
        from core.models import PersonnelStatusLog, Vehicle, VehicleStatusLog

        repair_car = Vehicle.objects.filter(plate='京A·Y8005').first()
        admin = users['1001']
        if repair_car and not repair_car.status_logs.exists():
            VehicleStatusLog.objects.create(
                vehicle=repair_car, from_status='idle', to_status='maintenance',
                reason='例行防弹钢板检修 + GPS 模块更换，预计两日',
                operator=admin)

        trainee = users.get('2006')
        if trainee and not trainee.duty_logs.exists():
            trainee.active_duty = False
            trainee.leave_type = 'training'
            trainee.save(update_fields=['active_duty', 'leave_type'])
            PersonnelStatusLog.objects.create(
                user=trainee, active_duty=False, leave_type='training',
                reason='参加省保安公司武装押运员年度复训（两天）',
                operator=admin)

    # ---------- 演示任务 ----------
    def _seed_tasks(self, routes, boxes, users):
        # 每次重建任务，保证状态可演示
        Task.objects.all().delete()
        today = timezone.localdate()

        dispatcher = users['1001']

        # 1) 已完成的下解任务：L01 全城西线
        t1 = TaskService.create_task({
            'direction': 'outbound', 'route_id': routes['L01'].id,
            'vehicle_id': Vehicle.objects.get(plate='京A·Y8001').id,
            'planned_date': today - timedelta(days=1),
            'planned_depart': time(8, 0), 'planned_return': time(11, 0),
            'name': '城西线下解款任务', 'notes': '工作日例行下解',
            'assignees': [
                {'user_id': users['2001'].id, 'role_on_task': 'car_captain'},
                {'user_id': users['2002'].id, 'role_on_task': 'guard'},
                {'user_id': users['3001'].id, 'role_on_task': 'driver'}],
            'boxes': [
                {'box_id': boxes['KX-JRJ-01'].id, 'target_stop_sequence': 1},
                {'box_id': boxes['KX-JRJ-02'].id, 'target_stop_sequence': 1},
                {'box_id': boxes['KX-XZM-01'].id, 'target_stop_sequence': 2},
                {'box_id': boxes['KX-XZM-02'].id, 'target_stop_sequence': 2},
                {'box_id': boxes['KX-XYL-01'].id, 'target_stop_sequence': 3}],
        }, dispatcher)
        self._run_outbound(t1, boxes, {
            'KX-JRJ-01': ('FJ0001', users['4001'], users['5001']),
            'KX-JRJ-02': ('FJ0002', users['4001'], users['5001']),
            'KX-XZM-01': ('FJ0003', users['4001'], users['5002']),
            'KX-XZM-02': ('FJ0004', users['4001'], users['5002']),
            'KX-XYL-01': ('FJ0005', users['4001'], users['5004']),
        })

        # 2) 进行中的下解任务：L02，已到中关村站
        # KX-XYL-01 在昨日任务完成后已回库空闲，可复用
        t2 = TaskService.create_task({
            'direction': 'outbound', 'route_id': routes['L02'].id,
            'vehicle_id': Vehicle.objects.get(plate='京A·Y8002').id,
            'planned_date': today,
            'planned_depart': time(8, 0), 'planned_return': time(11, 30),
            'name': '海淀线下解款任务', 'notes': '',
            'assignees': [
                {'user_id': users['2003'].id, 'role_on_task': 'car_captain'},
                {'user_id': users['2005'].id, 'role_on_task': 'guard'},
                {'user_id': users['3002'].id, 'role_on_task': 'driver'}],
            'boxes': [
                {'box_id': boxes['KX-ZGC-01'].id, 'target_stop_sequence': 1},
                {'box_id': boxes['KX-ZGC-02'].id, 'target_stop_sequence': 1},
                {'box_id': boxes['KX-XYL-02'].id, 'target_stop_sequence': 2},
            ],
        }, dispatcher)
        self._run_partial_outbound(t2, boxes, users)

        # 3) 异常挂起任务：L03，国贸站验证码不符
        t3 = TaskService.create_task({
            'direction': 'outbound', 'route_id': routes['L03'].id,
            'vehicle_id': Vehicle.objects.get(plate='京A·Y8004').id,
            'planned_date': today,
            'planned_depart': time(8, 0), 'planned_return': time(12, 0),
            'name': '朝阳环线加钞下解任务', 'notes': '含ATM加钞箱',
            'assignees': [
                {'user_id': users['2004'].id, 'role_on_task': 'car_captain'},
                {'user_id': users['2001'].id, 'role_on_task': 'guard'},
                {'user_id': users['3004'].id, 'role_on_task': 'driver'}],
            'boxes': [
                {'box_id': boxes['KX-GM-01'].id, 'target_stop_sequence': 1},
                {'box_id': boxes['KX-GM-02'].id, 'target_stop_sequence': 1},
                {'box_id': boxes['KX-SLT-ATM1'].id, 'target_stop_sequence': 2},
                {'box_id': boxes['KX-SLT-ATM2'].id, 'target_stop_sequence': 2},
                {'box_id': boxes['KX-WJ-01'].id, 'target_stop_sequence': 3}],
        }, dispatcher)
        self._run_abnormal(t3, boxes, users)

        # 4) 已派车待出发的上收任务：回收昨日下解、现停留在城西各网点的款箱
        t4 = TaskService.create_task({
            'direction': 'inbound', 'route_id': routes['L01'].id,
            'vehicle_id': Vehicle.objects.get(plate='京A·Y8003').id,
            'planned_date': today,
            'planned_depart': time(13, 30), 'planned_return': time(16, 30),
            'name': '城西线尾箱上收任务', 'notes': '下午回收昨日下解款箱',
            'assignees': [
                {'user_id': users['2002'].id, 'role_on_task': 'car_captain'},
                {'user_id': users['2007'].id, 'role_on_task': 'guard'},
                {'user_id': users['3003'].id, 'role_on_task': 'driver'}],
            'boxes': [
                {'box_id': boxes['KX-JRJ-01'].id, 'target_stop_sequence': 1},
                {'box_id': boxes['KX-JRJ-02'].id, 'target_stop_sequence': 1},
                {'box_id': boxes['KX-XZM-01'].id, 'target_stop_sequence': 2},
                {'box_id': boxes['KX-XZM-02'].id, 'target_stop_sequence': 2},
                {'box_id': boxes['KX-XYL-01'].id, 'target_stop_sequence': 3}],
        }, dispatcher)

        self.stdout.write(
            f'演示任务：{t1.task_no}(已完成)、{t2.task_no}(押运中)、'
            f'{t3.task_no}(异常挂起)、{t4.task_no}(已派车)')

    # ---------- 任务流转脚本 ----------
    def _out_all(self, task, box_map, seal_map, users):
        """全部款箱出库。box_map: box_no->box"""
        for no, box in box_map.items():
            seal = seal_map[no]
            tb = task.taskbox_set.get(box=box)
            TaskService.handover(task, {
                'task_box_id': tb.id, 'phase': 'vault_out',
                'seal_no_in': seal,
                'from_user_id': users['4001'].id,
                'to_user_id': task.taskassignee_set.get(
                    role_on_task='car_captain').user_id,
            }, users['4001'])

    def _run_outbound(self, task, boxes, plan):
        """完整跑完一个下解任务。plan: box_no -> (seal, vault_user, clerk_user)"""
        seal_map = {no: seal for no, (seal, _, _) in plan.items()}
        self._out_all(task, {no: boxes[no] for no in plan}, seal_map,
                      {u.employee_no: u for u in User.objects.all()})
        TaskService.depart(task, plan[list(plan)[0]][1])
        captain = task.taskassignee_set.get(role_on_task='car_captain').user
        for stop in task.stops.order_by('sequence'):
            TaskService.arrive_stop(task, stop.id, captain)
            for no, (seal, vault_user, clerk) in plan.items():
                tb = task.taskbox_set.filter(
                    box=boxes[no], target_stop=stop).first()
                if not tb:
                    continue
                TaskService.handover(task, {
                    'task_box_id': tb.id, 'phase': 'branch_recv',
                    'stop_id': stop.id,
                    'seal_no_in': seal, 'code': stop.verify_code,
                    'seal_intact': True,
                    'from_user_id': captain.id,
                    'to_user_id': clerk.id,
                }, captain)

    def _run_partial_outbound(self, task, boxes, users):
        """出库 + 出发 + 到达中关村，完成第一只款箱交接，第二只待核对。"""
        seal_map = {'KX-ZGC-01': 'FJ1001', 'KX-ZGC-02': 'FJ1002',
                    'KX-XYL-02': 'FJ1003'}
        self._out_all(task,
                      {k: boxes[k] for k in seal_map}, seal_map, users)
        TaskService.depart(task, users['4001'])
        captain = task.taskassignee_set.get(role_on_task='car_captain').user
        stop1 = task.stops.get(sequence=1)
        TaskService.arrive_stop(task, stop1.id, captain)
        tb = task.taskbox_set.get(box=boxes['KX-ZGC-01'])
        TaskService.handover(task, {
            'task_box_id': tb.id, 'phase': 'branch_recv',
            'stop_id': stop1.id,
            'seal_no_in': 'FJ1001', 'code': stop1.verify_code,
            'from_user_id': captain.id, 'to_user_id': users['5003'].id,
        }, captain)

    def _run_abnormal(self, task, boxes, users):
        """出库 + 出发 + 到国贸，第一只款箱验证码录入错误，触发异常挂起。"""
        seal_map = {'KX-GM-01': 'FJ2001', 'KX-GM-02': 'FJ2002',
                    'KX-SLT-ATM1': 'FJ2003', 'KX-SLT-ATM2': 'FJ2004',
                    'KX-WJ-01': 'FJ2005'}
        self._out_all(task,
                      {k: boxes[k] for k in seal_map}, seal_map, users)
        TaskService.depart(task, users['4002'])
        captain = task.taskassignee_set.get(role_on_task='car_captain').user
        stop1 = task.stops.get(sequence=1)
        TaskService.arrive_stop(task, stop1.id, captain)
        tb = task.taskbox_set.get(box=boxes['KX-GM-01'])
        # 故意录错验证码 → CODE_MISMATCH，任务挂起
        wrong = '0000' if stop1.verify_code != '0000' else '1111'
        TaskService.handover(task, {
            'task_box_id': tb.id, 'phase': 'branch_recv',
            'stop_id': stop1.id,
            'seal_no_in': 'FJ2001', 'code': wrong,
            'from_user_id': captain.id, 'to_user_id': users['5005'].id,
            'remark': '网点录入交接码不匹配，暂停交接',
        }, captain)
