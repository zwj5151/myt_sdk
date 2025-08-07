from common.logger import logger
from common.dockerApi import dockerApi
import subprocess
import socket
import os
import json
from threading import Thread
import threading
from common.ToolsKit import ToolsKit
from common.mytApi import MytOS_API
import time
import sys
import shlex
import sqlite3
import ipaddress

#TODO:  
#监听所有的容器开启和关闭状态 用于添加iptables 的规则

#基于mytos 和docker 封装的vpc 网络操作接口
#提供VPC对象的基础操作
class evnetsListen(object):
    def __init__(self):
        if sys.platform == "linux":
            self.docker_host_ip = '172.17.0.1'           
        else:
            self.docker_host_ip = '192.168.86.176'      #windows only test 
        self.gateway_ip = None
        self.lock = threading.Lock()
        self.local_port_arr = {}
        self.port_status = {}
        self.port_ip_arr = {}
        #默认使用的端口范围 20000-20050 
        for i in range(20000, 200050):
            self.port_status[i] = False
            self.local_port_arr[i] = ''
            self.port_ip_arr[i]  = ''

    #获取主机IP
    def Host_Ip(self):
        return self.docker_host_ip

    def add_port(self, port:int, name:str, ip:str) -> bool:
        ret = False
        if self.port_status[port] == False:
            self.local_port_arr[port] = name
            self.port_status[port] = True
            self.port_ip_arr[port] = ip
        return ret
    
    def remove_port(self, name:str) -> bool:
        ret = False
        for i in range(20000, 200050):
            if self.local_port_arr[i] == name:
                ip = self.port_ip_arr[i]
                self.local_port_arr[i] = ''
                self.port_ip_arr[i] = ''
                self.port_status[i] = False
                ret = {'port':i, 'ip':ip}
                break
        return ret

    def get_idx_port_status(self, idx:int) -> bool:
        """
        获取端口状态
        :param port: 端口号
        :return: 端口状态（True：占用 False：空闲）
        """
        port = idx - 1  + 20000
        return self.port_status[port]

    def get_free_port(self) -> int:
        """
        获取一个空闲的端口号
        :return: 空闲端口号
        """
        for port in range(20000, 200050):
            if not self.port_status[port]:
                return port
        return -1


    #clear iptables
    def clear_iptables(self) -> bool:
        try:
            # 添加 PREROUTING 规则（外部访问本机端口时转发到目标）
            cmd_prerouting = (
                f"iptables -t nat -F "
            )
            subprocess.run(shlex.split(cmd_prerouting), check=True)
            #清理端口数据
            self.local_port_arr = {}
            self.port_status = {}
            self.port_ip_arr = {}
            #默认使用的端口范围 20000-20050 
            for i in range(20000, 200050):
                self.port_status[i] = False
                self.local_port_arr[i] = ''
                self.port_ip_arr[i]  = ''
                
            logger.debug(f"执行 iptables -t nat -F  ")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"添加规则失败: {e}")
        except Exception as e:
            logger.error("Exception Error:" + str(e))
            return False
    #type: tcp/udp
    def add_port_forward(self, target_ip: str, target_port: int, local_port: int, type: str) -> bool:
        """
        添加端口转发规则
        :param target_ip: 目标IP地址（如 "192.168.1.100"）
        :param target_port: 目标端口（如 8080）
        :param local_port: 本机监听的端口（如 80）
        :return: 是否执行成功
        """
        try:
            # 添加 PREROUTING 规则（外部访问本机端口时转发到目标）
            cmd_prerouting = (
                f"iptables -t nat -A PREROUTING "
                f"-p {type} --dport {target_port} "
                f"-j DNAT --to-destination {target_ip}:{local_port}"
            )
            subprocess.run(shlex.split(cmd_prerouting), check=True)

            # 添加 POSTROUTING 规则（MASQUERADE 确保返回流量正确路由）
            cmd_postrouting = (
                f"iptables -t nat -A POSTROUTING "
                f"-p {type} -d {target_ip} --dport {local_port} "
                f"-j MASQUERADE"
            )
            subprocess.run(shlex.split(cmd_postrouting), check=True)
            #logger.debug(f"执行 iptables -t nat -A PREROUTING 规则: {cmd_prerouting}")
            return True
        except subprocess.CalledProcessError as e:
            print(f"添加规则失败: {e}")
        except Exception as e:
            print("Exception Error:" + str(e))
            return False

    def delete_port_forward(self, target_ip: str, target_port: int, local_port: int, type: str) -> bool:
        """
        删除端口转发规则
        :param target_ip: 目标IP地址（需与添加时一致）
        :param target_port: 目标端口（需与添加时一致）
        :param local_port: 本机监听的端口（需与添加时一致）
        :return: 是否执行成功
        """
        try:
            # 删除 PREROUTING 规则
            cmd_prerouting = (
                f"iptables -t nat -D PREROUTING "
                f"-p {type} --dport {target_port} "
                f"-j DNAT --to-destination {target_ip}:{local_port}"
            )
            subprocess.run(shlex.split(cmd_prerouting), check=True)

            # 删除 POSTROUTING 规则
            cmd_postrouting = (
                f"iptables -t nat -D POSTROUTING "
                f"-p {type} -d {target_ip} --dport {local_port} "
                f"-j MASQUERADE"
            )
            subprocess.run(shlex.split(cmd_postrouting), check=True)
            #logger.debug(f"执行 iptables -t nat -D PREROUTING 规则: {cmd_prerouting}")
            return True
        except subprocess.CalledProcessError as e:
            print(f"删除规则失败: {e}")
        except Exception as e:
            print("Exception Error:" + str(e))
            return False

    #启动容器的时候 扫描当前开启的容器端口
    def scan_docker_port(self):
        try:
            docker_api =  dockerApi(self.docker_host_ip)
            r = docker_api.SDK_contianer_list(True)
            if r != False:
                while len(r)>0:
                    c = r.pop()
                    if c == None:
                        break
                    else:
                        name = c.attrs['Names'][0]
                        cfg = docker_api.SDK_get_container_config_detail(name)
                        if 'idx' in c.attrs['Labels'] and c.attrs['State'] == 'running':
                            #显示ip
                            idx = int(c.attrs['Labels']['idx'])
                            if cfg['network'] != 'myt':      
                                local_ip = cfg['local_ip']
                                port = idx -1 + 20000
                                dc_id = cfg['id']
                                if self.get_idx_port_status(idx) == False:
                                    #增加端口映射功能 
                                    if (self.add_port_forward(local_ip, port, 10008, 'tcp') == True) and \
                                        (self.add_port_forward(local_ip, port, 10008, 'udp') == True):
                                        #添加端口映射成功
                                        self.add_port(port, dc_id, local_ip)
                                        logger.error(f"添加端口映射成功, local_ip:{local_ip}, port:{port}, dc_id:{dc_id}")
                                    else:
                                        logger.error(f"添加端口映射失败, local_ip:{local_ip}, port:{port}, dc_id:{dc_id}")
                    
                                else:
                                    logger.error(f"端口已经被占用, local_ip:{local_ip}, port:{port}, dc_id:{dc_id}")
        except Exception as e:
            logger.debug("Exception Error:" + str(e))
    #获取当前运行的主机ip 和容器列表  
    def check_network_env(self):
        try:
            #ip_arr = {}
            bNeedReset = False
            dc_api =  dockerApi(self.docker_host_ip)
            dc_bridge = dc_api.SDK_get_network_info("bridge")
            for dc_id in dc_bridge['Containers']:
                attr = dc_api.SDK_get_contianer_attr(dc_id)
                bIsAndroid = False  
                if 'Config' in attr:
                    if 'Labels' in attr['Config']:
                        if 'idx' in attr['Config']['Labels']:
                            idx = int(attr['Config']['Labels']['idx'])
                            bIsAndroid = True
                if bIsAndroid == True:
                    print(dc_bridge['Containers'][dc_id]['IPv4Address'])
                    cidr = dc_bridge['Containers'][dc_id]['IPv4Address']
                    interface = ipaddress.ip_interface(cidr)
                    print(interface.ip)
                    ip_addr = str(interface.ip)
                    #ip_arr[idx] = str(interface.ip)
                    #ip_arr[dc_id] = str(interface.ip)
                    port = idx -1 + 20000
                    if (self.port_status[port] == True) and (self.port_ip_arr[port] == ip_addr) and (self.local_port_arr[port] == dc_id):
                        #正确
                        pass
                    else:
                        # if (self.port_status[port] != True):
                        #     print(self.port_status[port])
                        # if (str(self.port_ip_arr[port]) != ip_addr) :
                        #     print(str(self.port_ip_arr[port]))
                        #     #print(self.port_ip_arr)
                        #     print(str(ip_addr))
                        # if (self.local_port_arr[port] != dc_id):
                        #     print(self.local_port_arr[port])

                        logger.error(f"端口映射错误, idx:{idx}, port:{port}, ip:{ip_addr}, dc_id:{dc_id}")
                        bNeedReset = True
                        break
            #处理修复
            if bNeedReset == True:
                self.clear_iptables()
                self.scan_docker_port()
        except Exception as e:
            logger.debug("Exception Error:" + str(e))
    #开启后台线程
    def run_thread(self):
        #启动的时候扫描当前运行容器
        self.scan_docker_port()
        background_thread = Thread(target=self.start_listen_events,  kwargs={"ip":self.docker_host_ip} )
        background_thread.start()

    def restore_android_vpc_rules(self, docker_api, container_name):
        """
        恢复安卓容器的 VPC 规则
        """
        try:
            # logger.debug(f"开始恢复安卓容器 {container_name} 的 VPC 规则")
            # time.sleep(30)
            tools = ToolsKit()
            root_path = tools.GetRootPath()
            DB_PATH = root_path + "/backup/vpc_config.db"
            
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()

            # 查询安卓容器对应的 VPC 配置和 IP
            cursor.execute("""
                SELECT vpc_config.tun, vpc_config.address, vpc_config.user, vpc_config.password, android_vpc_config.android_ip
                FROM android_vpc_config
                JOIN vpc_config ON android_vpc_config.vpc_id = vpc_config.id
                WHERE android_vpc_config.android_name = ?
            """, (container_name,))
            row = cursor.fetchone()
            conn.close()

            if not row:
                # print(f"没有安卓需要重写vpc: {container_name}")
                return

            tun, address, user, password, android_ip = row

            try:
                docker_api = dockerApi("172.17.0.1")
                command = "ip addr show eth0 | grep 'inet ' | awk '{print $2}' | cut -d'/' -f1"
                result = subprocess.run(command, shell=True, capture_output=True, text=True)
                if result.returncode == 0:
                    sdk_eth0_ip = result.stdout.strip()
                else:
                    logger.debug(f"获取 SDK 容器 eth0 IP 失败: {result.stderr.strip()}")
                    # continue

                # 检查容器网卡名称
                # check_result = docker_api.SDK_contianer_exec(container_name, "ifconfig rmnet0")
                # output = check_result.output.decode('utf-8') if hasattr(check_result, 'output') else str(check_result)
                # net_interface = "rmnet0" if (output and "No such device" not in output) else "bur0"
                
                start_time = time.time()
                timeout_seconds = 120
                while True:
                    if time.time() - start_time > timeout_seconds:
                        # logger.debug(f"等待容器启动超时: {android_name}")
                        break
                    apiinfo = docker_api.SDK_get_container_api_http(container_name, "172.17.0.1")
                    if apiinfo != None:
                        api = MytOS_API()
                        exec_ret = api.is_api_server_inited(apiinfo['ip'], apiinfo['port'], time_out=120, isdevInit=1, docker_api=docker_api, dc_name=container_name)
                        if exec_ret == 0:

                            check_result = docker_api.SDK_contianer_exec(container_name, "ifconfig rmnet0")
                            output = check_result.output.decode('utf-8') if hasattr(check_result, 'output') else str(check_result)
                            net_interface = "rmnet0" if (output and "No such device" not in output) else "bur0"

                            # 添加网络规则
                            add_cmd = (
                                "sd -c 'setprop ro.boot.dns_force_tcp true;"
                                # "ip route add 172.16.0.0/12 via 172.17.0.1 dev bur0 table bur0;"
                                # "ip route add 10.0.0.0/8 via 172.17.0.1 dev bur0 table bur0;"
                                # "ip route add 192.168.0.0/16 via 172.17.0.1 dev bur0 table bur0;"
                                # "ip route del default via 172.17.0.1 dev bur0 table bur0;"
                                # f"ip route add default via {sdk_eth0_ip} dev bur0 table bur0'"
                                "ip rule add from all uidrange 0-99999 lookup 77 pref 10;"
                                "ip route add 172.16.0.0/12 via 172.17.0.1 dev bur0 table 77;"
                                "ip route add 10.0.0.0/8 via 172.17.0.1 dev bur0 table 77;"
                                "ip route add 192.168.0.0/16 via 172.17.0.1 dev bur0 table 77;"
                                f"ip route add default via {sdk_eth0_ip} dev bur0 table 77'"
                            )
                            add_cmd = add_cmd.replace("bur0", net_interface)
                            result = docker_api.SDK_contianer_exec(container_name, add_cmd)
                            # 检查命令执行结果
                            if result.exit_code == 0 and "Cannot find device" not in result.output.decode('utf-8'):
                                logger.info(f"安卓容器网络规则恢复成功: {container_name}")
                                break
                            else:
                                # logger.debug(f"添加网络规则失败，重试中: {result.output.decode('utf-8')}")
                                time.sleep(3)  # 等待 3 秒后重试
                        else:
                            # logger.debug(f"安卓接口返回不为0: {android_name}")
                            time.sleep(3)
                    else:
                        # logger.debug(f"安卓容器网络规则恢复失败: {android_name}")
                        pass

            except Exception as e:
                logger.debug(f"安卓容器网络规则恢复失败 {container_name}: {str(e)}")
        except Exception as e:
            logger.debug(f"恢复安卓容器 {container_name} 的 VPC 规则失败: {str(e)}")
        

    #开启后台监控docker events 事件监控进程
    #{'status': 'start', 'id': '670b9d62728dea350a2310655bf94fa3e08991dc0c894170fe7cc57bb9e125d4', 
    # 'from': 'registry.cn-hangzhou.aliyuncs.com/whsyf/dobox:rk3588-dm-base-20230925-02', 
    # 'Type': 'container', 'Action': 'start', 
    # 'Actor': {'ID': '670b9d62728dea350a2310655bf94fa3e08991dc0c894170fe7cc57bb9e125d4', 'Attributes': {'idx': '6', 'image': 'registry.cn-hangzhou.aliyuncs.com/whsyf/dobox:rk3588-dm-base-20230925-02', 'mytsdk_dns': '223.5.5.5', 'mytsdk_network': 'bridge', 'name': 'myt_6_t6'}},
    #  'scope': 'local', 'time': 1699179188, 'timeNano': 1699179188720585705}
    

    #{'Type': 'network', 'Action': 'connect', 'Actor': {'ID': '2cccb216edbf09c2b29422f0fda18122f92d1998def6ad74811bdef17a106648', 'Attributes': {'container': 'f995a313377e9949598f3d9603aaa4bd53c20ef36f2db2a8d0c2cd611f656654', 'name': 'bridge', 'type': 'bridge'}}, 'scope': 'local', 'time': 1745374626, 'timeNano': 1745374626987135821}
    # {'Type': 'network', 'Action': 'disconnect', 'Actor': {'ID': '2cccb216edbf09c2b29422f0fda18122f92d1998def6ad74811bdef17a106648', 'Attributes': {'container': 'f995a313377e9949598f3d9603aaa4bd53c20ef36f2db2a8d0c2cd611f656654', 'name': 'bridge', 'type': 'bridge'}}, 'scope': 'local', 'time': 1745374615, 'timeNano': 1745374615295640514}
    # 当监听到docker 容器创建和销毁的时候 如果是android容器则将其指定的端口镜像映射到本容器的端口上
    # 10008  10009       webrtc plugin  端口
    def start_listen_events(self, ip):
        try:
            docker_api =  dockerApi(ip)
            events = docker_api.get_events()
            Check_Time = time.time()

            for event in events:            
                #logger.debug(event)

                now = time.time()
                if now - Check_Time > 60:
                    Check_Time = now
                    #检查当前的网络环境是否正确
                    self.check_network_env()
                    #logger.debug("执行检测")
                #添加事件过滤
                if 'Type' not in event or 'Action' not in event:
                    continue

                if 'Action' in event  and event['Type'] == 'network':
                    act = event['Action']
                    dc_id = event['Actor']['Attributes']['container']
                    network_type = event['Actor']['Attributes']['type']
                    attr = docker_api.SDK_get_contianer_attr(dc_id)
                    bIsAndroid = False
                    if attr != False:  
                        if 'Config' in attr:
                            if 'Labels' in attr['Config']:
                                if 'idx' in attr['Config']['Labels']:
                                    idx = int(attr['Config']['Labels']['idx'])
                                    bIsAndroid = True
                                
                            #print(attr['Config']['Labels'])
                    #print(attr)
                    if bIsAndroid == True:
                        #判断当前网络模式  
                        #cfginfo = docker_api.SDK_get_container_config_detail(dc_id)
                        #if cfginfo['network'] != 'myt':
                        if network_type == 'bridge':
                            cfginfo = docker_api.SDK_get_container_config_detail(dc_id)
                            if act == 'connect':
                                local_ip = cfginfo['local_ip']
                                print(f"local_ip:{local_ip}")
                                if self.get_idx_port_status(idx) == False:
                                    port = idx -1 + 20000
                                    #增加端口映射功能 
                                    if (self.add_port_forward(local_ip, port, 10008, 'tcp') == True) and \
                                        (self.add_port_forward(local_ip, port, 10008, 'udp') == True):
                                        #添加端口映射成功
                                        self.add_port(port, dc_id, local_ip)
                                        print(f"添加端口映射成功, local_ip:{local_ip}, port:{port}, dc_id:{dc_id}")
                                    else:
                                        print(f"添加端口映射失败, local_ip:{local_ip}, port:{port}, dc_id:{dc_id}")
                                else:
                                    print(f"端口已经被占用, local_ip:{local_ip}, port:{port}, dc_id:{dc_id}")
        
                            elif act == 'disconnect':
                                #移除端口映射
                                exec_ret = self.remove_port(dc_id)
                                if exec_ret == False:
                                    print(f"移除端口映射失败, dc_id:{dc_id}")
                                else:
                                    port = exec_ret['port']
                                    local_ip = exec_ret['ip']
                                    if (self.delete_port_forward(local_ip, port, 10008, 'tcp') == True) and \
                                        (self.delete_port_forward(local_ip, port, 10008, 'udp') == True):
                                        print(f"移除端口映射成功, dc_id:{dc_id} port:{port}")
                                    else:
                                        print(f"移除端口映射失败, dc_id:{dc_id} port:{port}")
                        else:
                            pass
        except Exception as e:
            logger.debug("Exception Error:" + str(e))
                
                        #do nothing
                # else:
                #     #重新扫描当前的容器
                #     self.clear_iptables()
                #     self.scan_docker_port()
            # if event['Type'] == 'container':
            #     if event['Action'] == 'start':
            #         container_name = event['Actor']['Attributes'].get('name', '')
            #         # print(f"重写规则容器是{container_name}")
            #         self.restore_android_vpc_rules(docker_api,container_name)