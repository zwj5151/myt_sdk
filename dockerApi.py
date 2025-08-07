import docker
import time
from docker.errors import DockerException, APIError
from docker.errors import NotFound
from docker.errors import ImageNotFound
import docker.errors
from common.logger import logger
import os
import json
import random
import re
import math
from dateutil import parser

class dockerApi(object):
    _port = 2375
    _NETWORK = "myt" 
    # 用于执行shell 命令的公共镜像
    _ALPINE = "registry.cn-hangzhou.aliyuncs.com/whsyf/dobox:alpine"
    _SHELL_INS = "SHELL_INS"
    
    def __init__(self, ip):
        # init docker_client
        self.docker_client = docker.DockerClient(base_url="tcp://" + ip + ":" + str(self._port), version="1.41", timeout=30, tls=False)
        self.self_hostip = ip
        self.check_alpine_img()


    def __init__(self, ip, time_out = 30, bCheckImg = False):
                # init docker_client
        self.docker_client = docker.DockerClient(base_url="tcp://" + ip + ":" + str(self._port), version="1.41", timeout=time_out, tls=False)
        #print(self.docker_client.info())
        # 检查alpine镜像是否存在 不存在则创建
        # if not self.check_alpine_image(ip):
        self.self_hostip = ip
        if bCheckImg:
            self.check_alpine_img()



    #判断基础进行是否存在 若不存在则镜像下载
    def check_alpine_img(self):
        if not self.SDK_exits_image(self._ALPINE):
            logger.debug('alpine镜像不存在 进行下载操作')
            self.SDK_pull_image(self._ALPINE)

    #都开连接
    def close(self):
        self.docker_client.close()

    #返回是否是 镜像分区
    def is_img_dir(self,dir_path):
        ret = False
        if len(dir_path)>=4:
            last_chars = dir_path[-4:]
            if last_chars == ".img" :
                ret = True
        return ret
    """
        remove 容器对象
        同时删除容器实例对象和数据文件夹
    """
    def remove(self, ip, c_id):
        ret = False
        # 获取实例目录名称
        data_path = self.get_data_dir(c_id)
        if data_path != '':
            # 删除实例
            while True:
                if self.SDK_stop_continer(c_id) == False:
                    ret = False
                    break
                
                self.SDK_wait_continer(c_id)

                if self.SDK_rm_continer(c_id) == False:
                    ret = False
                    break

                # 创建特殊实例 挂载data
                if self.is_img_dir(data_path):
                    if os.path.basename(data_path) == "data.img":       #用于区分pc 端创建的和web端创建的
                        dir_path = os.path.dirname(data_path)
                    else:
                        dir_path = data_path
                    cmd = "rm -rf  " + dir_path
                else:
                    cmd = "rm -rf  " + data_path

                if self.SDK_SHELL_COMMAD(cmd) == False:
                    ret = False
                    break

                ret = True
                break
        return ret
    
    #获取Events
    def get_events(self):
        return self.docker_client.events(decode = True)
    
    #重置指定的容器
    def reset(self, c_id):
        ret = False
        # 获取实例目录名称
        data_path = self.get_data_dir(c_id, True)
        if data_path != '':
            # 删除实例
            while True:
                cfginfo = self.SDK_get_container_config_detail(c_id)
                if self.SDK_stop_continer(c_id) == False:
                    ret = False
                    break

                self.SDK_wait_continer(c_id)

                # 创建特殊实例 挂载data
                #判断当前镜像是否是img 分区格式

                if self.is_img_dir(data_path) == True:
                    cmd = " mkfs.ext4 -O project,quota " + data_path
                else:
                    cmd = "rm -rf  " + data_path

                if self.SDK_SHELL_COMMAD(cmd) == False:
                    ret = False
                    break

                #和重置之前的状态保持一致
                if cfginfo['status'] == 'running':
                    self.SDK_start_continer(c_id)

                ret = True
                break
        return ret
    
    #拷贝指定的容器
    #model = 'c1' 'a1' 'p1'  默认为c1
    def copy(self, c_src, c_dest, index, model = None):
        ret = False
        # 获取实例目录名称
        data_path = self.get_data_dir(c_src)
        if data_path != '':
            # 删除实例
            while True:
                
                if self.SDK_stop_continer(c_src) == False:
                    ret = False
                    break

                self.SDK_wait_continer(c_src)

                cfginfo = self.SDK_get_container_config_detail(c_src)

                img = cfginfo['image']
                if len(img) == 0:               #镜像为空则返回失败
                    ret = False
                    break

                is_img_mode = False
                str_time = time.strftime('%Y%m%d%H%M%S')
                #增加一个随机数防止文件名冲突
                random_number = random.randint(0, 999)
                str_time = f"{str_time}_{random_number:03d}"
                # 创建特殊实例 拷贝data
                if self.is_img_dir(data_path) == True:

                    
                    new_data_path = "/mmc/data/data" + str(index) + "_" + str_time
                    #cmd = "mkdir " +  new_data_path + "  && cp --sparse=always  " + data_path + " " + new_data_path
                    cmd = "mkdir " +  new_data_path 
                    is_img_mode = True
                else:
                    query_cp_cmd = "ls -l /bin/cp"
                    exec_ret = self.SDK_SHELL_COMMAD(query_cp_cmd)
                    if "busybox" in exec_ret:
                        install_cmd = "apk add --no-cache coreutils"
                        self.SDK_SHELL_COMMAD(install_cmd)

                    new_data_path = "/mmc/data/data" + str(index) + "_" + str_time
                    cmd = "cp -a  " + data_path + " " + new_data_path

                if self.SDK_SHELL_COMMAD(cmd) == False:
                    ret = False
                    break
                
                if is_img_mode == True:
                    self.SDK_COPY_IMG(data_path, new_data_path + "/data.img")
                #c = self.SDK_get_contianer(c_src)




                network = cfginfo['network']
                if 'dns' in cfginfo:
                    dns = cfginfo['dns']
                else:
                    dns = "223.5.5.5"

                memory = cfginfo['memory']
                cpusets = cfginfo['cpuset']

                dobox_resolution_detail = {}
                dobox_resolution = 'custom'
                dobox_resolution_detail['width'] = cfginfo['width']
                dobox_resolution_detail['height'] = cfginfo['height']
                dobox_resolution_detail['dpi'] = cfginfo['dpi']
                



                mac = self.random_mac()
                # if cfginfo['dpi'] == '320':
                #     dobox_resolution = "720P"
                # else:
                #     dobox_resolution = "1080P"

                if len(network)>0:
                    if network == "myt":
                        if 'ip' in cfginfo:
                            c_ip = cfginfo['ip']
                        if len(c_ip)>0:
                            # 创建新的容器
                            c_dict = {
                                'tid': c_dest,                       # 必填项   后缀带_n
                                'index': int(index),                            # 必填项   1-12
                                'token': c_dest,                            # 必填项   任意字符串
                                'dns1': dns,                  # 选填项   223.5.5.5/8.8.8.8
                                'image': img,
                                'network': 'myt',                       # 必填项 网络名称
                                #'network_id': network_id,  # 必填项 get_network 中返回的ID
                                'docker_ip': c_ip,            # 必填项
                                #'datapath': new_data_path + "/data"   # 可选参数指定数据文件夹
                                }
                            if is_img_mode== True:
                                c_dict['imgpath'] = new_data_path + "/data.img"
                            else:
                                c_dict['datapath'] = new_data_path + "/data"

                        else:
                            # 创建新的容器
                            c_dict = {
                                'tid': c_dest,                       # 必填项   后缀带_n
                                'index': int(index),                            # 必填项   1-12
                                'token': f"{c_dest}_{index}",                            # 必填项   任意字符串
                                'dns1': dns,                  # 选填项   223.5.5.5/8.8.8.8
                                'image': img,
                                #'network': 'myt',                       # 必填项 网络名称
                                #'network_id': network_id,  # 必填项 get_network 中返回的ID
                                #'docker_ip': c_ip,            # 必填项
                                #'datapath': new_data_path + "/data"   # 可选参数指定数据文件夹
                                }
                            if is_img_mode== True:
                                c_dict['imgpath'] = new_data_path +  "/data.img"
                            else:
                                c_dict['datapath'] = new_data_path + "/data"
                    else:
                        # 创建新的容器
                        c_dict = {
                            'tid': c_dest,                       # 必填项   后缀带_n
                            'index': int(index),                            # 必填项   1-12
                            'token': f"{c_dest}_{index}",                            # 必填项   任意字符串
                            'dns1': dns,                  # 选填项   223.5.5.5/8.8.8.8
                            'image': img,
                            #'network': 'myt',                       # 必填项 网络名称
                            #'network_id': network_id,  # 必填项 get_network 中返回的ID
                            #'docker_ip': c_ip,            # 必填项
                            #'datapath': new_data_path + "/data"   # 可选参数指定数据文件夹
                            }
                        if is_img_mode== True:
                            c_dict['imgpath'] = new_data_path + "/data.img"
                        else:
                            c_dict['datapath'] = new_data_path + "/data"

 
                else:
                    # 创建新的容器
                    c_dict = {
                        'tid': c_dest,                       # 必填项   后缀带_n
                        'index': int(index),                            # 必填项   1-12
                        'token': f"{c_dest}_{index}",                            # 必填项   任意字符串
                        'dns1': dns,                  # 选填项   223.5.5.5/8.8.8.8
                        'image': img,
                        #'network': 'myt',                       # 必填项 网络名称
                        #'network_id': network_id,  # 必填项 get_network 中返回的ID
                        #'docker_ip': c_ip,            # 必填项
                        #'datapath': new_data_path + "/data"   # 可选参数指定数据文件夹
                    }
                    
                    if is_img_mode== True:
                        c_dict['imgpath'] = new_data_path + "/data.img"
                    else:
                        c_dict['datapath'] = new_data_path + "/data"


                if memory>0:
                    c_dict['memory'] = memory 
                
                if len(cpusets)>0:
                    c_dict['cpuset'] = cpusets

                c_dict['mac'] = mac

                c_dict['dobox_resolution'] = dobox_resolution
                c_dict['dobox_resolution_detail'] = dobox_resolution_detail

                #"androidboot.ro.rpa=7100",         rpa 主机端口
                #"androidboot.ro.init.devinfo=4"    开机指定初始化设备型号
                if 'androidboot.ro.rpa' in cfginfo['Args']:
                    c_dict['rpa_port'] = cfginfo['Args']['androidboot.ro.rpa']
                
                if 'androidboot.ro.init.devinfo' in cfginfo['Args']:
                    c_dict['init_dev'] = cfginfo['Args']['androidboot.ro.init.devinfo']

                if 'fps' in cfginfo:
                    c_dict['fps'] = cfginfo['fps']

                if 'rpa' in cfginfo:
                    c_dict['rpa_port'] = cfginfo['rpa']

                if 'dnstcp_mode' in cfginfo:
                    c_dict['dnstcp_mode'] = cfginfo['dnstcp_mode']
                
                if model is None:
                    r = self.SDK_Create_container(self.self_hostip, c_dict)
                elif model == 'c1' or model == 'q1':
                    r = self.SDK_Create_container(self.self_hostip, c_dict)
                elif model == 'a1':
                    r = self.SDK_Create_container_a1(self.self_hostip, c_dict)
                elif model == 'p1':
                    r = self.SDK_Create_container_p1(self.self_hostip, c_dict)
                else:
                    r = False
                
                    
                if r == False:
                    ret = False
                    break
                
                #self.SDK_start_continer(c_dest)

                ret = True
                break
        return ret
    

    #更新指定的容器
    # 更新成功后 容器处于关机状态需要在此 启动
    # img --   镜像
    # index -- 坑位
    # dns ---  dns 信息
    # c_name ---  容器名称
    # model --- 'a1' 'p1'  默认为c1
    # enforceMode --  严格模式
    def update_container(self, c_src, dict, model = None, c_index = None, c_img = None, c_dns = None,c_name = None, new_ip = None, fps = None, mac = None, enforceMode = None, resolution = None):
        ret = False

        if c_index is None and c_img is None and c_dns is None and c_name is None and fps is None and new_ip is None and len(dict)==0 and resolution is None:
            return True

        # 获取实例目录名称
        data_path = self.get_data_dir(c_src, True)
        if self.is_img_dir(data_path) == True:
            is_img_mode = True
        else:
            is_img_mode = False
            
        if data_path != '':
            # 删除实例
            while True:
                cfginfo = self.SDK_get_container_config_detail(c_src)
                if cfginfo == False:
                    ret = False
                    break 

                if self.SDK_stop_continer(c_src) == False:
                    ret = False
                    break

                self.SDK_wait_continer(c_src)

                #c = self.SDK_get_contianer(c_src)


                memory = cfginfo['memory']
                cpusets = cfginfo['cpuset']

                if resolution is None:
                    if cfginfo['dpi'] == '320':
                        dobox_resolution = "720P"
                    else:
                        dobox_resolution = "1080P"
                else:
                    dobox_resolution = resolution['resolution']

                if c_img is not None:
                    img = c_img
                else:                
                    img = cfginfo['image']

                network = cfginfo['network']
                if 'dns' in cfginfo:
                    dns = cfginfo['dns']
                else:
                    dns = "223.5.5.5"

                if c_dns is not None:
                    dns = c_dns

                if c_index is not None:
                    index = c_index
                else:
                    index = cfginfo['index']

                if fps is None:
                    if 'fps' in cfginfo:
                        fps = cfginfo['fps']

                #用户指定修改网络类型
                if new_ip is not None:
                    network = "myt"
                    cfginfo['ip'] = new_ip
                else:
                    network = 'bridge'
                    
                if len(network)>0:
                    if network == "myt":
                        if 'ip' in cfginfo:
                            c_ip = cfginfo['ip']
                        if len(c_ip)>0:
                            # 创建新的容器
                            c_dict = {
                                'tid': c_src,                       # 必填项   后缀带_n
                                'index': int(index),                            # 必填项   1-12
                                'token': f"{c_src}_{index}",                            # 必填项   任意字符串
                                'dns1': dns,                  # 选填项   223.5.5.5/8.8.8.8
                                'image': img,
                                'network': 'myt',                       # 必填项 网络名称
                                #'network_id': network_id,  # 必填项 get_network 中返回的ID
                                'docker_ip': c_ip,            # 必填项
                                #'datapath': new_data_path + "/data"   # 可选参数指定数据文件夹
                                }
                        else:
                            # 创建新的容器
                            c_dict = {
                                'tid': c_src,                       # 必填项   后缀带_n
                                'index': int(index),                            # 必填项   1-12
                                'token': f"{c_src}_{index}",                            # 必填项   任意字符串
                                'dns1': dns,                  # 选填项   223.5.5.5/8.8.8.8
                                'image': img,
                                #'network': 'myt',                       # 必填项 网络名称
                                #'network_id': network_id,  # 必填项 get_network 中返回的ID
                                #'docker_ip': c_ip,            # 必填项
                                #'datapath': new_data_path + "/data"   # 可选参数指定数据文件夹
                                }
                    else:
                        # 创建新的容器
                        c_dict = {
                            'tid': c_src,                       # 必填项   后缀带_n
                            'index': int(index),                            # 必填项   1-12
                            'token': f"{c_src}_{index}",                            # 必填项   任意字符串
                            'dns1': dns,                  # 选填项   223.5.5.5/8.8.8.8
                            'image': img,
                            #'network': 'myt',                       # 必填项 网络名称
                            #'network_id': network_id,  # 必填项 get_network 中返回的ID
                            #'docker_ip': c_ip,            # 必填项
                            #'datapath': new_data_path + "/data"   # 可选参数指定数据文件夹
                            }

                else:
                    # 创建新的容器
                    c_dict = {
                    'tid': c_src,                       # 必填项   后缀带_n
                    'index': int(index),                            # 必填项   1-12
                    'token': f"{c_src}_{index}",                            # 必填项   任意字符串
                    'dns1': dns,                  # 选填项   223.5.5.5/8.8.8.8
                    'image': img,
                    #'network': 'myt',                       # 必填项 网络名称
                    #'network_id': network_id,  # 必填项 get_network 中返回的ID
                    #'docker_ip': c_ip,            # 必填项
                    #'datapath': new_data_path + "/data"   # 可选参数指定数据文件夹
                    }

                if is_img_mode== True:
                    c_dict['imgpath'] = data_path
                else:
                    c_dict['datapath'] = data_path

                if memory>0:
                    c_dict['memory'] = memory 
                
                if len(cpusets)>0:
                    c_dict['cpuset'] = cpusets

                if c_name is not None:
                    c_dict['tid'] = c_name

                if fps is  not None:
                    c_dict['fps'] = fps

                if mac is not None:
                    c_dict['mac'] = mac

                if enforceMode is not None:
                    c_dict['enforce'] = enforceMode


                if 'dnstcp_mode' in cfginfo:
                    c_dict['dnstcp_mode'] = cfginfo['dnstcp_mode']

                c_dict['dobox_resolution'] = dobox_resolution
                if dobox_resolution == 'custom': 
                    c_dict['dobox_resolution_detail'] = {}
                    c_dict['dobox_resolution_detail']['width'] = resolution['width']
                    c_dict['dobox_resolution_detail']['height'] =  resolution['height'] 
                    c_dict['dobox_resolution_detail']['dpi'] =  resolution['dpi']

                #赋值属性值
                for key,value in dict.items():
                    c_dict[key] = value

                #修改更新容器的逻辑若创建失败则还原到初始状态
                tmp_src_name = c_src + "_bak_" + str(time.time())

                if self.SDK_rename_contianer(c_src, tmp_src_name) == False:
                    ret = False
                    break
                
                if model is None:
                    r = self.SDK_Create_container(self.self_hostip, c_dict, True)
                elif model == 'c1':
                    r = self.SDK_Create_container(self.self_hostip, c_dict, True)
                elif model == 'a1':
                    r = self.SDK_Create_container_a1(self.self_hostip, c_dict, True)
                elif model == 'p1':
                    r = self.SDK_Create_container_p1(self.self_hostip, c_dict, True)

                if r == False:
                    #创建失败则还原到初始状态
                    self.SDK_rename_contianer(tmp_src_name, c_src)
                    ret = False
                    break
                else:
                    self.SDK_rm_continer(tmp_src_name)
                
                if cfginfo['status'] == 'running':
                    self.SDK_start_continer(c_dict['tid'])

                ret = True
                break
        return ret

    #清理volume
    def SDK_Prune_volume(self):
        ret = True
        try:
            vol_arr = self.docker_client.volumes.list()
            for vol in vol_arr:
                vol.remove()
        except APIError as e:
            logger.debug("API Error:" + str(e))
            ret = False
        except DockerException  as e:
            logger.debug("DockerException Error:"  + str(e))
            ret = False
        return ret

    #清理未使用的镜像
    def SDK_Prune_image(self):
        ret = True
        try:
            img_arr = self.docker_client.images.list()
            for img in img_arr:
                #if img.tags[0] not in dc_img_arr:
                try:
                    self.docker_client.images.remove(img.id)
                except APIError as e:
                    if e.status_code == 409:
                        logger.debug("Image is in use by a container")
                        continue
                    else:
                        logger.debug("API Error:" + str(e))
                        break
            
        except ImageNotFound:
            logger.debug(f"Image {self._ALPINE} 不存在")
            ret = False
        except APIError as e:
            logger.debug("API Error:" + str(e))
            ret = False
        except DockerException  as e:
            logger.debug("DockerException Error:"  + str(e))
            ret = False
        except Exception as e:
            logger.debug("Exception Error:" + str(e))
            ret = False  
        return ret
    
    #关闭所有的容器
    def SDK_Close_All_container(self, except_name = ""):
        ret = True
        try:
            arr = self.docker_client.containers.list(sparse=True)
            for c in arr:
                print(c.attrs['Names'])
                if c.attrs['Names'][0] == f"/{except_name}":
                    continue
                c.stop()
        except ImageNotFound:
            logger.debug(f"Image {self._ALPINE} 不存在")
            ret = False
        except APIError as e:
            logger.debug("API Error:" + str(e))
            ret = False
        except DockerException  as e:
            logger.debug("DockerException Error:"  + str(e))
            ret = False
        except Exception as e:
            logger.debug("Exception Error:" + str(e))
            ret = False  
        return ret
    # 清理 未使用的实例
    def SDK_Prune_container(self):
        ret = True
        try:
            self.docker_client.containers.prune()
        except ImageNotFound:
            logger.debug(f"Image {self._ALPINE} 不存在")
            ret = False
        except APIError as e:
            logger.debug("API Error:" + str(e))
            ret = False
        except DockerException  as e:
            logger.debug("DockerException Error:"  + str(e))
            ret = False
        except Exception as e:
            logger.debug("Exception Error:" + str(e))
            ret = False  
        return ret  

    # 创建img镜像
    # size  单位GB  分区大小
    # file_path  文件的存储路径
    def SDK_Create_imgDisk(self, size, file_path):
        ret = False
        file_name = file_path + "/data.img" 
        cmd = "mkdir " + file_path + " &&  dd if=/dev/zero of=" + str(file_name)  + " bs=1G seek=" + str(size) + " count=1 && mkfs.ext4 -O project,quota " + str(file_name) 
        ret = self.SDK_SHELL_COMMAD(cmd)
        logger.debug(f"SDK_Create_imgDisk={ret}")

        if ret != "":
            cmd = "rm -rf  " + file_path
            self.SDK_SHELL_COMMAD(cmd)
        return ret
    
    #获取Img文件的大小
    def SDK_Get_imgDisk_Size(self, file_path):
        ret = False
        cmd = "ls -lh "  + file_path + " | awk -F' ' '{print $5}'"           
        exec_ret = self.SDK_SHELL_COMMAD(cmd)
        ret = exec_ret.rstrip("\n")
        logger.debug(f"SDK_Get_imgDisk_Size={ret}  cmd={cmd}")
        return ret
    
    #规整磁盘空间 不允许有小数  存在小数则扩大一位
    def SDK_Disk_Align(self, size_str):
        # 使用正则表达式提取数字部分
        match = re.search(r'(\d+\.?\d*)', size_str)
        if not match:
            return size_str  # 如果没有匹配到数字，返回原字符串

        size = float(match.group(1))
        unit = size_str[match.end():].strip()

        if size.is_integer():
            # 如果小数部分为0，去掉小数部分
            processed_size = int(size)
        else:
            # 如果小数部分大于0，向上取整
            processed_size = math.ceil(size)

        return f"{processed_size}{unit}"

    # 创建容器实例
    def SDK_Create_container(self,ip,config_dict, bUpdateOpern = False):
        ret = False
        try:
            bridge_mode = False
            tid = config_dict['tid']
            index = config_dict['index']
            token = config_dict['token']
            
            #随机生成mac地址
            mac = self.random_mac()
            #开机时间作随机
            if 'timeoffset' in config_dict:
                t_offset = int(config_dict['timeoffset']) * 60
                t_offset = str(t_offset)
            else:
                t_offset = str(random.randint(86400*6, 86400*30))

            # config DNS
            if 'dns1' in config_dict:
                dns1 = config_dict['dns1']
            else:
                dns1 = '223.5.5.5'

            # config resolution
            if 'dobox_resolution' in config_dict:
                if config_dict['dobox_resolution'] == '720P':
                    dobox_width = '720'
                    dobox_height = '1280'
                    dobox_dpi = '320'
                elif config_dict['dobox_resolution'] == '1080P':
                    dobox_width = '1080'
                    dobox_height = '1920'
                    dobox_dpi = '480'
                elif config_dict['dobox_resolution'] == 'custom':
                    dobox_width = config_dict['dobox_resolution_detail']['width']
                    dobox_height = config_dict['dobox_resolution_detail']['height']
                    dobox_dpi = config_dict['dobox_resolution_detail']['dpi']
                else:
                    dobox_width = '720'
                    dobox_height = '1280'
                    dobox_dpi = '320'
            else:
                dobox_width = '720'
                dobox_height = '1280'
                dobox_dpi = '320'

            image = config_dict['image']
            binder_index = (index - 1) * 3 + 1
            #event_index =  index + 1
            data_index = index

            #记录资源目录 用于创建失败时删除目录
            datares_folder = ''
            if 'datapath' in config_dict:
                data_path = config_dict['datapath']  + ":/data"
                #mac = None
            else:
                str_time = time.strftime('%Y%m%d%H%M%S')
                random_number = random.randint(0, 999)
                str_time = f"{str_time}_{random_number:03d}"
                data_path = "/mmc/data/data" + str(data_index) + "_" + tid +  "_"+ str_time + "/data" + ":/data"
                datares_folder = "/mmc/data/data" + str(data_index) + "_" + tid +  "_"+ str_time + "/data" 



            #使用img 方式
            if 'imgpath' in config_dict:
                data_path = config_dict['imgpath']  + ":/userdata.img"
                datares_folder = config_dict['imgpath']
                #mac = None

            if 'memory' in config_dict:
                memory = config_dict['memory']
            else:
                memory = None

            if 'memoryswap' in config_dict:
                swap = config_dict['memoryswap']
            
            if 'cpuset' in config_dict:
                cpuset = config_dict['cpuset']
            else:
                cpuset = None

            if 'network' in config_dict:
                network = config_dict['network']
                #network_id = config_dict['network_id']
                docker_ip = config_dict['docker_ip']
            else:
                network = 'bridge'  # bridge
                bridge_mode = True

            if 'fps' in config_dict:
                fps = str(config_dict['fps'])
            else:
                fps = '24'

            if 'mac' in config_dict:
                mac = config_dict['mac']

            if 'ykuser' in config_dict:
                yk_user = config_dict['ykuser']
            
            if 'yktoken' in config_dict:
                yk_token = config_dict['yktoken']

            if 'yktid' in config_dict:
                yk_tid = config_dict['yktid']
            
            if 'ykbitrate' in config_dict:
                yk_bitrate = config_dict['ykbitrate']
                data_json = json.loads(yk_bitrate)  
                yk_bitrate_1 = data_json['1']
                yk_bitrate_2 = data_json['2']
                yk_bitrate_3 = data_json['3']
                yk_bitrate_4 = data_json['4']

            phyinput = None
            if 'phyinput' in config_dict:
                phyinput = config_dict['phyinput']
            
            #映射主机目录到android 中
            #volumes = ["/dev/net/tun:/dev/tun", "/dev/mali0:/dev/mali0", data_path,"/usr/share/zoneinfo/Asia/Shanghai:/etc/localtime", "/mmc/data:/dev/test"]
            volumes = ["/dev/net/tun:/dev/tun", "/dev/mali0:/dev/mali0", data_path,"/usr/share/zoneinfo/Asia/Shanghai:/etc/localtime"]

            command = ["androidboot.hardware=rk30board",
                            "androidboot.dobox_fps=" + fps,
                            #"androidboot.selinux=permissive",
                            "qemu=1",
                            "androidboot.ro.kernel.syfToken=" + token,
                            "androidboot.ro.kernel.syfHost=" + ip,
                            "androidboot.dobox_net_ndns=1",
                            "androidboot.dobox_net_dns1=" + dns1,
                            "androidboot.dobox_width=" + str(dobox_width),
                            "androidboot.dobox_height=" + str(dobox_height),
                            "androidboot.dobox_dpi=" + str(dobox_dpi),
                            "androidboot.dobox_tag=" + token,
                            "androidboot.offset=" + t_offset,
                            #"androidboot.ro.rpa=7100",         rpa 主机端口
                            #"androidboot.ro.init.devinfo=4"    开机指定初始化设备型号
                            #"androidboot.dobox_debug=true"
                            ]
            
            #开机默认不随机
            if 'random_dev' in config_dict:
                if config_dict['random_dev'] == '0':
                    command.append("androidboot.nomodifydev=true")
            #dns tcp 模式
            if 'dnstcp_mode' in config_dict:
                if config_dict['dnstcp_mode'] == '1':
                    command.append("androidboot.dns_force_tcp=true")

            append_flag = False
            if 'rpa_port' in config_dict: 
                command.append(f"androidboot.ro.rpa={config_dict['rpa_port']}")
                append_flag = True
            # else:
            #     #默认添加 rpa 端口
            #     rpa_hostport = 7100 + index
            #     command.append(f"androidboot.ro.rpa={rpa_hostport}")

            if 'adbport' in config_dict:
                command.append(f"androidboot.ro.ccd={config_dict['adbport']}")
                append_flag = True
                #volumes.append("/proc/1/ns/net:/dev/net")

            if append_flag == True:
                volumes.append("/proc/1/ns/net:/dev/mnetns")

            #默认添加9082  -> 7120+索引 和   客户端传屏的映射 tcp  7130+索引 * 2
            # api_hostport = 7120 + index    
            # video_hostport = 7130 + index * 2
            # command.append(f"androidboot.ro.sysext={api_hostport}")
            # command.append(f"androidboot.ro.hwcodec={video_hostport}")
            #volumes.append("/proc/1/ns/net:/dev/mnetns")


                
            if 'init_dev' in config_dict:
                command.append(f"androidboot.ro.init.devinfo={config_dict['init_dev']}")
            
            if 'enforce' in config_dict:
                if config_dict['enforce'] == '0':
                    command.append(f"androidboot.selinux=permissive")

            if 'ykuser' in config_dict and 'yktoken' in config_dict:
                command.append(f"androidboot.ro.yk.user={yk_user}")
                command.append(f"androidboot.ro.yk.token={yk_token}")

            if 'yktid' in config_dict:
                command.append(f"androidboot.ro.lgsys.tid={yk_tid}")

            if 'ykbitrate' in config_dict:
                command.append(f"androidboot.ro.yk.bitrate1={yk_bitrate_1}")
                command.append(f"androidboot.ro.yk.bitrate2={yk_bitrate_2}")
                command.append(f"androidboot.ro.yk.bitrate3={yk_bitrate_3}")
                command.append(f"androidboot.ro.yk.bitrate4={yk_bitrate_4}")

            #默认开启s5模式
            if 's5ip' in config_dict and 's5port' in config_dict and 's5pwd' in config_dict and 's5user' in config_dict:
                command.append("androidboot.s5_type=1")
                command.append(f"androidboot.s5_ip={config_dict['s5ip']}")
                command.append(f"androidboot.s5_port={config_dict['s5port']}")
                command.append(f"androidboot.s5_usr={config_dict['s5user']}")
                command.append(f"androidboot.s5_pwd={config_dict['s5pwd']}")


            if 'enablemeid' in config_dict:
                command.append("androidboot.enablemeid=true")

            cap_add = ["SYSLOG",
                        "AUDIT_CONTROL",
                        "SETGID",
                        "DAC_READ_SEARCH",
                        "SYS_ADMIN",
                        "NET_ADMIN",
                        "SYS_MODULE",
                        "SYS_NICE",
                        "SYS_TIME",
                        "SYS_TTY_CONFIG",
                        "NET_BROADCAST",
                        "IPC_LOCK",
                        "SYS_RESOURCE",
                        "SYS_PTRACE",
                        "WAKE_ALARM",
                        "BLOCK_SUSPEND",
                        "MKNOD"   # dm add
                        ]
            # Sysctls = {"net.ipv4.conf.eth0.rp_filter": "0", "net.ipv4.conf.all.rp_filter":"0"}
            Sysctls = {"net.ipv4.conf.eth0.rp_filter": "2"}
            network_mode = network
            security_opt = ["seccomp=unconfined"]
            restart_policy = {"Name": "unless-stopped", 'MaximumRetryCount': 0}
            device = [
                        {'PathOnHost': '/dev/binder' + str(binder_index), 'PathInContainer': '/dev/binder',
                        'CgroupPermissions': 'rwm'},
                        {'PathOnHost': '/dev/binder' + str(binder_index + 1), 'PathInContainer': '/dev/hwbinder',
                        'CgroupPermissions': 'rwm'},
                        {'PathOnHost': '/dev/binder' + str(binder_index + 2), 'PathInContainer': '/dev/vndbinder',
                        'CgroupPermissions': 'rwm'},
                        {'PathOnHost': '/dev/tee0', 'PathInContainer': '/dev/tee0', 'CgroupPermissions': 'rwm'},
                        {'PathOnHost': '/dev/teepriv0', 'PathInContainer': '/dev/teepriv0', 'CgroupPermissions': 'rwm'},
                        {'PathOnHost': '/dev/crypto', 'PathInContainer': '/dev/crypto', 'CgroupPermissions': 'rwm'},
                        {'PathOnHost': '/dev/mali0', 'PathInContainer': '/dev/mali0', 'CgroupPermissions': 'rwm'},
                        {'PathOnHost': '/dev/rga', 'PathInContainer': '/dev/rga', 'CgroupPermissions': 'rwm'},
                        {'PathOnHost': '/dev/dri', 'PathInContainer': '/dev/dri', 'CgroupPermissions': 'rwm'},
                        {'PathOnHost': '/dev/mpp_service', 'PathInContainer': '/dev/mpp_service', 'CgroupPermissions': 'rwm'},
                        {'PathOnHost': '/dev/fuse', 'PathInContainer': '/dev/fuse', 'CgroupPermissions': 'rwm'},
                        #{'PathOnHost': '/dev/input/event' + str(event_index), 'PathInContainer': '/dev/input/event1', 'CgroupPermissions': 'rwm'},
                        
                        # {'PathOnHost': '/dev/input/event' + str(index*2 + 1), 'PathInContainer': '/dev/input/event1', 'CgroupPermissions': 'rwm'},
                        # {'PathOnHost': '/dev/input/event' + str(index*2 + 2), 'PathInContainer': '/dev/input/event2', 'CgroupPermissions': 'rwm'},
                        # {'PathOnHost': '/dev/myinput', 'PathInContainer': '/dev/myinput', 'CgroupPermissions': 'rwm'},

                        {'PathOnHost': '/dev/input/event0', 'PathInContainer': '/dev/input/event0', 'CgroupPermissions': 'rwm'},
                        # {'PathOnHost': '/dev/input/event1', 'PathInContainer': '/dev/input/event1', 'CgroupPermissions': 'rwm'},
                        {'PathOnHost': '/dev/dma_heap/cma', 'PathInContainer': '/dev/dma_heap/cma', 'CgroupPermissions': 'rwm'},
                        {'PathOnHost': '/dev/dma_heap/cma-uncached', 'PathInContainer': '/dev/dma_heap/cma-uncached',
                        'CgroupPermissions': 'rwm'},
                        {'PathOnHost': '/dev/dma_heap/system', 'PathInContainer': '/dev/dma_heap/system',
                        'CgroupPermissions': 'rwm'},
                        {'PathOnHost': '/dev/dma_heap/system-dma32', 'PathInContainer': '/dev/dma_heap/system-dma32',
                        'CgroupPermissions': 'rwm'},
                        {'PathOnHost': '/dev/dma_heap/system-uncached', 'PathInContainer': '/dev/dma_heap/system-uncached',
                        'CgroupPermissions': 'rwm'},
                        {'PathOnHost': '/dev/dma_heap/system-uncached-dma32',
                        'PathInContainer': '/dev/dma_heap/system-uncached-dma32', 'CgroupPermissions': 'rwm'},
                        {'PathOnHost': '/dev/ashmem', 'PathInContainer': '/dev/ashmem', 'CgroupPermissions': 'rwm'}
                    ]
            cg_rules = ["c 10:* rmw", "b 253:* rmw", "b 7:* rmw"]
            
            if phyinput is not None:
                if phyinput == '1':
                    device.append({'PathOnHost': '/dev/input/event' + str(index*2 + 1), 'PathInContainer': '/dev/input/event1', 'CgroupPermissions': 'rwm'})
                    device.append({'PathOnHost': '/dev/input/event' + str(index*2 + 2), 'PathInContainer': '/dev/input/event2', 'CgroupPermissions': 'rwm'})
                    device.append({'PathOnHost': '/dev/myinput', 'PathInContainer': '/dev/myinput', 'CgroupPermissions': 'rwm'})

            if bridge_mode:
                label = {"idx": str(index), "mytsdk_network":network, "mytsdk_dns":dns1}        #用于记录当前的索引值
                # if 'imgpath' in config_dict:
                #     label['shType'] = 'yes'
                
                # if 'imgsize' in config_dict:
                #     label['shSize'] = str(config_dict['imgsize'])
        

                tcp_port = 10000 + index * 3
                udp_port = tcp_port + 1
                web_port = tcp_port + 2
                adb_port = 5000 + index
                api_port = 11010 + (index-1) * 10
                cam1_port = 11011 + (index-1) * 10
                cam2_port = 11012 + (index-1) * 10
                webrtc_tcp = 11013 + (index-1) * 10         #10002
                webrtc_udp = 11014 + (index-1) * 10         #10003  

                ports = {'5555/tcp': [{'HostPort': str(adb_port)}],
                                                        '9082/tcp': [{'HostPort': str(web_port)}],
                                                        '10000/tcp': [{'HostPort': str(tcp_port)}],
                                                        '10001/udp': [{'HostPort': str(udp_port)}],
                                                        '9083/tcp': [{'HostPort': str(api_port)}],
                                                        '10006/tcp': [{'HostPort': str(cam1_port)}],
                                                        '10007/udp': [{'HostPort': str(cam2_port)}],
                                                        '10002/tcp': [{'HostPort': str(webrtc_tcp)}],
                                                        '10003/udp': [{'HostPort': str(webrtc_udp)}],
                                                        }
                
                #增加自定义端口支持
                if 'tcp_map_port' in config_dict:
                    for k,v in config_dict['tcp_map_port'].items():
                        s = f"{v}/tcp"
                        ports[s] = [{'HostPort': str(k)}]
                    
                if 'udp_map_port' in config_dict:
                    for k,v in config_dict['udp_map_port'].items():
                        s = f"{v}/udp"
                        ports[s] = [{'HostPort': str(k)}]
                        
                ret = self.docker_client.containers.create(image, command, volumes=volumes, cap_add = cap_add, name = tid, sysctls= Sysctls, network_mode = network_mode, 
                                                         security_opt = security_opt, restart_policy = restart_policy,devices = device,device_cgroup_rules = cg_rules, 
                                                         ports = ports, auto_remove = False, privileged = False, detach=True,labels =label, mem_limit = memory, 
                                                         cpuset_cpus = cpuset,mac_address = mac)     

                
                #ret = True                    
            else:
                command.append(f"androidboot.ro.kernel.and_ip={docker_ip}")
                label = {"idx": str(index), "mytsdk_network":network, "mytsdk_ip":docker_ip, "mytsdk_dns":dns1}        #用于记录当前的索引值

                # if 'imgpath' in config_dict:
                #     label['shType'] = 'yes'
                #     label['shSize'] = str(config_dict['imgsize'])

                #关联IP
                ret = self.docker_client.containers.create(image, command, volumes=volumes, cap_add = cap_add, name = tid, sysctls= Sysctls,network = network,
                                                         security_opt = security_opt, restart_policy = restart_policy,devices = device,device_cgroup_rules = cg_rules, 
                                                         auto_remove = False, privileged = False, detach=True,labels =label, mem_limit = memory, 
                                                         cpuset_cpus = cpuset, mac_address = mac)      
                if ret :
                    #attach network
                    network_obj = self.docker_client.networks.get(network)
                    network_obj.disconnect(ret)
                    network_obj.connect(ret,  ipv4_address=docker_ip)
                    #ret = True

                #pass
               # data_dict['NetworkingConfig'] = {}
                #data_dict['NetworkingConfig']['EndpointsConfig'] = {
                 #   network: {'IPAddress': docker_ip, 'IPAMConfig': {'IPv4Address': docker_ip}, 'NetworkID': network_id}}
        

        except ImageNotFound:
            logger.debug(f"Image {self._ALPINE} 不存在")
            ret = False
        except APIError as e:
            logger.debug("API Error:" + str(e))
            ret = False
        except DockerException  as e:
            logger.debug("DockerException Error:"  + str(e))
            ret = False
        except Exception as e:
            logger.debug("Exception Error:" + str(e))
            ret = False
        
        if (ret == False)  and (bUpdateOpern == False):
            #删除资源目录
            # 如果是更新的时候  则不能删除
            if len(datares_folder)>0:
                file_path = os.path.dirname(datares_folder)
                cmd = "rm -rf  " + file_path
                self.SDK_SHELL_COMMAD(cmd)
        return ret



