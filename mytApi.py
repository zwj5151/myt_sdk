import urllib.request
import urllib.error
import json
import os
import base64
from common.logger import logger
from urllib import parse
from  urllib.parse import quote
import time
from common.ToolsKit import ToolsKit
import requests

# myt api
class MytOS_API(object):
    _port = "9082"

    def __init__(self) -> None:
        self.devinfo = None
        self.tools = ToolsKit()
        cfg_path = self.tools.GetRootPath() + "/conf/dev.dat"
        if os.path.exists(cfg_path) == False:
            cfg_path = os.getcwd() + "/dev.dat"

        if os.path.exists(cfg_path) == True:
            with open(cfg_path,'r') as f:
                self.devinfo = json.load(f)
                f.close()
        #else:
        #   logger.debug(f"myt_api path:{cfg_path} is not exists!")

    # """单例模式"""
    # @classmethod
    # def get_instance(cls, *args, **kwargs):
    #     if not hasattr(MytOS_API, "_instance"):
    #         MytOS_API._instance = MytOS_API(*args, **kwargs)
    #     return MytOS_API._instance
    
    #访问url方法
    def http_request(self, url, data = None):
        ret = False
        try:
            status_code, response_test = self.tools.http_request_get(url)
            # response = urllib.request.urlopen(url, data=data)
            if status_code == 200:
                arr = json.loads(response_test)
                ret = arr
            else:
                logger.debug(f"HTTP request failed with status code: {status_code}")
                ret = False
        except json.JSONDecodeError as e:
            logger.debug(f"JSON decode error: {e}")
            ret = False
        except Exception as e:
            logger.debug(f"Unexpected error: {e}")
            ret = False
        return ret

    # 设置app root 权限
    def set_app_root(self, c_ip,  port, package):
        ret = False
        try:
            url = "http://" + c_ip + ":" + str(port) + "/modifydev?cmd=10&pkg=" + package + "&root=true"
            response = requests.get(url, timeout=5)
            response.raise_for_status()
        except requests.exceptions.HTTPError as errh:
            print(f"HTTP Error: {errh}")
        except requests.exceptions.ConnectionError as errc:
            print(f"Error Connecting: {errc}")
        except requests.exceptions.Timeout as errt:
            print(f"Timeout Error: {errt}")
        except requests.exceptions.RequestException as err:
            print(f"Something went wrong: {err}")
        else:
            data = response.text
            arr = json.loads(data)
            if arr['code'] == 200 :
                ret = True
            else:
                logger.debug("http request set root failed!")
        return ret

    #设置云手机设备信息
    def set_dev_info(self, c_ip, port, devfile):
        ret = False
        try:
            file_path = devfile
            if os.path.exists(file_path):
                with open(file_path, "r", encoding='utf-8') as file:
                    content = file.read()
                arr = json.loads(content)
                json_string = json.dumps(arr)
                encoded_text = base64.urlsafe_b64encode(json_string.encode("utf-8")).decode("utf-8")
                # with open("base64.bin", "w") as file2:
                #     file2.write(encoded_text)

                url =  "http://" + c_ip + ":" + str(port) + "/modifydev?cmd=1&data=" + encoded_text
                #url =  "http://" + c_ip + ":" + str(port) + "/modifydev?cmd=2"
                status_code, response_text  = self.tools.http_request_get(url) 
                if status_code == 200:
                    arr = json.loads(response_text)
                    logger.debug(arr)
                    ret = True
                else:
                    logger.debug(f"http request set root failed! {status_code} {response_text}")         
                # data = response_text
                # logger.debug(data)
                # arr = json.loads(data)
                # if arr['code'] == 200:
                #     ret = True
                # else:
                #     logger.debug("http request set root failed!")
            else:
                logger.debug("文件不存在!")
        except json.JSONDecodeError as e:
            logger.debug(f"JSON decode error: {e}")
            ret = False
        except Exception as e:
            logger.debug(f"Unexpected error: {e}")
            ret = False
        return ret
    
    #导出设备信息
    def export_dev_info(self, ip, port, ofile):
        ret = False
        try:
            url =  "http://" + ip + ":" + str(port) + "/modifydev?cmd=8"
            status_code, response_text = self.tools.http_request_get(url)
            data = response_text
            # logger.debug(data)
            if status_code == 200:
                arr = json.loads(data)
                if arr['code'] == 200 :
                    with open(ofile, "w") as file2:
                        file2.write(arr['ret'])
                    ret = True
                else:
                    logger.debug("http request export_dev failed!")
            else:
                logger.debug(f"http request export_dev failed! {status_code} {response_text}")
        except json.JSONDecodeError as e:
            logger.debug(f"JSON decode error: {e}")
            ret = False
        except Exception as e:
            logger.debug(f"Unexpected error: {e}")
            ret = False
        return ret

    #导入设备信息
    def import_dev_info(self, ip, port, ifile):
        ret = False
        try:
            file_path = ifile
            if os.path.exists(file_path):
                with open(file_path, "r", encoding='utf-8') as file:
                    content = file.read()

                url =  "http://" + ip + ":" + str(port) + "/modifydev?cmd=9&data=" + quote(content)
                status_code, response_text = self.tools.http_request_get(url, timeout=20)       
                 # 构造 POST 请求的 URL 和数据
                # url = f"http://{ip}:{port}/modifydev?cmd=9"
                # data = {
                #     "data": content
                # }
                # headers = {"Content-Type": "application/json"}
                # data_encoded = json.dumps(data).encode('utf-8')

                # # 发送 POST 请求
                # request = urllib.request.Request(url, data=data_encoded, headers=headers, method="POST")
                # response = urllib.request.urlopen(request, timeout=20)
                if status_code == 200:
                    data = response_text
                    logger.debug(data)
                    arr = json.loads(data)
                    if arr['code'] == 200:
                        ret = True
                    else:
                        logger.debug("http request import_dev_info failed!")
                else:
                    logger.debug(f"http request import_dev_info failed! {status_code} {response_text}")
            else:
                logger.debug("文件不存在!")
        except json.JSONDecodeError as e:
            logger.debug(f"JSON decode error: {e}")
            ret = False
        except Exception as e:
            logger.debug(f"Unexpected error: {e}")
            ret = False
        return ret  
    
    #隐藏App信息
    def hide_app_info(self, ip, port, app_json_str):
        ret = False
        try:
            encoded_text = base64.urlsafe_b64encode(app_json_str.encode("utf-8")).decode("utf-8")
            url =  "http://" + ip + ":" + str(port) + "/modifydev?cmd=3&data=" + encoded_text
            status_code, response_text = self.tools.http_request_get(url)
            if status_code == 200:
                data = response_text
                logger.debug(data)
                arr = json.loads(data)
                if arr['code'] == 200:
                    ret = True
                else:
                    logger.debug("http request set hide_app failed!")
            else:
                logger.debug(f"http request set hide_app failed! {status_code} {response_text}")
        except json.JSONDecodeError as e:
            logger.debug(f"JSON decode error: {e}")
            ret = False
        except Exception as e:
            logger.debug(f"Unexpected error: {e}")
            ret = False
        return ret
    
    #获取当前视频流
    def get_video_stream_addr(self, ip, port):
        ret = False
        try:
            url =  "http://" + ip + ":" + str(port) + "/modifydev?cmd=5"
            status_code, response_text = self.tools.http_request_get(url)
            if status_code == 200:
                data = response_text
                logger.debug(data)
                arr = json.loads(data)
                if arr['code'] == 200:
                    ret = True
                else:
                    logger.debug("http request set get_video_stream failed!")
            else:
                logger.debug(f"http request set get_video_stream failed! {status_code} {response_text}")
        except json.JSONDecodeError as e:
            logger.debug(f"JSON decode error: {e}")
            ret = False
        except Exception as e:
            logger.debug(f"Unexpected error: {e}")
            ret = False
        return ret
    
    #设置摄像头视频流
    # resloution 分辨率
    def set_video_stream_addr(self, ip, port, addr, type, resloution = None):
        ret = False
        try:
            url =  "http://" + ip + ":" + str(port) + "/modifydev?cmd=4&type=" + type + "&path=" + addr
            # response = urllib.request.urlopen(url)   
            status_code, response_text = self.tools.http_request_get(url)         
            if status_code == 200:
                data = response_text
                logger.debug(data)
                arr = json.loads(data)
                if arr['code'] == 200:
                    ret = arr
                else:
                    logger.debug("http request set set_video_stream_addr failed!")
            else:
                logger.debug(f"http request set set_video_stream_addr failed! {status_code} {response_text}")

            if (resloution is not None) and (ret != False) :
                s_arr = {}
                s_arr['cmdline'] = f'setprop persist.lg.resolution {resloution}'
                encoded_text = parse.urlencode(s_arr)
                url = f"http://{ip}:{port}/modifydev?cmd=6&{encoded_text}"
                status_code, response_text = self.tools.http_request_get(url)
                if status_code == 200:
                    data = response_text
                    logger.debug(data)
                    arr = json.loads(data)
                    if arr['code'] == 200:
                        ret = True
                    else:
                        logger.debug("http request set get_video_stream failed!")
                else:
                    logger.debug(f"http request set get_video_stream failed! {status_code} {response_text}")
        except json.JSONDecodeError as e:
            logger.debug(f"JSON decode error: {e}")
            ret = False
        except Exception as e:
            logger.debug(f"Unexpected error: {e}")
            ret = False
        return ret
    
    #判断设备api 是否初始化完成 block
    #ret = 0 成功    1 超时   2 系统启动失败需要重启
    def is_api_server_inited(self, ip, port, time_out, isdevInit, docker_api = None, dc_name = None):
        ret = 1
        b_time = time.time()
        default_url_timeout = 20
        default_sleep_time = 5
        if time_out<default_url_timeout:
            default_url_timeout = time_out
            default_sleep_time = 0

        bInitState = False      #初始化完成的状态
        while True:
            try:
                #print(time.time())

                now = time.time()
                if now - b_time>=time_out:
                    break
                url = f"http://{ip}:{port}/task=snap&level=1"
                # response = urllib.request.urlopen(url, timeout=default_url_timeout) 
                status_code, response_text = self.tools.http_request_get(url,timeout=default_url_timeout)
                # data = response.read()
                # data = json.loads(response_text)

                if isdevInit == 1:   #需要判断设备是否初始化完成
                    cmd = "ls /data/prop.txt"
                    #cmd = "ls /sdcard/Android"
                    exec_ret = docker_api.SDK_contianer_exec(dc_name, cmd)
                    if exec_ret.exit_code==0:
                        ret = 0
                        time.sleep(1)
                        bInitState = True
                else:
                    ret = 0
                    time.sleep(1)
                    bInitState = True

                if bInitState == True:
                    #判断当前系统是否启动成功
                    cmd = "ls /sdcard/Android"
                    exec_ret = docker_api.SDK_contianer_exec(dc_name, cmd)
                    if exec_ret.exit_code==0:
                        ret = 0
                    else:
                        ret = 2 #系统启动失败

                    break
                #logger.debug(data)
                #arr = json.loads(data)
            except urllib.error.HTTPError as e:
                #logger.debug(f"is_api_server_inited HTTPError: {e.code} - {e.reason}")
                pass
            except urllib.error.URLError as e:
                pass
                #logger.debug(f"is_api_server_inited URLError: {e.reason}")
            except Exception as e:
                pass
                #logger.debug("Exception Error:" + str(e)) 
            time.sleep(default_sleep_time)
        return ret
    
    #获取文件列表
    def get_file_list(self, ip, port, filelist):
        ret = False
        try:
            url = "http://" + ip + ":" + str(port) + "/files?list=" + filelist
            # 使用封装的 GET 请求方法替换 urllib.request.urlopen
            status_code, response_text = self.tools.http_request_get(url, timeout=1)
            if status_code == 200:
                data = response_text
                logger.debug(data)
                arr = json.loads(data)
                if arr['code'] == 200:
                    ret = arr['files']
                else:
                    logger.debug("http request get_file_list failed!")
            else:
                logger.debug(f"HTTP request failed with status code: {status_code} {response_text}")
        except json.JSONDecodeError as e:
            logger.debug(f"JSON decode error: {e}")
            ret = False
        except Exception as e:
            logger.debug(f"Unexpected error: {e}")
            ret = False
        return ret
    
    #下载文件
    # def down_file(self, ip, port, filepath, localfile):
    #     ret = False
    #     try:
    #         #http://192.168.181.27:10017/download?path=/sdcard/Pictures/.thumbnails/.database_uuid
    #         down_url =  "http://" + ip + ":" + str(port) + "/download?path=" + filepath
    #         urllib.request.urlretrieve(down_url, localfile)
    #         ret = True
    #     except urllib.error.HTTPError as e:
    #         logger.debug(f"HTTPError: {e.code} - {e.reason}")
    #         ret = False
    #     except urllib.error.URLError as e:
    #         logger.debug(f"URLError: {e.reason}")
    #         ret = False
    #     except Exception as e:
    #         logger.debug("Exception Error:" + str(e)) 
    #         ret = False
    #     return ret    
    

    def down_file(self, ip, port, filepath, localfile):
        ret = False
        url =  "http://" + ip + ":" + str(port) + "/download?path=" + filepath
        try:
            response = requests.get(url, stream=True)
            response.raise_for_status()  # 如果请求状态不是200，引发HTTPError异常
            ret = True
        except requests.exceptions.HTTPError as errh:
            print(f"HTTP Error: {errh}")
        except requests.exceptions.ConnectionError as errc:
            print(f"Error Connecting: {errc}")
        except requests.exceptions.Timeout as errt:
            print(f"Timeout Error: {errt}")
        except requests.exceptions.RequestException as err:
            print(f"Something went wrong: {err}")
        else:
            with open(localfile, 'wb') as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)
            ret = True
            logger.debug("File downloaded successfully.")
        return ret


    #随机设备信息
    #http://ip:9082/modifydev?random_abroad=false&modelId=xiaomi&isSpecifiedModel=true&cmd=2
    def random_devinfo(self, ip, port, random_abroad = False, model_id = None, Lang = None, UserIp = None):
        ret = False
        try:
            if random_abroad == True:
                str_abroad = "random_abroad=true"
            else:
                str_abroad = "random_abroad=false"
            
            if model_id is None:
                url =  "http://" + ip + ":" + str(port) + "/modifydev?modifymac=true&cmd=2&" + str_abroad
            else:
                url =  "http://" + ip + ":" + str(port) + "/modifydev?cmd=2&isSpecifiedModel=true&modifymac=true&modelId=" + model_id

            if Lang is not None:
                url = url + "&language=" + Lang

            if UserIp is not None:
                url = url + "&userip=" + UserIp
                
            status_code, response_text = self.tools.http_request_get(url, timeout=60)
            if status_code == 200:
                data = response_text
                logger.debug(data)
                arr = json.loads(data)
                if arr['code'] == 200:
                    ret = arr['msg']
                else:
                    logger.debug("http request random_devinfo failed!")
            else:
                logger.debug(f"HTTP request failed with status code: {status_code} {response_text}")
        except json.JSONDecodeError as e:
            logger.debug(f"JSON decode error: {e}")
            ret = False
        except Exception as e:
            logger.debug(f"Unexpected error: {e}")
            ret = False
        return ret

    #采用异步请求的方式查询
    #ret = 200  成功
    #ret = 202 失败
    #ret = 203 查询中
    #ret = 204 当前有任务正在执行
    #ret = 205 当前没有任务
    #ret = 206 当前任务已超时失败

    def random_devinfo_async2(self, ip, port, act, random_abroad = False, model_id = None, Lang = None, UserIp = None):
        ret = 0
        tools  = ToolsKit()
        skey = f"{ip}_{port}"
        #strV = tools.get_key_value(skey)
        strV = tools.get_tmpfile_value(skey)
        if strV is not None:
            kvarr = strV
            #kvarr = json.loads(strV)
            # t_time = arr['t_time']
            # task_id = arr['task_id']
        else:
            kvarr = None

        if act == 'request':
            #判断当前状态
            if kvarr is not None:
                now_time = time.time()
                if now_time - int(kvarr['t_time'])<60:
                    ret = 204
                    msg = "当前有任务正在执行"
                    return ret,msg
            else:
                kvarr = {}
            
            url =  "http://" + ip + ":" + str(port) + "/queryversion"
            #logger.debug(f"http request random_devinfo asyn  {url}")
            # response = urllib.request.urlopen(url, timeout = 3)  
            status_code, response_text = self.tools.http_request_get(url, timeout=3)
            # data = response.read()
            if status_code == 200:
                data = response_text
                data = json.loads(response_text)
            else:
                logger.debug(f"HTTP request failed with status code: {status_code} {response_text}")
            if random_abroad == True:
                str_abroad = "random_abroad=true"
            else:
                str_abroad = "random_abroad=false"
            if model_id is None:
                url =  "http://" + ip + ":" + str(port) + "/modifydev?modifymac=true&cmd=2&" + str_abroad
            else:
                url =  "http://" + ip + ":" + str(port) + "/modifydev?cmd=2&isSpecifiedModel=true&modifymac=true&modelId=" + model_id
            if Lang is not None:
                url = url + "&language=" + Lang 
            if UserIp is not None:
                url = url + "&userip=" + UserIp
            url = url + "&isasync=true"
            #logger.debug(f"http request random_devinfo asyn  {url}")
            try:
                # response = urllib.request.urlopen(url, timeout = 5)  
                status_code, response_text = self.tools.http_request_get(url, timeout=5)          
                # data = response.read()
                if status_code == 200:
                    data = response_text
                    arr = json.loads(response_text)
                else:
                    logger.debug(f"HTTP request failed with status code: {status_code} {response_text}")
                if arr['code'] == 200 :
                    #开始循环查询任务
                    task_id = arr['msg']
                    t_time = time.time()
                    kvarr['task_id'] = task_id
                    kvarr['t_time'] = t_time
                    #tools.set_key_value(skey, json.dumps(kvarr))
                    tools.set_tmpfile_value(skey, kvarr)
                    ret = 200
                    msg = "请求成功"
                else:
                    #logger.debug("http request random_devinfo failed!")
                    ret = 202
                    msg  ="执行失败"
            except Exception as e:
                #logger.debug("Exception Error:" + str(e)) 
                ret = 202  
                msg = "执行失败"
        elif act == "query":        
            #判断当前状态
            if kvarr is not None:
                now_time = time.time()
                if now_time - int(kvarr['t_time'])>60:
                    #logger.debug("wait for random devinfo timeout!")
                    ret = 206
                    msg = "超时失败"
                    #tools.delete_key_value(skey)
                    tools.delete_tmpfile_value(skey)
                    return ret,msg
            else:
                #logger.debug("no task !")
                ret = 205
                msg = "当前无任务"
                return ret,msg
            try:
                url =  "http://" + ip + ":" + str(port) + "/modifydev?cmd=2&query=" + kvarr['task_id']
                # response = urllib.request.urlopen(url, timeout = 2) 
                status_code, response_text = self.tools.http_request_get(url, timeout=2)      
                # data = response.read()
                if status_code == 200:
                    data = response_text
                    arr = json.loads(data)
                else:
                    logger.debug(f"HTTP request failed with status code: {status_code} {response_text}")
                if arr['code'] == 200 :
                    ret = 200
                    msg = "执行成功"
                    #tools.delete_key_value(skey)
                    tools.delete_tmpfile_value(skey)
                else:
                    if arr['reason'] == 'busy':
                        ret = 204
                        msg = "任务正在执行中"
                    else:
                        #logger.debug(f"http request random_devinfo failed! reason:{arr['reason']}")
                        ret = 202
                        msg = "任务执行失败"
                        #tools.delete_key_value(skey)
                        tools.delete_tmpfile_value(skey)
                        
            except json.JSONDecodeError as e:
                #logger.debug(f"async URLError: {e.reason}")
                ret = 204
                msg = "任务正在执行中"
            except Exception as e:
                #logger.debug(f" async query HTTPError: {e.code} - {e.reason}")
                ret = 204
                msg = "任务正在执行中"
        return ret,msg
    #异步请求方式  随机信息  需要系统版本支持
    def random_devinfo_async(self, ip, port, random_abroad = False, model_id = None, Lang = None, UserIp = None):
        ret = False
        url_try_count = 0
        url_try_max = 3
        try:
            url =  "http://" + ip + ":" + str(port) + "/queryversion"
            # response = urllib.request.urlopen(url, timeout = 15)            
            # data = response.read()
            status_code, response_text = self.tools.http_request_get(url, timeout=15)    
            if status_code == 200:
                data = response_text
            else:
                logger.debug(f"HTTP request failed with status code: {status_code} {response_text}")
            if random_abroad == True:
                str_abroad = "random_abroad=true"
            else:
                str_abroad = "random_abroad=false"
            
            if model_id is None:
                url =  "http://" + ip + ":" + str(port) + "/modifydev?modifymac=true&cmd=2&" + str_abroad
            else:
                url =  "http://" + ip + ":" + str(port) + "/modifydev?cmd=2&isSpecifiedModel=true&modifymac=true&modelId=" + model_id

            if Lang is not None:
                url = url + "&language=" + Lang

            if UserIp is not None:
                url = url + "&userip=" + UserIp

            url = url + "&isasync=true"

            logger.debug(f"http request random_devinfo async")
            # response = urllib.request.urlopen(url, timeout = 20)            
            # data = response.read()
            status_code, response_text = self.tools.http_request_get(url, timeout=2)   
            if status_code == 200: 
                data = response_text
                arr = json.loads(data)
            else:
                logger.debug(f"HTTP request failed with status code: {status_code} {response_text}")
            if arr['code'] == 200 :
                #{"code":200,"msg":"b329f34d-5a8c-45ef-805c-ac774da788fe"}

                #开始循环查询任务
                task_id = arr['msg']
                t_time = time.time()
                while(True):
                    if (time.time() - t_time) > 120:
                        logger.debug("wait for random devinfo timeout!")
                        ret = False
                        break
                    else:
                        time.sleep(1)
                    try:
                        url =  "http://" + ip + ":" + str(port) + "/modifydev?cmd=2&query=" + task_id
                        # response = urllib.request.urlopen(url, timeout = 5)            
                        # data = response.read()
                        status_code, response_text = self.tools.http_request_get(url, timeout=2)    
                        if status_code == 200:
                            data = response_text
                            arr = json.loads(data)
                            if arr['code'] == 200 :
                                ret = True
                                time.sleep(3)
                                break
                            else:
                                if arr['reason'] == 'busy':
                                    continue
                                else:
                                    logger.debug(f"http request random_devinfo failed! reason:{arr['reason']}")
                                    ret = False
                                    break
                        else:
                            logger.debug(f"HTTP request failed with status code: {status_code} {response_text}")
                            ret = False
                            break
                    except json.JSONDecodeError as e:
                        #logger.debug(f"async URLError: {e.reason}")
                        continue
                    except urllib.error.HTTPError as e:
                        #logger.debug(f"async query HTTPError: {e.code} - {e.reason}")
                        continue

            else:
                logger.debug("http request random_devinfo failed!")
                ret = False
        except json.JSONDecodeError as e:
            logger.debug(f"JSON decode error: {e}")
            ret = False
            # url_try_count = url_try_count + 1
            # if url_try_count < url_try_max:
            #     time.sleep(1)
            #     ret = self.random_devinfo_async(ip, port, random_abroad, model_id, Lang, UserIp)
            # else:
            #     logger.debug(f"URLError: {e.reason}  trycount:{url_try_count}")
            ret = False
        except Exception as e:
            logger.debug("Exception Error:" + str(e)) 
            ret = False
        return ret

    #获取设备型号字典
    def get_devinfo_dict(self):
        return self.devinfo
    
    #设置系统语言
    #lang 默认为  en
    #该方法为 ip定位
    def set_language(self, ip, port, lang = 'en', user_ip = None):
        ret = False
        try:
            #http://192.168.181.27:10017/download?path=/sdcard/Pictures/.thumbnails/.database_uuid
            if user_ip is not None:
                url =  "http://" + ip + ":" + str(port) + "/modifydev?cmd=11&launage=" + lang + "&ip=" + user_ip
            else:
                url =  "http://" + ip + ":" + str(port) + "/modifydev?cmd=11&launage=" + lang
            #url =  "http://" + ip + ":" + str(port) + "/modifydev?cmd=11&launage=" + lang
            # response = urllib.request.urlopen(url, timeout = 45)
            # data = response.read()
            status_code, response_text = self.tools.http_request_get(url, timeout=45)    
            if status_code == 200:
                data = response_text
                logger.debug(data)
                arr = json.loads(data)
                if arr['code'] == 200 :
                    ret = True
                else:
                    logger.debug("http request set_language failed!")
            else:
                logger.debug(f"HTTP request failed with status code: {status_code} {response_text}")
        except json.JSONDecodeError as e:
            logger.debug(f"JSON decode error: {e}")
            ret = False
        except Exception as e:
            logger.debug(f"Unexpected error: {e}")
            ret = False
        return ret 
    
    #设置语言属性
    def set_languageProp(self, ip, port, lang , country ):
        ret = False
        try:
            #http://192.168.181.27:10017/download?path=/sdcard/Pictures/.thumbnails/.database_uuid
            url =  "http://" + ip + ":" + str(port) + "/modifydev?cmd=13&language=" + lang + "&country=" + country
            # response = urllib.request.urlopen(url, timeout = 5)
            # data = response.read()
            status_code, response_text = self.tools.http_request_get(url, timeout=5)
            if status_code == 200:  
                data = response_text  
                logger.debug(data)
                arr = json.loads(data)
                if arr['code'] == 200 :
                    ret = True
                else:
                    logger.debug("http request set_languageProp failed!")
            else:
                logger.debug(f"HTTP request failed with status code: {status_code} {response_text}")
            #ret = True
        except json.JSONDecodeError as e:
            logger.debug(f"JSON decode error: {e}")
            ret = False
        except Exception as e:
            logger.debug(f"Unexpected error: {e}")
            ret = False
        return ret 
    
    #设置经纬度
    def set_location(self, ip, port, lat, lng):
        ret = False
        try:
            #http://192.168.181.27:10017/download?path=/sdcard/Pictures/.thumbnails/.database_uuid
            #cmd=12&lat=11.56721&lng=89.9911232321
            url =  "http://" + ip + ":" + str(port) + "/modifydev?cmd=12&lat=" + lat + "&lng=" + lng
            # response = urllib.request.urlopen(url, timeout = 5)
            # data = response.read()
            status_code, response_text = self.tools.http_request_get(url, timeout=5)    
            if status_code == 200:
                data = response_text
                logger.debug(data)
                arr = json.loads(data)
                if arr['code'] == 200 :
                    ret = True
                else:
                    logger.debug("http request set_language failed!")
            else:
                logger.debug(f"HTTP request failed with status code: {status_code} {response_text}")
            ret = True
        except json.JSONDecodeError as e:
            logger.debug(f"JSON decode error: {e}")
            ret = False
        except Exception as e:
            logger.debug(f"Unexpected error: {e}")
            ret = False
        return ret   
    
    #设置声音资源
    #res 本地资源
    #act play   stop
    def set_audio_restype(self, ip, port, type, res, act):
        ret = False
        try:
            #http://192.168.181.27:10017/download?path=/sdcard/Pictures/.thumbnails/.database_uuid
            #cmd=12&lat=11.56721&lng=89.9911232321
            #http://192.168.30.2:10011/modifydev?cmd=14&type=media&source=/sdcard//mymus.mp3&state=play|stop
            # cmd=14 type=(media webrtc rtmp camera) source=
            url =  "http://" + ip + ":" + str(port) + f"/modifydev?cmd=14&type={type}&source={res}&state={act}"
            # response = urllib.request.urlopen(url, timeout = 5)
            # data = response.read()
            status_code, response_text = self.tools.http_request_get(url, timeout=5) 
            if status_code == 200:
                data = response_text   
                logger.debug(data)
                arr = json.loads(data)
                if arr['code'] == 200 :
                    ret = True
                else:
                    logger.debug("http request set_audio_restype failed!")
            else:
                logger.debug(f"HTTP request failed with status code: {status_code} {response_text}")
            ret = True
        except json.JSONDecodeError as e:
            logger.debug(f"JSON decode error: {e}")
            ret = False
        except Exception as e:
            logger.debug(f"Unexpected error: {e}")
            ret = False
        return ret     
    
    #自定义设置设备信息
    def set_custom_dev(self, ip, port, devinfo, fingerinfo):
        ret = False
        try:
            json_str = json.dumps(fingerinfo)
            s_arr = {}
            s_arr['dev_data'] = devinfo
            s_arr['custom'] = json_str
            encoded_text = parse.urlencode(s_arr)
            url =  "http://" + ip + ":" + str(port) + f"/modifydev?cmd=15&{encoded_text}"
            # response = urllib.request.urlopen(url, timeout = 40)
            # data = response.read()
            status_code, response_text = self.tools.http_request_get(url, timeout=40)
            if status_code == 200:
                data = response_text    
                logger.debug(data)
                arr = json.loads(data)
                if arr['code'] == 200 :
                    ret = True
                else:
                    logger.debug("http request set_custom_dev failed!")
            else:
                logger.debug(f"HTTP request failed with status code: {status_code} {response_text}")
        except json.JSONDecodeError as e:
            logger.debug(f"JSON decode error: {e}")
            ret = False
        except Exception as e:
            logger.debug(f"Unexpected error: {e}")
            ret = False
        return ret 

    #获取剪切板内容
    def get_clipboard(self, ip, port):
        ret = False
        try:
            url =  "http://" + ip + ":" + str(port) + f"/clipboard"
            # response = urllib.request.urlopen(url, timeout = 15)
            # data = response.read()
            status_code, response_text = self.tools.http_request_get(url, timeout=15)    
            if status_code == 200:
                data = response_text
                logger.debug(data)
                arr = json.loads(data)
                if arr['code'] == 200 :
                    ret = arr['data']['text']
                else:
                    logger.debug("http request get_clipboard failed!")
            else:
                logger.debug(f"HTTP request failed with status code: {status_code} {response_text}")
            #ret = True
        except json.JSONDecodeError as e:
            logger.debug(f"JSON decode error: {e}")
            ret = False
        except Exception as e:
            logger.debug(f"Unexpected error: {e}")
            ret = False
        return ret
    
    #设置内容到剪切板
    def set_clipboard(self, ip, port, text):
        ret = False
        try:
            s_arr = {}
            s_arr['text'] = text
            encoded_text = parse.urlencode(s_arr)
            url =  "http://" + ip + ":" + str(port) + f"/clipboard?cmd=2&{encoded_text}"
            # response = urllib.request.urlopen(url, timeout = 15)
            # data = response.read()
            status_code, response_text = self.tools.http_request_get(url, timeout=2)   
            if status_code == 200: 
                data = response_text
                logger.debug(data)
                arr = json.loads(data)
                if arr['code'] == 200 :
                    ret = True
                else:
                    logger.debug("http request set_clipboard failed!")
            else:
                logger.debug(f"HTTP request failed with status code: {status_code} {response_text}")
        except json.JSONDecodeError as e:
            logger.debug(f"JSON decode error: {e}")
            ret = False
        except Exception as e:
            logger.debug(f"Unexpected error: {e}")
            ret = False
        return ret

    #s5 操作
    def query_s5(self, ip, port, time_out=5):
        ret = False
        try:
            url =  "http://" + ip + ":" + str(port) + f"/proxy"
            # response = urllib.request.urlopen(url, timeout = time_out)
            # data = response.read()
            status_code, response_text = self.tools.http_request_get(url, timeout=time_out)   
            if status_code == 200: 
                data = response_text
                logger.debug(data)
                arr = json.loads(data)
                if arr['code'] == 200 :
                    ret = arr['data']
                else:
                    logger.debug("http request query_s5_oper failed!")
            else:
                logger.debug(f"HTTP request failed with status code: {status_code} {response_text}")
        except json.JSONDecodeError as e:
            logger.debug(f"JSON decode error: {e}")
            ret = False
        except Exception as e:
            logger.debug(f"Unexpected error: {e}")
            ret = False
        return ret  
    
    #设置s5信息
    def set_s5(self, ip, port, s5_ip, s5_port, s5_id, s5_pwd, mode = None):
        ret = False
        try:
            #ky 20240910 执行一次调用修复bug
            s_arr = {}
            s_arr['cmdline'] = "sed -i '/persist\\.s5/d' /data/prop.txt"
            encoded_text = parse.urlencode(s_arr)
            url = f"http://{ip}:{port}/modifydev?cmd=6&{encoded_text}"
            # response = urllib.request.urlopen(url, timeout = 15)
    
            if mode == None:
                url =  f"http://" + ip + ":" + str(port) + f"/proxy?cmd=2&ip={s5_ip}&port={s5_port}&usr={s5_id}&pwd={s5_pwd}"
            else:
                url =  f"http://" + ip + ":" + str(port) + f"/proxy?cmd=2&ip={s5_ip}&port={s5_port}&usr={s5_id}&pwd={s5_pwd}&type={mode}"
                
            # response = urllib.request.urlopen(url, timeout = 15)
            # data = response.read()
            status_code, response_text = self.tools.http_request_get(url, timeout=15)   
            if status_code == 200: 
                data = response_text
                logger.debug(data)
                arr = json.loads(data)
                if arr['code'] == 200 :
                    ret = arr['msg']
                else:
                    logger.debug("http request query_s5_oper failed!")
            else:
                logger.debug(f"HTTP request failed with status code: {status_code} {response_text}")
        except json.JSONDecodeError as e:
            logger.debug(f"JSON decode error: {e}")
            ret = False
        except Exception as e:
            logger.debug(f"Unexpected error: {e}")
            ret = False
        return ret  
    
    #停止s5
    def stop_s5(self, ip, port):
        ret = False
        try:
            url =  f"http://" + ip + ":" + str(port) + f"/proxy?cmd=3"
            # response = urllib.request.urlopen(url, timeout = 15)
            # data = response.read()
            status_code, response_text = self.tools.http_request_get(url, timeout=15)  
            if status_code == 200:  
                data = response_text
                logger.debug(data)
                arr = json.loads(data)
                if arr['code'] == 200 :
                    ret = arr['msg']
                else:
                    logger.debug("http request query_s5_oper failed!")
            else:
                logger.debug(f"HTTP request failed with status code: {status_code} {response_text}")
        except json.JSONDecodeError as e:
            logger.debug(f"JSON decode error: {e}")
            ret = False
        except Exception as e:
            logger.debug(f"Unexpected error: {e}")
            ret = False
        return ret   
    
    def add_s5_filter_url(self, ip, port, url_list):
        ret = False
        try:
            url =  f"http://" + ip + ":" + str(port) + f"/proxy?cmd=4"
            data = url_list.encode('utf-8')
            data_list = eval(data)
            print(data)
            # request = urllib.request.Request(url, data=data)
            # response = urllib.request.urlopen(request, timeout = 15)
            # data = response.read().decode('utf-8')
            # status_code, response_test = self.tools.http_request_post(url, data=data_list, timeout=15)
            response = requests.post(url, json=data_list)
            print(response.text)
            logger.debug(response.text)
            arr = json.loads(response.text)
            if arr['code'] == 200 :
                ret = arr['msg']
            else:
                logger.debug("http request query_s5_oper failed!")
        except json.JSONDecodeError as e:
            logger.debug(f"JSON decode error: {e}")
            ret = False
        except Exception as e:
            logger.debug(f"Unexpected error: {e}")
            ret = False
        return ret   
    
    #设置运动传感器灵敏度
    def set_motion_sensor_sensitivity(self, ip, port, factor):
        ret = False
        try:
            url =  f"http://{ip}:{port}/modifydev?cmd=17&scale={factor}"
            # response = urllib.request.urlopen(url, timeout = 15)
            # data = response.read()
            status_code, response_text = self.tools.http_request_get(url, timeout=15)    
            if status_code == 200:
                data = response_text
                logger.debug(data)
                arr = json.loads(data)
                if arr['code'] == 200 :
                    ret = arr['msg']
                else:
                    logger.debug("http request set_motion_sensor_sensitivity failed!")
            else:
                logger.debug(f"HTTP request failed with status code: {status_code} {response_text}")
        except json.JSONDecodeError as e:
            logger.debug(f"JSON decode error: {e}")
            ret = False
        except Exception as e:
            logger.debug(f"Unexpected error: {e}")
            ret = False
        return ret    

    #设置摇一摇状态
    def set_shake_status(self, ip, port, enable):
        ret = False
        try:
            url =  f"http://{ip}:{port}/modifydev?cmd=17&shake={enable}"
            # response = urllib.request.urlopen(url, timeout = 15)
            # data = response.read()
            status_code, response_text = self.tools.http_request_get(url, timeout=15)
            if status_code == 200:
                data = response_text
                logger.debug(data)
                arr = json.loads(data)
                if arr['code'] == 200 :
                    ret = arr['msg']
                else:
                    logger.debug("http request set_shake_status failed!")
            else:
                logger.debug(f"HTTP request failed with status code: {status_code} {response_text}")
        except json.JSONDecodeError as e:
            logger.debug(f"JSON decode error: {e}")
            ret = False
        except Exception as e:
            logger.debug(f"Unexpected error: {e}")
            ret = False
        return ret    

    #给指定的应用所有的权限
    def set_app_authority(self, ip, port, package):
        ret = False
        try:
            url =  f"http://{ip}:{port}/modifydev?cmd=18&pkg={package}"
            # response = urllib.request.urlopen(url, timeout = 15)
            # data = response.read()
            status_code, response_text = self.tools.http_request_get(url, timeout=15)
            if status_code == 200:
                data = response_text
                logger.debug(data)
                arr = json.loads(data)
                if arr['code'] == 200 :
                    ret = arr['msg']
                else:
                    logger.debug("http request set_app_authority failed!")
            else:
                logger.debug(f"HTTP request failed with status code: {status_code} {response_text}")
        except json.JSONDecodeError as e:
            logger.debug(f"JSON decode error: {e}")
            ret = False
        except Exception as e:
            logger.debug(f"Unexpected error: {e}")
            ret = False
        return ret  
    
    #对分辨率感知添加白名单
    def set_reloution_filter(self, ip, port, pkg, enable):
        ret = False
        try:
            if enable == '1':
                url =  f"http://{ip}:{port}/modifydev?cmd=19&pkg={pkg}&filter=true"
            else:
                url =  f"http://{ip}:{port}/modifydev?cmd=19&pkg={pkg}&filter=false"
            # response = urllib.request.urlopen(url, timeout = 15)
            # data = response.read()
            status_code, response_text = self.tools.http_request_get(url, timeout=15)
            if status_code == 200:
                data = response_text
                logger.debug(data)
                arr = json.loads(data)
                if arr['code'] == 200 :
                    ret = arr['msg']
                else:
                    logger.debug("http request set_reloution_Enable failed!")
            else:
                logger.debug(f"HTTP request failed with status code: {status_code} {response_text}")
        except json.JSONDecodeError as e:
            logger.debug(f"JSON decode error: {e}")
            ret = False
        except Exception as e:
            logger.debug(f"Unexpected error: {e}")
            ret = False
        return ret    
    
    #设备信息修改指定数据
    def update_devinfo(self, ip, port, dev_data):
        ret = False
        try:
            s_arr = {}
            s_arr['data'] = dev_data
            encoded_text = parse.urlencode(s_arr)
            url =  f"http://{ip}:{port}/modifydev?cmd=21&{encoded_text}"
            # response = urllib.request.urlopen(url, timeout = 15)
            # data = response.read()
            status_code, response_text = self.tools.http_request_get(url, timeout=15)    
            if status_code == 200:
                data = response_text
                logger.debug(data)
                arr = json.loads(data)
                if arr['code'] == 200 :
                    ret = arr['msg']
                else:
                    logger.debug("http request update_devinfo failed!")
            else:
                logger.debug(f"HTTP request failed with status code: {status_code} {response_text}")
        except json.JSONDecodeError as e:
            logger.debug(f"JSON decode error: {e}")
            ret = False
        except Exception as e:
            logger.debug(f"Unexpected error: {e}")
            ret = False
        return ret   
    
    #切换默认输入法
    def switch_default_input_method(self, ip, port, input_pkg = None):
        """
        切换默认输入法
        
        参数:
        - ip: 服务器的IP地址
        - port: 服务器的端口号
        - input_pkg: 指定的输入法包名，默认为"com.android.gmime/com.android.GmIme"
        
        返回值:
        - ret: 切换操作是否成功，成功返回True，否则返回False
        """
        ret = False
        try:
            # 如果未指定输入法包名，则使用默认值
            if input_pkg == None:
                input_pkg = "com.android.gmime/com.android.GmIme"
            
            # 构造请求URL，并发送请求
            url =  f"http://{ip}:{port}/modifydev?cmd=20&imeid={input_pkg}"
            # response = urllib.request.urlopen(url, timeout = 15)
            # data = response.read()
            status_code, response_text = self.tools.http_request_get(url, timeout=15)  
            if status_code == 200:  
                data = response_text
                logger.debug(data)
                
                # 解析响应数据
                arr = json.loads(data)
                if arr['code'] == 200 :
                    ret = arr['msg']  # 成功切换
                else:
                    logger.debug("http request update_devinfo failed!")  # 请求失败
            else:
                logger.debug(f"HTTP request failed with status code: {status_code} {response_text}")
        except json.JSONDecodeError as e:
            logger.debug(f"JSON decode error: {e}")
            ret = False
        except Exception as e:
            logger.debug(f"Unexpected error: {e}")
            ret = False
        return ret    

    #旋转摄像头
    #rot 0  1  2  3  (x90)
    # face ---- true(正面)   false(反面)
    def rot_cam(self, ip, port, rot, face):
        url =  f"http://{ip}:{port}/modifydev?cmd=22&rot={rot}&face={face}"
        # arr = self.http_request(url)
        # if arr == False:
        #     ret = arr
        # else:
        #     if arr['code'] == 200:
        #         ret = arr['msg']
        #     else:
        #         ret = arr['msg']
        #         logger.debug(f"http request update_devinfo failed!reason={ret}")  # 请求失败
        status_code, response_text = self.tools.http_request_get(url)
        if status_code == 200:
            data = response_text
            logger.debug(data)
            arr = json.loads(data)
            if arr['code'] == 200 :
                ret = arr['msg']
            else:
                logger.debug("http request rot_cam failed!")
                ret = False
        else:
            logger.debug(f"HTTP request failed with status code: {status_code} {response_text}")
            ret = False
        return ret
    

    #发送短信
    def send_sms(self, ip, port, phone, content, scaddress = None):
        url =  f"http://{ip}:{port}/sms?cmd=4"
        if scaddress == None:
            data = {
                "address": phone,
                "body": content,
            }
        else:
            data = {
                "address": phone,
                "body": content,
                "scaddress": scaddress
            }
        headers = {"Content-Type": "application/json"}

        response = requests.post(url, data=json.dumps(data), headers=headers)
        if response.status_code != 200:
            ret = False
        else:
            arr = response.json()
            if arr['code'] == 200:
                ret = arr['msg']
            else:
                ret = arr['msg']
                logger.debug(f"http request update_devinfo failed!reason={ret}")  # 请求失败
        return ret

    #设置启用全球域名加速
    def set_global_domain_accelerate(self, ip, port, enable):
        if enable == True:
            host = 'fig.moyunteng.net'
        else:
            host = 'null'
        try:
            url =  f"http://{ip}:{port}/modifydev?sethost={host}"

            # response = urllib.request.urlopen(url, timeout = 15)
            # data = response.read()
            status_code, response_text = self.tools.http_request_get(url, timeout=15)
            if status_code == 200:
                data = response_text
                logger.debug(data)
                # 解析响应数据
                arr = json.loads(data)
                if arr['code'] == 200 :
                    ret = arr['msg']  # 成功切换
                else:
                    logger.debug("http request update_devinfo failed!")  # 请求失败
                    ret = False
            else:
                logger.debug(f"HTTP request failed with status code: {status_code} {response_text}")
                ret = False
        except json.JSONDecodeError as e:
            logger.debug(f"JSON decode error: {e}")
            ret = False
        except Exception as e:
            logger.debug(f"Unexpected error: {e}")
            ret = False
        return ret     

    #上传goole 证书
    def upload_google_cert(self, ip, port, file_path):
        url =  f"http://{ip}:{port}/uploadkeybox"
        try:
            with open(file_path, 'rb') as file:
                files = {'fileToUpload': (file_path, file)}
                response = requests.post(url, files=files, timeout=15)
            if response.status_code != 200:
                ret = False
            else:
                arr = response.text
                print(arr)
                ret = True
    
        except json.JSONDecodeError as e:
            logger.debug(f"JSON decode error: {e}")
            ret = False
        except Exception as e:
            logger.debug(f"Unexpected error: {e}")
            ret = False
        return ret   
    

    #增量更新指定参数
    #str_dev_info  为json 字符串
    #{  "lac":"41764",  
    # "cid":"183968213",
    # "lat":"29.324806241241184",
    # "lon":"106.49183739636229",
    # "mcc":"310","mnc":"240",
    # "phonenumber":"\+19178078947",
    # "country":"cn","language":"zh",
    # "timezone":\"Asia/Shanghai\",
    # "opercode":"310240","opername":"Ultra",
    # "iccid":\"8901240357132212767F\",
    # "imsi":"310210123456",
    # "imei":"123456789012345",
    # "gaid":"4914c7cc-3fa4-463f-9b2c-00aa5614864e"}

    #可以更新1其中的任意 项目
    def update_fingerprint(self, ip, port, dev_info):
        #str_json = urllib.parse.quote(json.dumps(dev_info))
        ret = False
        str_json = json.dumps(dev_info)
        params = {
            "data": str_json
        }
        query_string = urllib.parse.urlencode(params)
        url =  f"http://{ip}:{port}/modifydev?cmd=7&{query_string}"
        try:
            # response = urllib.request.urlopen(url, timeout = 15)
            # data = response.read()
            # 解析响应数据
            status_code, response_text = self.tools.http_request_get(url, timeout=15)    
            if status_code == 200:
                data = response_text
                logger.debug(data)
                arr = json.loads(data)
                if arr['code'] == 200 :
                    ret = True
                else:
                    logger.debug("http request update_fingerprint failed!")  # 请求失败
            else:
                logger.debug(f"HTTP request failed with status code: {status_code} {response_text}")
                ret = False

        except json.JSONDecodeError as e:
            logger.debug(f"JSON decode error: {e}")
            ret = False
        except Exception as e:
            logger.debug(f"Unexpected error: {e}")
            ret = False
        return ret   
        

    #设置q1设备fan
    #fan_seppd 1 - 5     20%-100%
    #mode = 0 - 自动 1 - 手动
    #act = query   set
    def set_q1_fan(self, ip, port, act, mode = 0, fan_speed = 1):
        ret = False
        url =  f"http://{ip}:{port}/fan"
        if act == 'query':
            # request = urllib.request.Request(url,method="GET")
            status_code, response_text = self.tools.http_request_get(url, timeout=2)
        elif act == 'set':
            if mode == '0':
                fan_speed = 1
            params = {
                "model": mode,
                "fan":f"fan{fan_speed}"
            }
            data_encoded = urllib.parse.urlencode(params).encode('utf-8')
            # request = urllib.request.Request(url, data = data_encoded, method = "POST")
            status_code, response_text = self.tools.http_request_post(url, data=data_encoded, timeout=2)
        else:
            logger.debug("set_q1_fan act error!")
            return False
        
        try:
            # response = urllib.request.urlopen(request, timeout = 2)
            # data = response.read()
            if status_code == 200:
                data = response_text
                # 解析响应数据
                arr = json.loads(data)
                if arr['code'] == 0 :
                    ret = arr['data']
                else:
                    logger.debug("http request update_fingerprint failed!")  # 请求失败
            else:
                logger.debug(f"HTTP request failed with status code: {status_code} {response_text}")

        except json.JSONDecodeError as e:
            logger.debug(f"JSON decode error: {e}")
            ret = False
        except Exception as e:
            logger.debug(f"Unexpected error: {e}")
            ret = False
        return ret 

    #调用api 接口执行adb
    def exec_adb(self, ip, port, cmd):
        ret = False
        try:
            s_arr = {}
            s_arr['cmdline'] = cmd
            encoded_text = parse.urlencode(s_arr)
            url = f"http://{ip}:{port}/modifydev?cmd=6&{encoded_text}"
            # response = urllib.request.urlopen(url)            
            # data = response.read()
            status_code, response_test = self.tools.http_request_get(url)
            if status_code == 200:
                data = response_test
                logger.debug(data)
                arr = json.loads(data)
                if arr['code'] == 200 :
                    ret = arr['ret']
                else:
                    logger.debug("http request exec adb failed!")
            else:
                logger.debug(f"HTTP request failed with status code: {status_code} {response_test}")
        except json.JSONDecodeError as e:
            logger.debug(f"JSON decode error: {e}")
            ret = False
        except Exception as e:
            logger.debug(f"Unexpected error: {e}")
            ret = False
        return ret 
    
    # 导出app信息
    def export_app(self, ip, port, pkg, path):
        ret = False
        try:
            data = {
                'cmd': 'backup',
                'pkg': pkg,
                'saveto': path
            }
            response = requests.post(f'http://{ip}:{port}/backrestore', data=data)
            arr = response.json()
            logger.debug(arr)
            if arr["status"] == "success":
                ret = True
            else:
                logger.debug("http request export_app failed!")
                ret = False
        except json.JSONDecodeError as e:
            logger.debug(f"JSON decode error: {e}")
            ret = False
        except Exception as e:
            logger.debug(f"Unexpected error: {e}")
            ret = False
        return ret  
    # 导入app信息
    def import_app(self, ip, port, path):
        ret = False
        try:
            data = {
                'cmd': 'recovery',
                'backuppath': path
            }
            response = requests.post(f'http://{ip}:{port}/backrestore', data=data) 
            logger.debug(response.json()) 
            arr = response.json()          
            if arr["status"] == "success" :
                ret = "success"
            elif arr["status"] == "failed":
                logger.debug("http request import_app failed!")
                if "Could not find" in arr["message"]:
                    ret = "not_found"
                else:
                    ret = "failed"
        except json.JSONDecodeError as e:
            logger.debug(f"JSON decode error: {e}")
            ret = False
        except Exception as e:
            logger.debug(f"Unexpected error: {e}")
            ret = False
        return ret 
        
    #虚拟摄像头热启动或者关闭
    def camera_start(self, ip, port, action, path = None):
        #str_json = urllib.parse.quote(json.dumps(dev_info))
        ret = False
        str_path = json.dumps(path)
        params = {
            "path": str_path
        }
        query_string = urllib.parse.urlencode(params)
        url =  f"http://{ip}:{port}/camera?cmd={action}&{query_string}"
        try:
            # response = urllib.request.urlopen(url, timeout = 15)
            # data = response.read()
            status_code, response_text = self.tools.http_request_get(url, timeout=15)    
            if status_code == 200:
                data = response_text
                logger.debug(data)
                # 解析响应数据
                arr = json.loads(data)
                if arr['code'] == 200 :
                    ret = True
                else:
                    logger.debug("http request update_fingerprint failed!")  # 请求失败
            else:
                logger.debug(f"HTTP request failed with status code: {status_code} {response_text}")

        except json.JSONDecodeError as e:
            logger.debug(f"JSON decode error: {e}")
            ret = False
        except Exception as e:
            logger.debug(f"Unexpected error: {e}")
            ret = False
        return ret  
    
    #添加联系人
    def add_contact(self, ip, port, contact_list):
        ret = False
        params = {
            "data": contact_list
        }
        query_string = urllib.parse.urlencode(params)
        url =  f"http://{ip}:{port}/modifydev?cmd=23&{query_string}"
        try:
            # response = urllib.request.urlopen(url, timeout = 15)
            # result = response.read()
            status_code, response_text = self.tools.http_request_get(url, timeout=15)
            if status_code == 200:
                result = response_text
                logger.debug(result)
                # 解析响应数据
                arr = json.loads(result)
                if arr['code'] == 200 :
                    ret = True
                else:
                    logger.debug("http request update_fingerprint failed!")  # 请求失败
            else:
                logger.debug(f"HTTP request failed with status code: {status_code} {response_text}")
        except json.JSONDecodeError as e:
            logger.debug(f"JSON decode error: {e}")
            ret = False
        except Exception as e:
            logger.debug(f"Unexpected error: {e}")
            ret = False
        return ret  
    
    #伪装应用
    def disguise_app(self, ip, port, data_list):
        ret = False
        params = {
            "data": data_list
        }
        query_string = urllib.parse.urlencode(params)
        url =  f"http://{ip}:{port}/modifydev?cmd=24&{query_string}"
        print(url)
        try:
            # response = urllib.request.urlopen(url, timeout = 15)
            # result = response.read()
            status_code, response_text = self.tools.http_request_get(url, timeout=15)
            if status_code == 200:
                result = response_text
                logger.debug(result)
                # 解析响应数据
                arr = json.loads(result)
                if arr['code'] == 200 :
                    ret = True
                else:
                    logger.debug("http request update_fingerprint failed!")
            else:
                logger.debug(f"HTTP request failed with status code: {status_code} {response_text}")
                # 请求失败
        except json.JSONDecodeError as e:
            logger.debug(f"JSON decode error: {e}")
            ret = False
        except Exception as e:
            logger.debug(f"Unexpected error: {e}")
            ret = False
        return ret  
    
    # 更新谷歌信息
    def update_google(self, ip, port):
        ret = False
        url =  f"http://{ip}:{port}/modifydev?cmd=26"
        print(url)
        try:
            # response = urllib.request.urlopen(url, timeout = 15)
            # result = response.read()
            status_code, response_text = self.tools.http_request_get(url, timeout=15)
            if status_code == 200:
                result = response_text
                logger.debug(result)
                # 解析响应数据
                arr = json.loads(result)
                if arr['code'] == 200 :
                    ret = True
                else:
                    logger.debug(f"安卓接口请求失败,接口返回值是{arr}")
                    ret = False
            else:
                logger.debug(f"HTTP request failed with status code: {status_code} {response_text}")
                # 请求失败
        except json.JSONDecodeError as e:
            logger.debug(f"JSON decode error: {e}")
            ret = False
        except Exception as e:
            logger.debug(f"Unexpected error: {e}")
            ret = False
        return ret  


        