import socket
import time
import json
from threading import Thread
import psutil
import ipaddress
import common.globals
from common.ToolsKit import ToolsKit
from common.dockerApi import dockerApi
import os
from common.logger import logger
from  apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
import platform
from common.mytRomHandle import mytRomHandle

class MytBackTask(object):    

    def __init__(self) -> None:
        pass
    def init(self, host_ip , useCache = False, udp_port = None) -> None:
        self.useCache = useCache
        tools = ToolsKit()
        root_path = tools.GetRootPath()
        self.cfg_cache = root_path + "/conf/cache.json"
        self.token_cache = root_path + "/conf/token.json"
        #logger.debug("CachePath:" + str(self.cfg_cache))
        self.str_cache_json = ''
        if os.path.exists(self.cfg_cache):
            os.remove(self.cfg_cache)
        if os.path.exists(self.token_cache):
            os.remove(self.token_cache)
        self.host_ip = host_ip
        if udp_port is None:
            self.udp_port = 7600
        else:
            self.udp_port = int(udp_port)

        #申明一个调度器对象
        # 配置 SQLAlchemyJobStore
        root_path =  root_path + "/backup/"
        if not os.path.exists(root_path):
            os.makedirs(root_path)
        conf_path = os.path.join(root_path, "conf")
        if not os.path.exists(conf_path):
            os.makedirs(conf_path)
        sql_file_path = os.path.join(root_path, "conf", "scheduled_jobs.sqlite")
        jobstores = {
            'default': SQLAlchemyJobStore(
                url=f"sqlite:///{sql_file_path}",
                tablename='scheduled_jobs'
            )
        }
        self.scheduler = BackgroundScheduler(jobstores = jobstores)
        
        
    #开启线程
    def run(self):
        #self.flask = flask_app
        self.dict = {}
        self.dict_alive = {}        #记录设备的最后活跃时间
        background_thread = Thread(target=self.main)
        background_thread.start()

    # def run_subprocess(self):
    #     common.globals.global_bk_RunFlag = True
    #     p = Process(target=self.main)
    #     p.start()

    #获取本地IP
    def get_local_ip(self):
        gateway_ip = None
        if self.host_ip != '0.0.0.0':
            gateway_ip =  self.host_ip
        else:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(('223.5.5.5', 80))
                gateway_ip = s.getsockname()[0]
        return gateway_ip
    
    #获取广播地址
    def get_broadAddr(self):
        stats_list = psutil.net_if_stats()
        local_ip = self.get_local_ip()
        broadAddr = None
        netmask = None
        if len(local_ip)>0:
            for name, addrs in psutil.net_if_addrs().items(): 
                if name in stats_list :
                    if stats_list[name].isup == True:
                        for addr in addrs:
                            if (addr.family == 2) and (addr.address == local_ip):
                                netmask = addr.netmask
        #计算广播地址
        if len(local_ip)>0 and len(netmask)>0:
            net = ipaddress.IPv4Network(local_ip + '/' + netmask, False)
            broadAddr = net.broadcast_address.compressed
        return broadAddr 
    
                

    def deal_msg(self, msg,addr, sk):
        astr = msg.decode('utf-8')
        #logger.debug('来自[%s:%s]的消息: %s' % (addr[0], addr[1], msg))
        if astr != 'lgcloud':
            if addr[0]  not in self.dict:
                words = astr.split(':')
                if len(words)>1:
                    self.dict[addr[0]] = words[1]
                    self.dict_alive[addr[0]] = time.time()
                    s = json.dumps(self.dict)
                    common.globals.global_Flask_dev_list = s
                    if self.useCache:
                        if s == self.str_cache_json:
                            pass
                        else:
                            self.str_cache_json = s
                            with open(self.cfg_cache, 'w') as f:
                                f.write(s)
                            
                    #self.flask.config['dev_list'] = s
            else:
                self.dict_alive[addr[0]] = time.time()  #更新时间

            if os.path.exists(self.token_cache):
                u_token = None
                with open(self.token_cache, 'r') as f:
                    u_str = f.read()
                    #u_token = f.read()
                data_json = json.loads(u_str)
                u_token = data_json['token']
                d_time = data_json['time']
                if d_time< time.time():
                    os.remove(self.token_cache)
                    u_token = None
                if u_token != None:
                    n_msg = f"lgtoken:{u_token}"
                    sk.sendto(n_msg.encode(), addr)
                    #logger.debug("发送token:" + n_msg)

    #定时重启主机任务
    @staticmethod
    def scheduler_reboot_job():
        now = time.time()
        print(f"scheduler_job {now}")
        logger.debug(f"执行定时 scheduler_reboot_job {now}")
        MytBackTask.reboot_host()
    
    
    #仅仅对当前的ARM 主机有效
    @staticmethod
    def reboot_host( ip = "172.17.0.1"):
        if platform.machine() == 'aarch64':         #只有arm板才有该接口
            api = dockerApi(ip)
            cmd = 'echo "b" > /proc/sysrq-trigger'
            api.SDK_SHELL_COMMAD_HOST(cmd, True)            #防止重启后容器不删除 设置为自动销毁
            logger.debug(f"执行重启主机命令")
        else:
            print("Only support ARM platform!")

    #添加定时任务
    # :param int|str year: 4-digit year
    # :param int|str month: month (1-12)
    # :param int|str day: day of month (1-31)
    # :param int|str day_of_week: number or name of weekday (0-6 or mon,tue,wed,thu,fri,sat,sun)
    # :param int|str hour: hour (0-23)
    # :param int|str minute: minute (0-59)
    # :param int|str second: second (0-59)
    def add_scheduler_job(self, job_id, year = None, month = None, day = None,  day_of_week = None, hour = None, minute = None, second = None):
        #jobstores = {'default': SQLAlchemyJobStore(url='sqlite:///scheduler.sqlite')}
        intervalTrigger = CronTrigger(year=year, month=month, day=day, day_of_week=day_of_week, hour=hour, minute=minute, second=second)
        self.scheduler.add_job(MytBackTask.scheduler_reboot_job, intervalTrigger, id=job_id, jobstore='default')
    
    #序列化定时任务
    def serlize_cron2json(self, trigger):
        ret = {}
        for f in trigger.fields:
            #print(f.name)
            #print(f.__str__())
            ret[f.name] = f.__str__()
        return ret
            
    #查询当前的定时任务列表
    def get_scheduler_job(self):
        #print(self.scheduler.print_jobs())
        ret = []
        for j in self.scheduler.get_jobs():
            c = {}
            # print(j.id)
            # print(j.next_run_time)
            # print(j.trigger)
            #print(j.trigger.fields)
            c['id'] = j.id
            c['next_run_time'] = str(j.next_run_time)
            #c['cron'] = j.trigger.__str__()
            c['cron'] = self.serlize_cron2json(j.trigger)
            ret.append(c)
        return ret
            
    def remove_scheduler_job(self, job_id):
        self.scheduler.remove_job(job_id)
        #print(self.scheduler.get_jobs())  

    #主循环
    def main(self):
        
        #执行更新ROM操作
        if platform.machine() == 'aarch64':         #只有arm板才有执行该操作
            romHandle =  mytRomHandle()
            romHandle.updateQ1Rom()

        #开启调度任务
        self.scheduler.start()


        #获取本地IP
        local_addr = self.get_local_ip()
        if local_addr is not None:
            #self.flask.config['local_addr'] = local_addr
            if common.globals.global_sdk_mode is None:
                common.globals.global_Flask_local_addr = local_addr

        #获取当前的广播地址
        broad_addr = self.get_broadAddr()
        if broad_addr is None:
            print("广播地址获取失败!")
        #else:
            #print("广播地址:" + broad_adq  dr)
        # 创建 socket
        sk = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        #设置为广播模式
        sk.setsockopt(socket.SOL_SOCKET,socket.SO_BROADCAST,1)
        #设置接收数据超时1秒
        sk.settimeout(1)
        # 绑定 IP 和端口号
        sk.bind(('0.0.0.0', self.udp_port))
        msg = "lgcloud"
        sk.sendto(msg.encode(),(broad_addr,7678))
        last = time.time()

        while True:
            # 接收数据
            while True:
                try:
                    msg, addr = sk.recvfrom(1024)
                    self.deal_msg(msg, addr, sk)
                    # 打印
                    #print('来自[%s:%s]的消息: %s' % (addr[0], addr[1], msg))
                except Exception as e:
                    #print("Exception Error:" + str(e))
                    break
        
            #将数据原路发回
            #sk.sendto(msg, addr)
            time.sleep(1)

            if time.time()-last>30 :
                now = time.time()
                tmp_dict = {}
                for k in self.dict_alive:
                    if now - self.dict_alive[k] < 30:
                        tmp_dict[k] = now
                    else:
                        self.dict.pop(k)  
                        s = now - self.dict_alive[k]
                        #print("pop  " + k + "  lf:" + str(s) )
                self.dict_alive = tmp_dict
                last = time.time()
                msg = "lgcloud"
                sk.sendto(msg.encode(),(broad_addr,7678))
        print(f"backTask thread 退出")
        # 关闭 socket
        sk.close()