# 创建容器实例
#for qualcomm a1 modal
    def SDK_Create_container_a1(self,ip,config_dict, bUpdateOper = False):
        ret = False
        try:
            bridge_mode = False
            tid = config_dict['tid']
            index = config_dict['index']
            token = config_dict['token']
            
            #随机生成mac地址
            mac = self.random_mac()
            #开机时间作随机
            #t_offset = str(random.randint(86400*6, 86400*30))
            
            if 'timeoffset' in config_dict:
                t_offset = int(config_dict['timeoffset']) * 60
                t_offset = str(t_offset)
            else:
                t_offset = str(random.randint(86400*6, 86400*30))


            # config DNS
            if 'dns1' in config_dict:
                dns1 = config_dict['dns1']
            else:
                dns1 = '223.5.5.5'

            # config resolution
            if 'dobox_resolution' in config_dict:
                if config_dict['dobox_resolution'] == '720P':
                    dobox_width = '720'
                    dobox_height = '1280'
                    dobox_dpi = '320'
                elif config_dict['dobox_resolution'] == '1080P':
                    dobox_width = '1080'
                    dobox_height = '1920'
                    dobox_dpi = '480'
                elif config_dict['dobox_resolution'] == 'custom':
                    dobox_width = config_dict['dobox_resolution_detail']['width']
                    dobox_height = config_dict['dobox_resolution_detail']['height']
                    dobox_dpi = config_dict['dobox_resolution_detail']['dpi']
                else:
                    dobox_width = '720'
                    dobox_height = '1280'
                    dobox_dpi = '320'
            else:
                dobox_width = '720'
                dobox_height = '1280'
                dobox_dpi = '320'

            image = config_dict['image']
            binder_index = (index - 1) * 3 + 1
            #event_index =  index + 1
            data_index = index

            #记录资源目录 用于创建失败时删除目录
            datares_folder = ''
            if 'datapath' in config_dict:
                data_path = config_dict['datapath']  + ":/data"
                #mac = None
            else:
                str_time = time.strftime('%Y%m%d%H%M%S')
                random_number = random.randint(0, 999)
                str_time = f"{str_time}_{random_number:03d}"
                data_path = "/mmc/data/data" + str(data_index) + "_" + tid +  "_"+ str_time + "/data" + ":/data"
                datares_folder = "/mmc/data/data" + str(data_index) + "_" + tid +  "_"+ str_time + "/data" 

            #使用img 方式
            if 'imgpath' in config_dict:
                data_path = config_dict['imgpath']  + ":/userdata.img"
                datares_folder = config_dict['imgpath']
                #mac = None


            if 'memory' in config_dict:
                memory = config_dict['memory']
            else:
                memory = None

            if 'memoryswap' in config_dict:
                swap = config_dict['memoryswap']
            
            if 'cpuset' in config_dict:
                cpuset = config_dict['cpuset']
            else:
                cpuset = None

            if 'network' in config_dict:
                network = config_dict['network']
                #network_id = config_dict['network_id']
                docker_ip = config_dict['docker_ip']
            else:
                network = 'bridge'  # bridge
                bridge_mode = True

            if 'fps' in config_dict:
                fps = str(config_dict['fps'])
            else:
                fps = '24'

            if 'mac' in config_dict:
                mac = config_dict['mac']

            volumes = ["/dev/net/tun:/dev/tun",  data_path,"/usr/share/zoneinfo/Asia/Shanghai:/etc/localtime"]
    
       
            command = ["androidboot.hardware=qcom_a1",
                        "androidboot.dobox_fps=" + fps,
                        #"androidboot.selinux=permissive",
                        "qemu=1",
                        "androidboot.ro.kernel.syfToken=" + token,
                        "androidboot.ro.kernel.syfHost=" + ip,
                        "androidboot.dobox_net_ndns=1",
                        "androidboot.dobox_net_dns1=" + dns1,
                        "androidboot.dobox_width=" + dobox_width,
                        "androidboot.dobox_height=" + dobox_height,
                        "androidboot.dobox_dpi=" + dobox_dpi,
                        "androidboot.dobox_tag=" + token,
                        "androidboot.offset=" + t_offset,
                        #"androidboot.ro.rpa=7100",         rpa 主机端口
                        #"androidboot.ro.init.devinfo=4"    开机指定初始化设备型号
                        #"androidboot.dobox_debug=true"
                    ]
            
            #开机默认不随机
            if 'random_dev' in config_dict:
                if config_dict['random_dev'] == '0':
                    command.append("androidboot.nomodifydev=true")
            #dns tcp 模式
            if 'dnstcp_mode' in config_dict:
                if config_dict['dnstcp_mode'] == '1':
                    command.append("androidboot.dns_force_tcp=true")

            if 'rpa_port' in config_dict:
                command.append(f"androidboot.ro.rpa={config_dict['rpa_port']}")
                #volumes.append("/proc/1/ns/net:/dev/net")
                volumes.append("/proc/1/ns/net:/dev/mnetns")
            
            if 'init_dev' in config_dict:
                command.append(f"androidboot.ro.init.devinfo={config_dict['init_dev']}")
            
            if 'enforce' in config_dict:
                if config_dict['enforce'] == '0':
                    command.append(f"androidboot.selinux=permissive")

            #默认开启s5模式
            if 's5ip' in config_dict and 's5port' in config_dict and 's5pwd' in config_dict and 's5user' in config_dict:
                command.append("androidboot.s5_type=1")
                command.append(f"androidboot.s5_ip={config_dict['s5ip']}")
                command.append(f"androidboot.s5_port={config_dict['s5port']}")
                command.append(f"androidboot.s5_usr={config_dict['s5user']}")
                command.append(f"androidboot.s5_pwd={config_dict['s5pwd']}")

            cap_add = ["SYSLOG",
                        "AUDIT_CONTROL",
                        "SETGID",
                        "DAC_READ_SEARCH",
                        "SYS_ADMIN",
                        "NET_ADMIN",
                        "SYS_MODULE",
                        "SYS_NICE",
                        "SYS_TIME",
                        "SYS_TTY_CONFIG",
                        "NET_BROADCAST",
                        "IPC_LOCK",
                        "SYS_RESOURCE",
                        "SYS_PTRACE",
                        "WAKE_ALARM",
                        "BLOCK_SUSPEND",
                        "MKNOD"   # dm add
                        ]
            # Sysctls = {"net.ipv4.conf.eth0.rp_filter": "0", "net.ipv4.conf.all.rp_filter":"0"}
            Sysctls = {"net.ipv4.conf.all.rp_filter": "2"}
            network_mode = network
            security_opt = ["seccomp=unconfined"]
            restart_policy = {"Name": "unless-stopped", 'MaximumRetryCount': 0}
            device = [
                        {'PathOnHost': '/dev/binder' + str(binder_index), 'PathInContainer': '/dev/binder',
                        'CgroupPermissions': 'rwm'},
                        {'PathOnHost': '/dev/binder' + str(binder_index + 1), 'PathInContainer': '/dev/hwbinder',
                        'CgroupPermissions': 'rwm'},
                        {'PathOnHost': '/dev/binder' + str(binder_index + 2), 'PathInContainer': '/dev/vndbinder',
                        'CgroupPermissions': 'rwm'},
                        #{'PathOnHost': '/dev/tee0', 'PathInContainer': '/dev/tee0', 'CgroupPermissions': 'rwm'},
                        #{'PathOnHost': '/dev/teepriv0', 'PathInContainer': '/dev/teepriv0', 'CgroupPermissions': 'rwm'},
                        #{'PathOnHost': '/dev/crypto', 'PathInContainer': '/dev/crypto', 'CgroupPermissions': 'rwm'},
                        #{'PathOnHost': '/dev/mali0', 'PathInContainer': ' /dev/mali0', 'CgroupPermissions': 'rwm'},
                        #{'PathOnHost': '/dev/rga', 'PathInContainer': '/dev/rga', 'CgroupPermissions': 'rwm'},
                        {'PathOnHost': '/dev/dri', 'PathInContainer': '/dev/dri', 'CgroupPermissions': 'rwm'},
                        #{'PathOnHost': '/dev/mpp_service', 'PathInContainer': '/dev/mpp_service', 'CgroupPermissions': 'rwm'},
                        {'PathOnHost': '/dev/fuse', 'PathInContainer': '/dev/fuse', 'CgroupPermissions': 'rwm'},
                        #{'PathOnHost': '/dev/input/event' + str(event_index), 'PathInContainer': '/dev/input/event1', 'CgroupPermissions': 'rwm'},
                        {'PathOnHost': '/dev/input/event0', 'PathInContainer': '/dev/input/event0', 'CgroupPermissions': 'rwm'},
                        # {'PathOnHost': '/dev/input/event1', 'PathInContainer': '/dev/input/event1', 'CgroupPermissions': 'rwm'},
                        #{'PathOnHost': '/dev/dma_heap/cma', 'PathInContainer': '/dev/dma_heap/cma', 'CgroupPermissions': 'rwm'},
                        #{'PathOnHost': '/dev/dma_heap/cma-uncached', 'PathInContainer': '/dev/dma_heap/cma-uncached','CgroupPermissions': 'rwm'},
                        {'PathOnHost': '/dev/dma_heap/system', 'PathInContainer': '/dev/dma_heap/system','CgroupPermissions': 'rwm'},
                        #{'PathOnHost': '/dev/dma_heap/system-dma32', 'PathInContainer': '/dev/dma_heap/system-dma32','CgroupPermissions': 'rwm'},
                        #{'PathOnHost': '/dev/dma_heap/system-uncached', 'PathInContainer': '/dev/dma_heap/system-uncached','CgroupPermissions': 'rwm'},
                        #{'PathOnHost': '/dev/dma_heap/system-uncached-dma32','PathInContainer': '/dev/dma_heap/system-uncached-dma32', 'CgroupPermissions': 'rwm'},
                        {'PathOnHost': '/dev/ashmem', 'PathInContainer': '/dev/ashmem', 'CgroupPermissions': 'rwm'},
                        {'PathOnHost': '/dev/smcinvoke', 'PathInContainer': '/dev/smcinvoke', 'CgroupPermissions': 'rwm'},
                        {'PathOnHost': '/dev/dma_heap/qcom,system', 'PathInContainer': '/dev/dma_heap/qcom,system', 'CgroupPermissions': 'rwm'},
                        {'PathOnHost': '/dev/dma_heap/qcom,qseecom-ta', 'PathInContainer': '/dev/dma_heap/qcom,qseecom-ta', 'CgroupPermissions': 'rwm'},
                        {'PathOnHost': '/dev/video32', 'PathInContainer': '/dev/video32', 'CgroupPermissions': 'rwm'},
                        {'PathOnHost': '/dev/video33', 'PathInContainer': '/dev/video33', 'CgroupPermissions': 'rwm'},
                        {'PathOnHost': '/dev/kgsl-3d0', 'PathInContainer': '/dev/kgsl-3d0', 'CgroupPermissions': 'rwm'},
                        {'PathOnHost': '/dev/qseecom', 'PathInContainer': '/dev/qseecom', 'CgroupPermissions': 'rwm'},
                    ]
            cg_rules = ["c 10:* rmw", "b 253:* rmw", "b 7:* rmw", "c 240:* rmw", "b 254:* rmw"]
            
            

            if bridge_mode:
                label = {"idx": str(index), "mytsdk_network":network, "mytsdk_dns":dns1}        #用于记录当前的索引值
                if 'imgpath' in config_dict:
                    label['shType'] = 'yes'
                
                if 'imgsize' in config_dict:
                    label['shSize'] = str(config_dict['imgsize'])


                tcp_port = 10000 + index * 3
                udp_port = tcp_port + 1
                web_port = tcp_port + 2
                adb_port = 5000 + index
                api_port = 11010 + (index-1) * 10
                cam1_port = 11011 + (index-1) * 10
                cam2_port = 11012 + (index-1) * 10

                ports = {'5555/tcp': [{'HostPort': str(adb_port)}],
                                                        '9082/tcp': [{'HostPort': str(web_port)}],
                                                        '10000/tcp': [{'HostPort': str(tcp_port)}],
                                                        '10001/udp': [{'HostPort': str(udp_port)}],
                                                        '9083/tcp': [{'HostPort': str(api_port)}],
                                                        '10006/tcp': [{'HostPort': str(cam1_port)}],
                                                        '10007/udp': [{'HostPort': str(cam2_port)}],
                                                        }
                ret = self.docker_client.containers.create(image, command, volumes=volumes, cap_add = cap_add, name = tid, sysctls= Sysctls, network_mode = network_mode, 
                                                         security_opt = security_opt, restart_policy = restart_policy,devices = device,device_cgroup_rules = cg_rules, 
                                                         ports = ports, auto_remove = False, privileged = False, detach=True,labels =label, mem_limit = memory, 
                                                         cpuset_cpus = cpuset,mac_address = mac)     
                #ret = True                    
            else:
                label = {"idx": str(index), "mytsdk_network":network, "mytsdk_ip":docker_ip, "mytsdk_dns":dns1}        #用于记录当前的索引值
                if 'imgpath' in config_dict:
                    label['shType'] = 'yes'
                
                if 'imgsize' in config_dict:
                    label['shSize'] = str(config_dict['imgsize'])

                #关联IP
                ret = self.docker_client.containers.create(image, command, volumes=volumes, cap_add = cap_add, name = tid, sysctls= Sysctls,network = network,
                                                         security_opt = security_opt, restart_policy = restart_policy,devices = device,device_cgroup_rules = cg_rules, 
                                                         auto_remove = False, privileged = False, detach=True,labels =label, mem_limit = memory, 
                                                         cpuset_cpus = cpuset, mac_address = mac)      
                if ret :
                    #attach network
                    network_obj = self.docker_client.networks.get(network)
                    network_obj.disconnect(ret)
                    network_obj.connect(ret,  ipv4_address=docker_ip)
                    #ret = True

        except ImageNotFound:
            logger.debug(f"Image {self._ALPINE} 不存在")
            ret = False
        except APIError as e:
            logger.debug("API Error:" + str(e))
            ret = False
        except DockerException  as e:
            logger.debug("DockerException Error:"  + str(e))
            ret = False
        except Exception as e:
            logger.debug("Exception Error:" + str(e))
            ret = False
        
        if (ret == False) and (bUpdateOper == False):
            #删除资源目录
            if len(datares_folder)>0:
                file_path = os.path.dirname(datares_folder)
                cmd = "rm -rf  " + file_path
                self.SDK_SHELL_COMMAD(cmd)
        return ret


# 创建容器实例16202503140004    
#for qualcomm p1 modal
    def SDK_Create_container_p1(self,ip,config_dict, bUpdateOper = False):
        ret = False
        try:
            bridge_mode = False
            tid = config_dict['tid']
            index = config_dict['index']
            token = config_dict['token']
            
            #随机生成mac地址
            mac = self.random_mac()
            #开机时间作随机
            #t_offset = str(random.randint(86400*6, 86400*30))
            
            if 'timeoffset' in config_dict:
                t_offset = int(config_dict['timeoffset']) * 60
                t_offset = str(t_offset)
            else:
                t_offset = str(random.randint(86400*6, 86400*30))


            # config DNS
            if 'dns1' in config_dict:
                dns1 = config_dict['dns1']
            else:
                dns1 = '223.5.5.5'

            # config resolution
            if 'dobox_resolution' in config_dict:
                if config_dict['dobox_resolution'] == '720P':
                    dobox_width = '720'
                    dobox_height = '1280'
                    dobox_dpi = '320'
                elif config_dict['dobox_resolution'] == '1080P':
                    dobox_width = '1080'
                    dobox_height = '1920'
                    dobox_dpi = '480'
                elif config_dict['dobox_resolution'] == 'custom':
                    dobox_width = config_dict['dobox_resolution_detail']['width']
                    dobox_height = config_dict['dobox_resolution_detail']['height']
                    dobox_dpi = config_dict['dobox_resolution_detail']['dpi']
                else:
                    dobox_width = '720'
                    dobox_height = '1280'
                    dobox_dpi = '320'
            else:
                dobox_width = '720'
                dobox_height = '1280'
                dobox_dpi = '320'

            image = config_dict['image']
            binder_index = (index - 1) * 3 + 1
            #event_index =  index + 1
            data_index = index

            #记录资源目录 用于创建失败时删除目录
            datares_folder = ''
            if 'datapath' in config_dict:
                data_path = config_dict['datapath']  + ":/data"
                #mac = None
            else:
                str_time = time.strftime('%Y%m%d%H%M%S')
                random_number = random.randint(0, 999)
                str_time = f"{str_time}_{random_number:03d}"
                data_path = "/mmc/data/data" + str(data_index) + "_" + tid +  "_"+ str_time + "/data" + ":/data"
                datares_folder = "/mmc/data/data" + str(data_index) + "_" + tid +  "_"+ str_time + "/data" 

            #使用img 方式
            if 'imgpath' in config_dict:
                data_path = config_dict['imgpath']  + ":/userdata.img"
                datares_folder = config_dict['imgpath']
                #mac = None


            if 'memory' in config_dict:
                memory = config_dict['memory']
            else:
                memory = None

            if 'memoryswap' in config_dict:
                swap = config_dict['memoryswap']
            
            if 'cpuset' in config_dict:
                cpuset = config_dict['cpuset']
            else:
                cpuset = None

            if 'network' in config_dict:
                network = config_dict['network']
                #network_id = config_dict['network_id']
                docker_ip = config_dict['docker_ip']
            else:
                network = 'bridge'  # bridge
                bridge_mode = True

            if 'fps' in config_dict:
                fps = config_dict['fps']
            else:
                fps = '24'

            if 'mac' in config_dict:
                mac = config_dict['mac']

            volumes = ["/dev/net/tun:/dev/tun",  data_path,"/usr/share/zoneinfo/Asia/Shanghai:/etc/localtime"]
    
       
            command = ["androidboot.hardware=myt_p1",
                        "androidboot.dobox_fps=" + fps,
                        #"androidboot.selinux=permissive",
                        "androidboot.ro.kernel.syfToken=" + token,
                        "androidboot.ro.kernel.syfHost=" + ip,
                        "androidboot.dobox_net_ndns=1",
                        "androidboot.dobox_net_dns1=" + dns1,
                        "androidboot.dobox_width=" + dobox_width,
                        "androidboot.dobox_height=" + dobox_height,
                        "androidboot.dobox_dpi=" + dobox_dpi,
                        "androidboot.dobox_tag=" + token,
                        "androidboot.offset=" + t_offset,
                        #"androidboot.ro.rpa=7100",         rpa 主机端口
                        #"androidboot.ro.init.devinfo=4"    开机指定初始化设备型号
                        #"androidboot.dobox_debug=true"
                    ]
            
            #开机默认不随机
            if 'random_dev' in config_dict:
                if config_dict['random_dev'] == '0':
                    command.append("androidboot.nomodifydev=true")
            #dns tcp 模式
            if 'dnstcp_mode' in config_dict:
                if config_dict['dnstcp_mode'] == '1':
                    command.append("androidboot.dns_force_tcp=true")

            if 'rpa_port' in config_dict:
                command.append(f"androidboot.ro.rpa={config_dict['rpa_port']}")
                #volumes.append("/proc/1/ns/net:/dev/net")
                volumes.append("/proc/1/ns/net:/dev/mnetns")
            
            if 'init_dev' in config_dict:
                command.append(f"androidboot.ro.init.devinfo={config_dict['init_dev']}")
            
            if 'enforce' in config_dict:
                if config_dict['enforce'] == '0':
                    command.append(f"androidboot.selinux=permissive")

            #默认开启s5模式
            if 's5ip' in config_dict and 's5port' in config_dict and 's5pwd' in config_dict and 's5user' in config_dict:
                command.append("androidboot.s5_type=1")
                command.append(f"androidboot.s5_ip={config_dict['s5ip']}")
                command.append(f"androidboot.s5_port={config_dict['s5port']}")
                command.append(f"androidboot.s5_usr={config_dict['s5user']}")
                command.append(f"androidboot.s5_pwd={config_dict['s5pwd']}")

            cap_add = ["SYSLOG",
                        "AUDIT_CONTROL",
                        "SETGID",
                        "DAC_READ_SEARCH",
                        "SYS_ADMIN",
                        "NET_ADMIN",
                        "SYS_MODULE",
                        "SYS_NICE",
                        "SYS_TIME",
                        "SYS_TTY_CONFIG",
                        "NET_BROADCAST",
                        "IPC_LOCK",
                        "SYS_RESOURCE",
                        "SYS_PTRACE",
                        "WAKE_ALARM",
                        "BLOCK_SUSPEND",
                        "MKNOD"   # dm add
                        ]
            # Sysctls = {"net.ipv4.conf.eth0.rp_filter": "2", "net.ipv4.conf.all.rp_filter":"0"}
            Sysctls = {"net.ipv4.conf.eth0.rp_filter": "2"}
            network_mode = network
            security_opt = ["seccomp=unconfined"]
            restart_policy = {"Name": "unless-stopped", 'MaximumRetryCount': 0}
            device = [
                        {'PathOnHost': '/dev/binder' + str(binder_index), 'PathInContainer': '/dev/binder',
                        'CgroupPermissions': 'rwm'},
                        {'PathOnHost': '/dev/binder' + str(binder_index + 1), 'PathInContainer': '/dev/hwbinder',
                        'CgroupPermissions': 'rwm'},
                        {'PathOnHost': '/dev/binder' + str(binder_index + 2), 'PathInContainer': '/dev/vndbinder',
                        'CgroupPermissions': 'rwm'},
                        {'PathOnHost': '/dev/tee0', 'PathInContainer': '/dev/tee0', 'CgroupPermissions': 'rwm'},
                        {'PathOnHost': '/dev/teepriv0', 'PathInContainer': '/dev/teepriv0', 'CgroupPermissions': 'rwm'},
                        #{'PathOnHost': '/dev/crypto', 'PathInContainer': '/dev/crypto', 'CgroupPermissions': 'rwm'},
                        {'PathOnHost': '/dev/mali0', 'PathInContainer': ' /dev/mali0', 'CgroupPermissions': 'rwm'},
                        #{'PathOnHost': '/dev/rga', 'PathInContainer': '/dev/rga', 'CgroupPermissions': 'rwm'},
                        #{'PathOnHost': '/dev/dri', 'PathInContainer': '/dev/dri', 'CgroupPermissions': 'rwm'},
                        #{'PathOnHost': '/dev/mpp_service', 'PathInContainer': '/dev/mpp_service', 'CgroupPermissions': 'rwm'},
                        {'PathOnHost': '/dev/fuse', 'PathInContainer': '/dev/fuse', 'CgroupPermissions': 'rwm'},
                        #{'PathOnHost': '/dev/input/event' + str(event_index), 'PathInContainer': '/dev/input/event1', 'CgroupPermissions': 'rwm'},
                        {'PathOnHost': '/dev/null', 'PathInContainer': '/dev/input/event0', 'CgroupPermissions': 'rwm'},
                        # {'PathOnHost': '/dev/input/event1', 'PathInContainer': '/dev/input/event1', 'CgroupPermissions': 'rwm'},
                        #{'PathOnHost': '/dev/dma_heap/cma', 'PathInContainer': '/dev/dma_heap/cma', 'CgroupPermissions': 'rwm'},
                        #{'PathOnHost': '/dev/dma_heap/cma-uncached', 'PathInContainer': '/dev/dma_heap/cma-uncached','CgroupPermissions': 'rwm'},
                        {'PathOnHost': '/dev/dma_heap/system', 'PathInContainer': '/dev/dma_heap/system','CgroupPermissions': 'rwm'},
                        #{'PathOnHost': '/dev/dma_heap/system-dma32', 'PathInContainer': '/dev/dma_heap/system-dma32','CgroupPermissions': 'rwm'},
                        {'PathOnHost': '/dev/dma_heap/system-uncached', 'PathInContainer': '/dev/dma_heap/system-uncached','CgroupPermissions': 'rwm'},
                        #{'PathOnHost': '/dev/dma_heap/system-uncached-dma32','PathInContainer': '/dev/dma_heap/system-uncached-dma32', 'CgroupPermissions': 'rwm'},
                        {'PathOnHost': '/dev/ashmem', 'PathInContainer': '/dev/ashmem', 'CgroupPermissions': 'rwm'},
                        # {'PathOnHost': '/dev/smcinvoke', 'PathInContainer': '/dev/smcinvoke', 'CgroupPermissions': 'rwm'},
                        # {'PathOnHost': '/dev/dma_heap/qcom,system', 'PathInContainer': '/dev/dma_heap/qcom,system', 'CgroupPermissions': 'rwm'},
                        # {'PathOnHost': '/dev/dma_heap/qcom,qseecom-ta', 'PathInContainer': '/dev/dma_heap/qcom,qseecom-ta', 'CgroupPermissions': 'rwm'},
                        # {'PathOnHost': '/dev/video32', 'PathInContainer': '/dev/video32', 'CgroupPermissions': 'rwm'},
                        # {'PathOnHost': '/dev/video33', 'PathInContainer': '/dev/video33', 'CgroupPermissions': 'rwm'},
                        # {'PathOnHost': '/dev/kgsl-3d0', 'PathInContainer': '/dev/kgsl-3d0', 'CgroupPermissions': 'rwm'},
                        # {'PathOnHost': '/dev/qseecom', 'PathInContainer': '/dev/qseecom', 'CgroupPermissions': 'rwm'},
                        {'PathOnHost': '/dev/dri', 'PathInContainer': '/dev/dri', 'CgroupPermissions': 'rwm'},
                        {'PathOnHost': '/dev/video0', 'PathInContainer': '/dev/video0', 'CgroupPermissions': 'rwm'},
                        {'PathOnHost': '/dev/video1', 'PathInContainer': '/dev/video1', 'CgroupPermissions': 'rwm'},
                    ]
            cg_rules = ["c 10:* rmw", "b 252:* rmw", "b 7:* rmw"]
            
        
            if bridge_mode:
                label = {"idx": str(index), "mytsdk_network":network, "mytsdk_dns":dns1}        #用于记录当前的索引值
                if 'imgpath' in config_dict:
                    label['shType'] = 'yes'
                
                if 'imgsize' in config_dict:
                    label['shSize'] = str(config_dict['imgsize'])


                tcp_port = 10000 + index * 3
                udp_port = tcp_port + 1
                web_port = tcp_port + 2
                adb_port = 5000 + index
                api_port = 11010 + (index-1) * 10
                cam1_port = 11011 + (index-1) * 10
                cam2_port = 11012 + (index-1) * 10

                ports = {'5555/tcp': [{'HostPort': str(adb_port)}],
                                                        '9082/tcp': [{'HostPort': str(web_port)}],
                                                        '10000/tcp': [{'HostPort': str(tcp_port)}],
                                                        '10001/udp': [{'HostPort': str(udp_port)}],
                                                        '9083/tcp': [{'HostPort': str(api_port)}],
                                                        '10006/tcp': [{'HostPort': str(cam1_port)}],
                                                        '10007/udp': [{'HostPort': str(cam2_port)}],
                                                        }
                ret = self.docker_client.containers.create(image, command, volumes=volumes, cap_add = cap_add, name = tid, sysctls= Sysctls, network_mode = network_mode, 
                                                         security_opt = security_opt, restart_policy = restart_policy,devices = device,device_cgroup_rules = cg_rules, 
                                                         ports = ports, auto_remove = False, privileged = False, detach=True,labels =label, mem_limit = memory, 
                                                         cpuset_cpus = cpuset,mac_address = mac)                       
            else:
                label = {"idx": str(index), "mytsdk_network":network, "mytsdk_ip":docker_ip, "mytsdk_dns":dns1}        #用于记录当前的索引值
                if 'imgpath' in config_dict:
                    label['shType'] = 'yes'
                
                if 'imgsize' in config_dict:
                    label['shSize'] = str(config_dict['imgsize'])

                #关联IP
                ret = self.docker_client.containers.create(image, command, volumes=volumes, cap_add = cap_add, name = tid, sysctls= Sysctls,network = network,
                                                         security_opt = security_opt, restart_policy = restart_policy,devices = device,device_cgroup_rules = cg_rules, 
                                                         auto_remove = False, privileged = False, detach=True,labels =label, mem_limit = memory, 
                                                         cpuset_cpus = cpuset, mac_address = mac)      
                if ret :
                    #attach network
                    network_obj = self.docker_client.networks.get(network)
                    network_obj.disconnect(ret)
                    network_obj.connect(ret,  ipv4_address=docker_ip)
                    #ret = True


        except ImageNotFound:
            logger.debug(f"Image {self._ALPINE} 不存在")
            ret = False
        except APIError as e:
            logger.debug("API Error:" + str(e))
            ret = False
        except DockerException  as e:
            logger.debug("DockerException Error:"  + str(e))
            ret = False
        except Exception as e:
            logger.debug("Exception Error:" + str(e))
            ret = False
        
        if (ret == False) and (bUpdateOper == False):
            #删除资源目录
            if len(datares_folder)>0:
                file_path = os.path.dirname(datares_folder)
                cmd = "rm -rf  " + file_path
                self.SDK_SHELL_COMMAD(cmd)
        return ret



    """检查网络"""
    def check_network(self, ip, gate, subnet, eth_name):
        if self.SDK_exits_network(self._NETWORK) == False:
            if self.SDK_create_macvlan(self._NETWORK, subnet, gate, eth_name) == True:
                ret = True
            else:
                ret = False
        else:
            ret = True
        return ret

    """获取网络ID"""
    def get_network_ID(self):
        return  self.SDK_get_network_id(self._NETWORK)

    """获取指定容器对象的 数据 目录"""
    # 获取资源文件映射 目录
    def get_data_dir(self,  c_name, bfull = False):
        ret = ''
        arr = self.SDK_get_contianer_attr(c_name)
        if arr != False:
            for m in arr['Mounts']:
                if m['Destination'] == "/data":
                    filepath = m['Source']
                    if bfull:
                        ret = filepath
                    else:
                        ret = filepath.rstrip('/data')
                    break
                elif  m['Destination'] == "/userdata.img" : #添加img 支持
                    filepath = m['Source']
                    ret = filepath
        return ret
    

    # 执行Linux shell 命令 并返回结果
    def shell_cmd(self, ip, cmdline):
        ret = False
        if cmdline != '':
            logger.debug(f"shell_cmd cmd={cmdline}")
            ret = self.SDK_SHELL_COMMAD(cmdline)
        return ret 

    #实现稀疏镜像的拷贝
    # src  dest  : full path
    def SDK_COPY_IMG(self, src, dest):
        ret = False
        self.check_alpine_img()
        try:
            volumes = {
                        '/': {
                            'bind': '/host/',
                            'mode': 'rw'
                        }
                    }
            t_src = "/host" + src
            t_dest = "/host" + dest
            command = "cp --sparse=always " + t_src + " " + t_dest
            c = self.docker_client.containers.run(self._ALPINE, command, volumes=volumes,auto_remove = True, privileged = True, detach=True)
            ret = True
        except ImageNotFound:
            logger.debug(f"Image {self._ALPINE} 不存在")
            ret = False
        except APIError as e:
            logger.debug("API Error:" + str(e))
            ret = False
        except DockerException  as e:
            logger.debug("DockerException Error:" + str(e))
            ret = False
        except Exception as e:
            logger.debug("Exception Error:" + str(e))
            ret = False
        return ret

    # 实现docker run
    #    ret = False
    def SDK_SHELL_COMMAD(self, cmd):
        self.check_alpine_img()
        try:
            volumes = {
                        '/': {
                            'bind': '/host/',
                            'mode': 'rw'
                        }
                    }
            command = f'nsenter --mount=/host/proc/1/ns/mnt bash -c "{cmd}"'
            c = self.docker_client.containers.run(self._ALPINE, command, volumes=volumes,auto_remove = False, privileged = True, detach=True)
            ret = c.logs().decode('utf-8')
            c.wait()
            c.remove()
        except ImageNotFound:
            logger.debug(f"Image {self._ALPINE} 不存在")
            ret = False
        except APIError as e:
            logger.debug("API Error:" + str(e))
            ret = False
        except DockerException  as e:
            logger.debug("DockerException Error:" + str(e))
            ret = False
        except Exception as e:
            logger.debug("Exception Error:" + str(e))
            ret = False
        return ret
    
        # 实现docker run
    #    ret = False
    def SDK_SHELL_COMMAD_HOST(self, cmd, bAutoRemove = False):
        self.check_alpine_img()
        try:
            volumes = {
                        '/': {
                            'bind': '/host/',
                            'mode': 'rw'
                        }
                    }
            command = f'nsenter --mount=/host/proc/1/ns/mnt bash -c "{cmd}"'
            c = self.docker_client.containers.run(self._ALPINE, command, volumes=volumes,auto_remove = bAutoRemove, privileged = True, detach=True, network_mode='host')
            c.wait()
            ret = c.logs().decode('utf-8')
            c.remove()
        except ImageNotFound:
            logger.debug(f"Image {self._ALPINE} 不存在")
            ret = False
        except APIError as e:
            logger.debug("API Error:" + str(e))
            ret = False
        except DockerException  as e:
            logger.debug("DockerException Error:" + str(e))
            ret = False
        except Exception as e:
            logger.debug("Exception Error:" + str(e))
            ret = False
        return ret

    #创建macvlan
    def SDK_create_macvlan(self, network_name, subnet, gateway, parent_eth):
        try:
            ret = True
            ipam_pool = docker.types.IPAMPool(
                subnet=subnet,
                gateway=gateway
            )
            ipam_config = docker.types.IPAMConfig(
                pool_configs=[ipam_pool]
            )
            network = self.docker_client.networks.create(
                            network_name,
                            driver="macvlan",
                            options={
                                #"parent": "enp1s0"
                                "parent": parent_eth
                            },
                            ipam=ipam_config
                        )
        except APIError as e:
            logger.debug("API Error:" + str(e))
            ret = False
        except DockerException  as e:
            logger.debug("DockerException Error:" + str(e))
            ret = False
        except Exception as e:
            logger.debug("Exception Error:" + str(e))
            ret = False
        return ret
        

    #判断是否存在网络
    def SDK_exits_network(self, network_name):
        try:
            networks = self.docker_client.networks.list(names=[network_name])
            ret = (len(networks) > 0)
        except APIError as e:
            logger.debug("API Error:" + str(e))
            ret = False
        except DockerException  as e:
            logger.debug("DockerException Error:" + str(e))
            ret = False
        except Exception as e:
            logger.debug("Exception Error:" + str(e))
            ret = False
        return ret
    
    #获取网络的ID
    def SDK_get_network_id(self, network_name):
        try:
            # ret = True
            network = self.docker_client.networks.get(network_name)
            ret = network.id
        except NotFound:
            logger.debug(f"network {network_name} 不存在")
            ret = False   
        except APIError as e:
            logger.debug("API Error:" + str(e))
            ret = False
        except DockerException  as e:
            logger.debug("DockerException Error:" + str(e))
            ret = False
        except Exception as e:
            logger.debug("Exception Error:" + str(e))
            ret = False
        return ret
    
    #删除网络对象
    def SDK_remove_network(self, network_name):
        ret = False
        try:
            # 获取网络对象（通过名称）
            network = self.docker_client.networks.get(network_name)
            # 删除网络
            network.remove()
            ret = True
            logger.debug(f"Network '{network_name}' has been successfully removed.")
        except NotFound:
            logger.debug(f"Network {network_name} 不存在")
            ret = True   
        except APIError as e:
            logger.debug("API Error:" + str(e))
            ret = False
        except DockerException  as e:
            logger.debug("DockerException Error:" + str(e))
            ret = False
        except Exception as e:
            logger.debug("Exception Error:" + str(e))
            ret = False
        return ret
    
    #获取网络对象的详情
    def SDK_get_network_info(self, network_name):
        try:
            ret = False
            network = self.docker_client.networks.get(network_name)
            # logger.debug(network.attrs)
            ret = network.attrs
        except NotFound:
            logger.debug(f"network {network_name} 不存在")
            ret = False   
        except APIError as e:
            logger.debug("API Error:" + str(e))
            ret = False
        except DockerException  as e:
            logger.debug("DockerException Error:" + str(e))
            ret = False
        except Exception as e:
            logger.debug("Exception Error:" + str(e))
            ret = False
        return ret



    # 运行容器
    def SDK_start_continer(self, c_name):
        try:
            ret = True
            c = self.docker_client.containers.get(c_name)
            c.start()
            # logger.debug(c.labels)
        except NotFound:
            logger.debug(f"containers {c_name} 不存在")
            ret = False   
        except APIError as e:
            logger.debug("API Error:" + str(e))
            ret = False
        except DockerException  as e:
            logger.debug("DockerException Error:" + str(e))
            ret = False
        except Exception as e:
            logger.debug("Exception Error:" + str(e))
            ret = False
        return ret   
    
        # 重启容器
    def SDK_reboot_continer(self, c_name):
        try:
            ret = True
            c = self.docker_client.containers.get(c_name)
            c.restart()
            # logger.debug(c.labels)
        except NotFound:
            logger.debug(f"containers {c_name} 不存在")
            ret = False   
        except APIError as e:
            logger.debug("API Error:" + str(e))
            ret = False
        except DockerException  as e:
            logger.debug("DockerException Error:" + str(e))
            ret = False
        except Exception as e:
            logger.debug("Exception Error:" + str(e))
            ret = False
        return ret   


    #获取当前仓库的镜像列表
    def SDK_list_image(self,repository_name = None):
        try:
            ret = self.docker_client.images.list(name=repository_name)
        except APIError as e:
            logger.debug("API Error:" + str(e))
            ret = False
        except DockerException  as e:
            logger.debug("DockerException Error:" + str(e))
            ret = False
        except Exception as e:
            logger.debug("Exception Error:" + str(e))
            ret = False
        return ret
    # 拉取镜像
    def SDK_pull_image(self, img):
        try:
            self.docker_client.images.pull(img)
            ret = True
        except ImageNotFound:
            logger.debug(f"Image {img} 不存在")
            ret = False
        except APIError as e:
            logger.debug("API Error:" + str(e))
            ret = False
        except DockerException  as e:
            logger.debug("DockerException Error:" + str(e))
            ret = False
        except Exception as e:
            logger.debug("Exception Error:" + str(e))
            ret = False
        return ret

    # 执行关闭容器
    def SDK_stop_continer(self, c_name):
        try:
            ret = True
            c = self.docker_client.containers.get(c_name)
            c.stop()
            # logger.debug(c.labels)
        except NotFound:
            logger.debug(f"containers {c_name} 不存在")
            ret = False
        except APIError as e:
            logger.debug("API Error:" + str(e))
            ret = False
        except DockerException  as e:
            logger.debug("DockerException Error:" + str(e))
            ret = False
        except Exception as e:
            logger.debug("Exception Error:" + str(e))
            ret = False
        return ret
    
    # wait
    def SDK_wait_continer(self, c_name):
        try:
            ret = True
            c = self.docker_client.containers.get(c_name)
            c.wait()
            # logger.debug(c.labels)
        except NotFound:
            logger.debug(f"containers {c_name} 不存在")
            ret = False
        except APIError as e:
            logger.debug("API Error:" + str(e))
            ret = False
        except DockerException  as e:
            logger.debug("DockerException Error:" + str(e))
            ret = False
        except Exception as e:
            logger.debug("Exception Error:" + str(e))
            ret = False
        return ret
    
    # 执行删除容器
    def SDK_rm_continer(self, c_name):
        try:
            ret = True
            c = self.docker_client.containers.get(c_name)
            c.remove()
            # logger.debug(c.labels)
        except NotFound:
            logger.debug(f"containers {c_name} 不存在")
            ret = False
        except DockerException  as e:
            logger.debug("DockerException Error:" + str(e))
            ret = False
        except APIError as e:
            logger.debug("API Error:" + str(e))
            ret = False
        except Exception as e:
            logger.debug("Exception Error:" + str(e))
            ret = False

        return ret
    
    # 获取容器的属性数据
    def SDK_get_contianer_attr(self, c_name):
        try:
            c = self.docker_client.containers.get(c_name)
            ret = c.attrs
        except NotFound:
            logger.debug(f"containers {c_name} 不存在")
            ret = False    
        except APIError as e:
            logger.debug("API Error:" + str(e))
            ret = False
        except DockerException  as e:
            logger.debug("DockerException Error:" + str(e))
            ret = False
        except Exception as e:
            logger.debug("Exception Error:" + str(e))
            ret = False
        return ret

    # 判断容器是否存在
    def SDK_exits_contianer(self, c_name):
        ret = True
        try:
            # 获取容器对象
            container =  self.docker_client.containers.get(c_name)
        except NotFound:
            logger.debug(f"containers {c_name} 不存在")
            ret = False
        except APIError as e:
            logger.debug("API Error:" + str(e))
            ret = False
        except DockerException  as e:
            logger.debug("DockerException Error:" + str(e))
            ret = False
        except Exception as e:
            logger.debug("Exception Error:" + str(e))
            ret = False
        return ret
    
        # 判断容器是否存在
    def SDK_get_contianer(self, c_name):
        ret = True
        try:
            # 获取容器对象
            container =  self.docker_client.containers.get(c_name)
            ret = container
        except NotFound:
            logger.debug(f"containers {c_name} 不存在")
            ret = False
        except APIError as e:
            logger.debug("API Error:" + str(e))
            ret = False
        except DockerException  as e:
            logger.debug("DockerException Error:" + str(e))
            ret = False
        except Exception as e:
            logger.debug("Exception Error:" + str(e))
            ret = False
        return ret
    
    #重命名容器
    def SDK_rename_contianer(self, c_name, new_name):
        try:
            c = self.docker_client.containers.get(c_name)
            c.rename(new_name)
            ret = True
        except NotFound:
            logger.debug(f"containers {c_name} 不存在")
            ret = False
        except APIError as e:
            logger.debug("APIError:" + str(e))
            ret = False
        return ret

    # 判断是否镜像列表
    def SDK_exits_image(self, image_url):
        ret = True
        try:
            self.docker_client.images.get(image_url)
        except ImageNotFound:
            logger.debug(f"Image {image_url} 不存在")
            ret = False
        except APIError as e:
            logger.debug("API Error:" + str(e))
            ret = False
        except DockerException  as e:
            logger.debug("DockerException Error:" + str(e))
            ret = False
        except Exception as e:
            logger.debug("Exception Error:" + str(e))
            ret = False
        return ret  

    # 判断是否镜像列表
    def SDK_image_save(self, image_url, local_path):
        ret = True
        try:
            img = self.docker_client.images.get(image_url)
            f = open(local_path, 'wb')
            for chunk in img.save():
                f.write(chunk)
            f.close()
        except ImageNotFound:
            logger.debug(f"Image {image_url} 不存在")
            ret = False
        except APIError as e:
            logger.debug("API Error:" + str(e))
            ret = False
        except DockerException  as e:
            logger.debug("DockerException Error:" + str(e))
            ret = False
        except Exception as e:
            logger.debug("Exception Error:" + str(e))
            ret = False
        return ret  
    
    # 运行指定容器并返回运行结果
    def SDK_get_run_contianer_result(self, c_name):
        try:
            c = self.docker_client.containers.get(c_name)
            c.start()
            c.wait()
            ret = c.logs()
        except NotFound:
            logger.debug(f"containers {c_name} 不存在")
            ret = False
        except APIError as e:
            logger.debug("API Error:" + str(e))
            ret = False
        except DockerException  as e:
            logger.debug("DockerException Error:" + str(e))
            ret = False
        except Exception as e:
            logger.debug("Exception Error:" + str(e))
            ret = False
        return ret  

    #拷贝文件到容器中
    def SDK_copy_file_2_contianer(self, c_name, Src, Dest):
        try:
            c = self.docker_client.containers.get(c_name)
            with open(Src,'rb') as f:
                ret = c.put_archive( Dest, f.read())
        except NotFound as e:
            logger.debug(f"containers {c_name} 不存在")
            logger.debug("DockerException Error:" + str(e))
            ret = False
        except APIError as e:
            logger.debug("API Error:" + str(e))
            ret = False
        except DockerException  as e:
            logger.debug("DockerException Error:" + str(e))
            ret = False
        except Exception as e:
            logger.debug("Exception Error:" + str(e))
            ret = False
        return ret    
    


    #獲取列表
    def SDK_contianer_list(self, ball = False):
        try:
            ret=self.docker_client.containers.list(sparse=True, all= ball)            
        except APIError as e:
            logger.debug("API Error:" + str(e))
            ret = False
        except DockerException  as e:
            logger.debug("DockerException Error:" + str(e))
            ret = False
        except Exception as e:
            logger.debug("Exception Error:" + str(e))
            ret = False
        return ret 

    #ping
    def SDK_Ping(self):
        ret = True
        try:
            ret = self.docker_client.ping()
        except APIError as e:
            logger.debug("API Error:" + str(e))
            ret = False
        except DockerException  as e:
            logger.debug("DockerException Error:" + str(e))
            ret = False
        except Exception as e:
            logger.debug("Exception Error:" + str(e))
            ret = False
        return ret 
    
    #exec
    def SDK_contianer_exec(self, c_name, cmd, detach = False):
        ret = True
        try:
            # 获取容器对象
            container =  self.docker_client.containers.get(c_name)
            if detach == False:
                ret = container.exec_run(cmd,  tty = True)
            else:
                ret = container.exec_run(cmd, detach=detach, privileged = True)
        except NotFound:
            logger.debug(f"containers {c_name} 不存在")
            ret = False
        except APIError as e:
            logger.debug("API Error:" + str(e))
            ret = False
        except DockerException  as e:
            logger.debug("DockerException Error:" + str(e))
            ret = False
        except Exception as e:
            logger.debug("Exception Error:" + str(e))
            ret = False
        return ret
    

    #创建一个工具容器
    def SDK_CREATE_ALPINE(self, name, cmd, auto_remove = True, image = None):
        ret = False
        self.check_alpine_img()
        try:
            volumes = {
                        '/': {
                            'bind': '/host/',
                            'mode': 'rw'
                        }
                    }
            command = cmd
            if image == None:
                img = self._ALPINE
            else:
                img = image

            c = self.docker_client.containers.run(img, command, volumes=volumes,auto_remove = auto_remove, privileged = True, detach=True, name = name)
            ret = c

        except ImageNotFound:
            logger.debug(f"Image {self._ALPINE} 不存在")
            ret = False
        except APIError as e:
            logger.debug("API Error:" + str(e))
            ret = False
        except DockerException  as e:
            logger.debug("DockerException Error:" + str(e))
            ret = False
        except Exception as e:
            logger.debug("Exception Error:" + str(e))
            ret = False
        return ret


    def SDK_EXPORT(self, file_path, local_path):
        ret = False
        self.check_alpine_img()
        try:
            volumes = {
                        '/': {
                            'bind': '/data/',
                            'mode': 'rw'
                        }
                    }
            command = "tail -f /dev/null"
            c = self.docker_client.containers.run(self._ALPINE, command, volumes=volumes,auto_remove = True, privileged = True, detach=True)
            f = open(local_path, 'wb')
            bits, stat = c.get_archive('/data/' + file_path)
            for chunk in bits:
                f.write(chunk)
            ret = True
        except ImageNotFound:
            logger.debug(f"Image {self._ALPINE} 不存在")
            ret = False
        except APIError as e:
            logger.debug("API Error:" + str(e))
            ret = False
        except DockerException  as e:
            logger.debug("DockerException Error:" + str(e))
            ret = False
        except Exception as e:
            logger.debug("Exception Error:" + str(e))
            ret = False
            self.docker_client.close()
        finally:
            f.close()
            #由于stop 会抛出异常 必须嵌套使用一个方法做处理
            self._internal_stop_container(c)
        return ret
    
    def _internal_stop_container(self,c, time_out = 10):
        ret = False
        try:
            c.stop(timeout = time_out)
            ret = True
        except ImageNotFound:
            logger.debug(f"Image {self._ALPINE} 不存在")
            ret = False
        except APIError as e:
            logger.debug("API Error:" + str(e))
            ret = False
        except DockerException  as e:
            logger.debug("DockerException Error:" + str(e))
            ret = False
        except Exception as e:
            logger.debug("Exception Error:" + str(e))
            ret = False
        # finally:
        #     self.docker_client.close()
        return ret
    
    #导入文件到Linux主机目录
    def SDK_IMPORT_RES(self, local_file, remot_path):
        ret = False
        self.check_alpine_img()
        try:
            volumes = {
                        '/': {
                            'bind': '/data/',
                            'mode': 'rw'
                        }
                    }
            command = "tail -f /dev/null"
            c = self.docker_client.containers.run(self._ALPINE, command, volumes=volumes,auto_remove = True, privileged = True, detach=True)
            c.exec_run(" mkdir /data/" + remot_path)
            data = open(local_file, "rb")
            ret = c.put_archive( "/data/" + remot_path, data) 
            #c.stop()
            ret = True
        except ImageNotFound:
            logger.debug(f"Image {self._ALPINE} 不存在")
            ret = False
        except APIError as e:
            logger.debug("API Error:" + str(e))
            ret = False
        except DockerException  as e:
            logger.debug("DockerException Error:" + str(e))
            ret = False
        except Exception as e:
            logger.debug("Exception Error:" + str(e))
            ret = False
        finally:
            self._internal_stop_container(c)
        return ret
    
    #获取网络的ID
    def SDK_get_network_cfg(self, network_name):
        try:
            # ret = True
            network = self.docker_client.networks.get(network_name)
            ret = network.attrs['IPAM']['Config']
        except NotFound:
            logger.debug(f"network {network_name} 不存在")
            ret = False   
        except APIError as e:
            logger.debug("API Error:" + str(e))
            ret = False
        except DockerException  as e:
            logger.debug("DockerException Error:" + str(e))
            ret = False
        except Exception as e:
            logger.debug("Exception Error:" + str(e))
            ret = False
        return ret
    
    #获取指定容器的配置信息
    def SDK_get_container_config_detail(self, c_name):
        try:
            c = self.docker_client.containers.get(c_name)
            ret = {}
            mode = c.attrs['HostConfig']['NetworkMode']
            
            #from datetime import datetime
            
            date_time_str = c.attrs['State']['StartedAt']
            
            dt_obj = parser.isoparse(date_time_str)  # 自动截断到6位 linux兼容方法
            #dt_obj = datetime.fromisoformat(date_time_str)
 
            # 获取 UNIX 时间戳
            timestamp = dt_obj.timestamp()

            # 获取当前时间的时间戳
            timestamp_now = int(time.time())

            # 计算开机时间
            ret['uptime'] = int(timestamp_now - timestamp)

            #获取index 索引值
            # 这里c.attrs['HostConfig']['Devices'] != None 的时候会报错所以在这边加了一个判断
            if c.attrs['HostConfig']['Devices'] != None:
                for item in c.attrs['HostConfig']['Devices']:
                    for vk in item:
                        if item[vk] == '/dev/binder':
                            s = item['PathOnHost']
                            str_index = s[len('/dev/binder'): len(s)]
                            i_index = int(str_index)
                            ret['index'] = int((i_index -1) / 3 +1)
                            #print(str_index)
                            break
            
            #判断是否是沙盒模式
            #print(c.attrs['HostConfig']['Binds'])
            ret['sandbox'] = 0
            for item in c.attrs['HostConfig']['Binds']:
                if 'userdata.img' in item:
                    ret['sandbox'] = 1
                    break
                
            ret['name'] = c.name
            ret['id'] = c.id
            ret['status'] = c.status
            #获取内存
            ret['memory'] = c.attrs['HostConfig']['Memory']
            #cpu
            ret['cpuset'] = c.attrs['HostConfig']['CpusetCpus']
            
            #print(c.attrs['Args'])
            for item in c.attrs['Args']:
                lst = item.split("=")
                if lst[0] == "androidboot.dobox_net_dns1":
                    ret['dns'] = lst[1]
                elif lst[0] == "androidboot.dobox_width":
                    ret['width'] = lst[1]
                elif lst[0] == "androidboot.dobox_height":
                    ret['height'] = lst[1]
                elif lst[0] == "androidboot.dobox_dpi":
                    ret['dpi'] = lst[1]
                elif lst[0] == 'androidboot.dobox_fps':
                    ret['fps'] = lst[1]
                elif lst[0] == 'androidboot.ro.rpa':
                    ret['rpa'] = lst[1]
                elif lst[0] == 'androidboot.hardware':
                    ret['hardware'] = lst[1]
                elif lst[0] == 'androidboot.ro.sysext':
                    ret['hostapi_port'] = lst[1]
                elif lst[0] == 'androidboot.ro.hwcodec':
                    ret['hostvideo_port'] = lst[1] 
                elif lst[0] == 'androidboot.dns_force_tcp':
                    ret['dnstcp_mode'] = '1'
  
            #记录当前所有的参数信息
            ret['Args'] = c.attrs['Args']    
            ret['Devices'] = c.attrs['HostConfig']['Devices']

            
            if len(c.image.tags)>0:
                ret['image'] = c.image.tags[0]
            else:
                ret['image'] = ''

            if mode == 'myt':
                ip = c.attrs['NetworkSettings']['Networks']['myt']['IPAMConfig']['IPv4Address']
            else:
                ip = ''
                ret['local_ip'] = c.attrs['NetworkSettings']['IPAddress']
            
            ret['network'] = mode
            ret['ip'] = ip
        except NotFound:
            logger.debug(f"containers {c_name} 不存在")
            ret = False    
        except APIError as e:
            logger.debug("API Error:" + str(e))
            ret = False
        except DockerException  as e:
            logger.debug("DockerException Error:" + str(e))
            ret = False
        except Exception as e:
            #logger.debug("Exception Error:" + str(e))
            ret = False
        return ret

    #在Android容器通过wget 下载  文件 
    def SDK_wget_file_to_andorid(self,c_name, src, dest, retry = None):
        ret = False
        msg = ''
        try:
            # 获取容器对象
            container =  self.docker_client.containers.get(c_name)
            #cmd = f" sd -c ' busybox wget {src} -O {dest}'"
            if retry == None:
                cmd = f" sd -c ' curl  \"{src}\"  -o {dest}'"
            else:
                cmd = f" sd -c ' curl  --retry {retry} \"{src}\"  -o {dest}'"
            logger.debug(f"{cmd}")
            exec_ret = container.exec_run(cmd)
            if exec_ret.exit_code == 0:
                ret = True
            else:
                logger.debug(f"SDK_wget_file_to_andorid exec_ret:{exec_ret.output.decode('utf-8')} ")
                msg = f"code = {exec_ret}  {exec_ret.output.decode('utf-8')}"
            #ret = container
        except NotFound:
            logger.debug(f"containers {c_name} 不存在")
            msg = f"containers {c_name} 不存在"
            ret = False
        except APIError as e:
            logger.debug("API Error:" + str(e))
            msg = f"API Error:{e}"
            ret = False
        except DockerException  as e:
            logger.debug("DockerException Error:" + str(e))
            msg = f"DockerException Error:{e}"
            ret = False
        except Exception as e:
            logger.debug("Exception Error:" + str(e))
            msg = f"Exception Error:{e}"
            ret = False
        return ret,msg
    
    #运行apk
    def SDK_run_app(self, c_name, pkg):
        ret = True
        try:
            # 获取容器对象
            container =  self.docker_client.containers.get(c_name)
            cmd1 = f"sd -c \" dumpsys package {pkg} | grep activity |  "
            cmd2 = ' awk ' + " \'{print $2}\'" + ' " '
            cmd = cmd1 + cmd2
            exec_ret = container.exec_run(cmd)
            if exec_ret.exit_code == 0:
                out = exec_ret.output.decode('utf-8').strip()
                out.replace('"','',2)
                print(out)
                cmd = f" am start -n {out} "
                cmd3 = f"sd -c \"{cmd} \""
                exec_ret2 = container.exec_run(cmd3, tty = True)
                if exec_ret2.exit_code == 0:
                    ret = True
                else:
                    logger.debug(f"SDK_run_app exec_ret:{exec_ret2.output.decode('utf-8')} ")
            else:
                 logger.debug(f"SDK_wget_file_to_andorid exec_ret:{exec_ret.output.decode('utf-8')} ")
            #ret = container
        except NotFound:
            logger.debug(f"containers {c_name} 不存在")
            ret = False
        except APIError as e:
            logger.debug("API Error:" + str(e))
            ret = False
        except DockerException  as e:
            logger.debug("DockerException Error:" + str(e))
            ret = False
        except Exception as e:
            logger.debug("Exception Error:" + str(e))
            ret = False
        return ret  

    #获取坑位正在运行的容器
    def SDK_get_Running_container_by_index(self, index):
        ret = None
        r = self.SDK_contianer_list(True)
        if r != False:
            while len(r)>0:
                c = r.pop()
                if c == None:
                    break
                else:
                    name = c.attrs['Names'][0]
                    str_name = str(name)
                    real_name = str_name.replace(str_name[0], "", 1)
                    
                    if c.attrs['State'] == 'running':
                        if 'idx' in c.attrs['Labels']:
                            if c.attrs['Labels']['idx'] == str(index):
                                ret = real_name
                                break
        return ret

    #获取当前已经安装的插件信息列表
    def SDK_get_plugin_container(self):
        arr = []
        r = self.SDK_contianer_list(True)
        if r != False:
            while len(r)>0:
                c = r.pop()
                if c == None:
                    break
                else:                    
                    if 'myt_plugin_id' in c.attrs['Labels']:
                        att = {}
                        att['myt_plugin_id'] = c.attrs['Labels']['myt_plugin_id'] 
                        att['myt_plugin_ver'] = c.attrs['Labels']['myt_plugin_ver']
                        att['myt_plugin_name'] = c.attrs['Labels']['myt_plugin_name']
                        att['status'] = c.status
                        arr.append(att)
        return arr
    
    #获取指定容器的API端口
    def SDK_get_container_api_http(self, c_name, ip):
        cfg = self.SDK_get_container_config_detail(c_name)

        if cfg == False or cfg['status'] != 'running':
            ret = None
        else:
            # if 'hostapi_port' in cfg:           #使用主机端口
            #     ret = {'ip':ip, 'port':str(cfg['hostapi_port'])}
            # else:
            index = cfg['index']
            if cfg['network'] == 'myt':
                ret = {'ip':cfg['ip'], 'port':'9082'}   #f"http://{cfg['ip']}:9082/"
            else:
                port = 10000 + index * 3 + 2
                ret = {'ip':ip, 'port':str(port)}  #f"http://{cfg['ip']}:{port}/"
        return ret
    
    #设置应用开机启动
    def SDK_set_autorun_app(self, c_name,apk_package):
        ret = True
        try:
            # 获取容器对象
            container =  self.docker_client.containers.get(c_name)
            arr = []
            arr.append(apk_package)
            json_str = json.dumps(arr)
            json_str = f'[{apk_package}]'
            cmd1 = f'echo "{json_str}"  > /data/run/autoapp.txt'
            cmd = f" sd -c '{cmd1}'"
            ret = container.exec_run(cmd)
            #ret = container
        except NotFound:
            logger.debug(f"containers {c_name} 不存在")
            ret = False
        except APIError as e:
            logger.debug("API Error:" + str(e))
            ret = False
        except DockerException  as e:
            logger.debug("DockerException Error:" + str(e))
            ret = False
        except Exception as e:
            logger.debug("Exception Error:" + str(e))
            ret = False
        return ret
    
    #随机生成mac地址
    def random_mac(self):
        mac_arr = ["58:CB:52","7C:D9:5C","3C:8D:20","88:3D:24","98:D2:93","3C:5A:B4","F4:F5:E8","94:EB:2C","D4:F5:47","F0:72:EA","B0:E4:D5","60:B7:6E","08:B4:B1","24:29:34","60:70:6C","C8:2A:DD","20:DF:B9","44:07:0B","30:FD:38","E4:F0:42","94:95:A0","00:1A:11","88:54:1F","90:0C:C8","58:24:29","E4:5E:1B","14:22:3B","90:CA:FA","F0:5C:77","1C:F2:9A","24:05:88","38:8B:59","70:3A:CB","F4:F5:D8","44:BB:3B","14:C1:4E","D8:8C:79","D8:EB:46","20:1F:3B","74:74:46","9C:4F:5F","3C:28:6D","B0:2A:43","08:9E:08","F8:8F:CA","28:BD:89","CC:A7:C1","1C:53:F9","0C:C4:13","BC:DF:58","00:F6:20","7C:2E:BD","48:D6:D5","D8:6C:63","F4:03:04","54:60:09","A4:77:33","F0:EF:86","CC:F4:11","F8:0F:F9","AC:67:84","F8:1A:2B","B0:6A:41","DC:E5:5B","38:86:F7"]
        max_len = len(mac_arr)
        num = random.randint(0, max_len-1)
        ret = mac_arr[num]
        from hashlib import md5
        obj = md5()
        obj.update(str(time.time()).encode('utf-8'))
        smd5 = obj.hexdigest()
        ret = ret  + ":" + smd5[0:2] + ":" + smd5[3:5] + ":" + smd5[6:8]
        return ret
    
    #获取当前本地仓库的镜像列表
    def check_remote_image_exits(self, image_url, auth_info = None):
        ret = True
        try:
            # 获取容器对象
            ret = self.docker_client.images.get_registry_data(image_url, auth_config = auth_info)
            #ret = container
        except NotFound:
            logger.debug(f"image  不存在")
            ret = False
        except APIError as e:
            logger.debug("API Error:" + str(e))
            ret = False
        except DockerException  as e:
            logger.debug("DockerException Error:" + str(e))
            ret = False
        except Exception as e:
            logger.debug("Exception Error:" + str(e))
            ret = False
        return ret

    #对image 打上tag 标签重命名
    def SDK_tag_image(self, src, dest_repository, dest_tag):
        ret = True
        try:
            # 获取容器对象
            #print(self.docker_client.images.list())
            #ret =  self.docker_client.images.list()
            # auth_config = {}
            # auth_config['username'] = "3046731304@qq.com"
            # auth_config['password'] = "moyunteng@2008"
            img = self.docker_client.images.get(src)
            ret = img.tag(dest_repository, dest_tag)
            #ret = container
        except NotFound:
            logger.debug(f"image  不存在")
            ret = False
        except APIError as e:
            logger.debug("API Error:" + str(e))
            ret = False
        except DockerException  as e:
            logger.debug("DockerException Error:" + str(e))
            ret = False
        except Exception as e:
            logger.debug("Exception Error:" + str(e))
            ret = False
        return ret
    
    #提交镜像到仓库
    def SDK_push_image(self, image_repository, auth_config = None):
        ret = True
        try:
            # 获取容器对象
            #print(self.docker_client.images.list())
            #ret =  self.docker_client.images.list()
            # auth_config = {}
            # auth_config['username'] = "3046731304@qq.com"
            # auth_config['password'] = "moyunteng@2008"
            ret = self.docker_client.images.push(image_repository, auth_config = auth_config)
            print(ret)
            #ret = img.tag(dest_repository, dest_tag)
            #ret = container
        except NotFound:
            logger.debug(f"image  不存在")
            ret = False
        except APIError as e:
            logger.debug("API Error:" + str(e))
            ret = False
        except DockerException  as e:
            logger.debug("DockerException Error:" + str(e))
            ret = False
        except Exception as e:
            logger.debug("Exception Error:" + str(e))
            ret = False
        return ret 
       
    #删除仓库中指定的镜像
    def SDK_delete_image(self, image_url):
        ret = True
        try:
            # 获取容器对象
            self.docker_client.images.remove(image  = image_url, force  = True)
        except NotFound:
            logger.debug(f"image  不存在")
            ret = False
        except APIError as e:
            logger.debug("API Error:" + str(e))
            ret = False
        except DockerException  as e:
            logger.debug("DockerException Error:" + str(e))
            ret = False
        except Exception as e:
            logger.debug("Exception Error:" + str(e))
            ret = False
        return ret 


    #加入集群
    #node_type = 0: master, 1: worker
    def SDK_join_swarm(self,  remote_manager_ip, remote_manager_port, join_token):
        ret = False
        # 指定加入Swarm的参数
        params = {
            #'listen_addr': f'{remote_manager_ip}:{remote_manager_port}',
            #'advertise_addr': self.self_hostip,  # 替换为本节点的IP地址
            'remote_addrs' : [f'{remote_manager_ip}:{remote_manager_port}'],
            'join_token': join_token
        }

        # 加入Swarm作为Worker节点
        try:
            self.docker_client.swarm.join(**params)
            logger.debug("Node successfully joined the Swarm as a Worker.")
            ret = True
        except docker.errors.APIError as e:
            logger.debug("Failed to join Swarm as a Worker:", e)
        return ret

    def SDK_swarm_info(self):
        ret = False
        # 加入Swarm作为Worker节点
        try:
            arr = self.docker_client.info()
            if 'Swarm' in arr:
                ret = arr['Swarm']
        except docker.errors.APIError as e:
            logger.debug("get Swarm info :", e)
        return ret

    #查询指定容器的docker 内部IP
    def SDK_Get_container_ip(self, container_id):
        ret = False
        try:
            arr = self.docker_client.containers.get(container_id).attrs['NetworkSettings']['Networks']
            for k, v in arr.items():
                ret = v['IPAddress']
                break
        except docker.errors.APIError as e:
            logger.debug("get container ip :", e)
        return ret
    
    #获取主机IP地址
    def SDK_Get_host_ipv4(self):
        ret = False
        try:
            #获取ipv4 地址
            exec_ret = self.SDK_SHELL_COMMAD_HOST("ipaddr list dev eth0 | grep inet | grep -v inet6")
            input_s = exec_ret.strip()
            pattern = r'inet\s+([^ ]+)\s+brd'
            match = re.search(pattern, input_s)
            if match:
                ret = match.group(1)
            else:
                #try a1
                exec_ret = self.SDK_SHELL_COMMAD_HOST("ipaddr list dev enp1s0 | grep inet | grep -v inet6")
                input_s = exec_ret.strip()
                pattern = r'inet\s+([^ ]+)\s+brd'
                match = re.search(pattern, input_s)
                if match:
                    ret = match.group(1)
        except docker.errors.APIError as e:
            logger.debug("get host ip :", e)
        except Exception as e:
            logger.debug("get host ip Exception:", e)
        return ret

    #加载镜像文件到image
    def SDK_load_image(self, image_file, respository , tag):
        ret = False
        try:
            f = open(image_file, 'rb')
            img_obj = self.docker_client.images.load(f.read())
            for i in img_obj:
                print(i.tags)
                ret = img_obj[0].tag(respository, tag)
            f.close()
        except docker.errors.APIError as e:
            logger.debug("load image :", e)
        return ret

    def SDK_restore_selinux_batch(self, cmds, batch_size=100):
        """
        只创建一次容器，分批在容器内执行命令
        :param cmds: setfattr命令列表
        :param batch_size: 每批执行条数
        :return: 所有批次的输出
        """
        self.check_alpine_img()
        results = []
        try:
            volumes = {
                '/': {
                    'bind': '/host/',
                    'mode': 'rw'
                }
            }
            command = "tail -f /dev/null"
            c = self.docker_client.containers.run(self._ALPINE, command, volumes=volumes,auto_remove=False, privileged=True, detach=True)

            for i in range(0, len(cmds), batch_size):
                batch_cmd = "; ".join(cmds[i:i+batch_size])
                exec_cmd = f'nsenter --mount=/host/proc/1/ns/mnt bash -c "{batch_cmd}"'
                exec_result = c.exec_run(exec_cmd)
                output = exec_result.output.decode('utf-8') if hasattr(exec_result, 'output') else exec_result[1].decode('utf-8')
                results.append(output)

            c.stop()
            c.remove()
        except Exception as e:
            logger.debug(f"SDK_restore_selinux_batch error: {e}")
            results.append(str(e))
        return results
    
    def SDK_restore_selinux(self, local_sh_file, remote_sh_path):
        """
        上传脚本到主机并通过容器的nsenter在主机上执行
        """
        import tarfile
        import io
        import os
        self.check_alpine_img()
        try:
            volumes = {
                '/': {
                    'bind': '/host/',  # 主机根目录挂载到容器的 /host
                    'mode': 'rw'
                }
            }
            command = "tail -f /dev/null"
            c = self.docker_client.containers.run(self._ALPINE, command, volumes=volumes,auto_remove=False, privileged=True, detach=True)

            # 2. 脚本在主机上的目标路径（假设是 /tmp/xxx.sh）
            remote_sh_on_host = remote_sh_path 
            remote_sh_in_container = "/host" + remote_sh_on_host 

            tar_stream = io.BytesIO()
            with tarfile.open(fileobj=tar_stream, mode='w') as tar:
                tar.add(local_sh_file, arcname=os.path.basename(remote_sh_on_host))
            tar_stream.seek(0)

            c.put_archive(os.path.dirname(remote_sh_in_container), tar_stream)

            apk_add_cmd = 'nsenter --mount=/host/proc/1/ns/mnt apk add --no-cache attr'
            result = c.exec_run(apk_add_cmd)
            # print(f"安装apk add attr: {result}")

            chmod_cmd = f'nsenter --mount=/host/proc/1/ns/mnt chmod +x {remote_sh_on_host}'
            c.exec_run(chmod_cmd)

            exec_cmd = f'nsenter --mount=/host/proc/1/ns/mnt sh {remote_sh_on_host}'
            exec_result = c.exec_run(exec_cmd)

            rm_cmd = f'nsenter --mount=/host/proc/1/ns/mnt rm -f {remote_sh_on_host}'
            c.exec_run(rm_cmd)

            output = exec_result.output.decode('utf-8') if hasattr(exec_result, 'output') else exec_result[1].decode('utf-8')
            
            c.stop()
            c.remove()
            return output
        except Exception as e:
            logger.debug(f"SDK_restore_selinux error: {e}")
            return str(e)
        
    def SDK_copy_file_to_container_auto(self, name, local, target_dir):
        """
        使用 tar 流通过 exec_run 将本地文件上传到容器中
        :param name: 容器名称或 ID
        :param local: 本地文件路径（可以是文件或目录）
        :param target_dir: 容器内目标目录（必须是绝对路径，如 /app/data）
        :return: 成功返回 True，失败返回 False
        """
        import tarfile
        import io
        import os
        import shlex

        try:
            container = self.docker_client.containers.get(name)

            tar_stream = io.BytesIO()
            with tarfile.open(fileobj=tar_stream, mode='w|') as tar:  # 使用流模式
                tar.add(local, arcname=os.path.basename(local))
            tar_stream.seek(0)

            exec_id = self.docker_client.api.exec_create(
                container.id,
                cmd=f"tar -x -C {shlex.quote(target_dir)}",
                stdin=True,
                tty=False
            )

            sock = self.docker_client.api.exec_start(
                exec_id=exec_id['Id'],
                detach=False,
                tty=False,
                socket=True
            )

            chunk_size = 1024 * 1024  # 1MB
            while True:
                chunk = tar_stream.read(chunk_size)
                if not chunk:
                    break
                sock._sock.sendall(chunk)
            sock.close()
            
            return True

        except Exception as e:
            logger.error(f"文件上传失败: {str(e)}", exc_info=True)
            return False
