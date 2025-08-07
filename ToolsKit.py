import os
import sys
import psutil
import platform
import requests
import json
import hashlib
import time
import paramiko
import subprocess
import re
import urllib.request
import socket



 
class ToolsKit(object):

        
    #获取当前程序启动参数
    #按照空格分割
    def GetArgv(self):
        args = sys.argv[1:]  # 跳过第一个参数（脚本名）
    
        # 按照空格分割并输出为字典
        params_dict = {}
        for arg in args:
            key, value = arg.split('=')
            params_dict[key] = value
        return params_dict
            

    #获取当前程序的可执行文件路径
    def GetRootPath(self):

        #in bundle
        args = sys.argv[0]
        #判断是否 是相对路径 还是绝对路径
        if not os.path.exists(args): 
            pwd = os.getcwd()
            bundle_dir = pwd + args

            #防止路径文件出错
            if platform.system() == 'Windows':
                bundle_dir = pwd
        else:
            bundle_dir = os.path.dirname(args)
            if bundle_dir == '':
              bundle_dir = os.getcwd()
        return bundle_dir
    
    #判断是否多次运行
    #return   True 存在相同进程实例  False
    
    def check_multi_run(self):
        if platform.machine() == 'aarch64':         #arm板 是容器部署不进行判断
            ret = False
        else:
            ret = None
            root_path = self.GetRootPath()
            pid_file = root_path + "/conf/myt.pid"
            if os.path.isfile(pid_file):
                with open(pid_file,'r') as f:
                    pid = f.read()
                    if self.check_process(pid) == True:
                        ret =  True
                    else:
                        ret = False
            else:
                ret = False

            if ret == False:
                with open(pid_file, 'w') as f:
                    f.write(str(os.getpid()))
        return ret
    
    #判断进程是否存在
    def check_process(self, pid):
        try:
            process = psutil.Process(int(pid))
            return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            return False
        

    #用户登录获取token
    def UserLogin(self, uname, upwd):
        # User credentials and type
        url = "http://api.moyunteng.com/api.php"
        login_data = {
            "type": "login",
            "data": json.dumps({
                "uname": uname,   
                "pwd": hashlib.md5(upwd.encode()).hexdigest(),  
                "spid": "0"
            })
        }

        # Make the POST request for login
        response = requests.post(url, params=login_data)
        if response.status_code == 200:
            response_data = response.json()
            if response_data.get("code") == "200":
                print("Login successful.")
                root_path = self.GetRootPath()
                token_cache = root_path + "/conf/token.json"

                #写入时间和有效期
                data_json = {}
                data_json['time'] = int(time.time() + 300)
                #data_json['time'] = int(time.time() + 120)
                data_json['token'] = response_data['data']['token']

                with open(token_cache, 'w') as f:
                    f.write(json.dumps(data_json))
                    #f.write(response_data['data']['token'])
                return response_data['data']['token']
            else:
                print("Failed to login:", response_data.get("msg"))
        else:
            print("Login request failed with status code:", response.status_code)
        return None



    # Function to send a command and print the response
    def send_command_and_print_output(self, shell, cmd, input= False, endstr = None):
        shell.send(cmd + "\n")  # Send the command followed by a newline
        output = ""
        while True:
            data = shell.recv(65535).decode()  # Receive the response (large buffer size)
            output += data
            #print(data)
            if input == True:
                break
            else:
                if endstr is None:
                    if data.endswith("# ") or data.endswith("~$ ") or data.endswith("\x1b[6n"):  # Check for shell prompt
                        break
                else:
                    if data.endswith(endstr) :  # Check for shell prompt
                        break
        time.sleep(0.5)
        return output    #修改主机docker 配置文件
    
    # 通过 ssh root 权限重启 系统
    def ssh_client_reboot(self, ip, uname='user', upwd = 'myt', root_pwd = 'myt'):
        ssh = paramiko.SSHClient()
        try:
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(ip, 22, uname, upwd)
            shell = ssh.invoke_shell()
            self.send_command_and_print_output(shell, 'su', False, 'Password: ')
            self.send_command_and_print_output(shell, root_pwd, True)
            #Login  and su
            self.send_command_and_print_output(shell, 'echo "b" > /proc/sysrq-trigger')
            #self.send_command_and_print_output(shell, '/sbin/openrc shutdown')
            shell.close()
            ssh.close()
            #print(f"{ip} done!")
        except Exception as e:
            print(e)
    
    # 通过 ssh root 权限 执行命令
    def ssh_client_shell(self, ip, cmd, uname='user', upwd = 'myt', root_pwd = 'myt'):
        ssh = paramiko.SSHClient()
        try:
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(ip, 22, uname, upwd)
            shell = ssh.invoke_shell()
            self.send_command_and_print_output(shell, 'su', False, 'Password: ')
            self.send_command_and_print_output(shell, root_pwd, True)
            #Login  and su
            self.send_command_and_print_output(shell, cmd)
            #self.send_command_and_print_output(shell, '/sbin/openrc shutdown')
            shell.close()
            ssh.close()
            #print(f"{ip} done!")
        except Exception as e:
            print(e)

    #获取本机ip
    def get_local_ip(self):
        ret = ''
        try:
            result = subprocess.run(['hostname', '-i'], capture_output=True, text=True, check=True)
            ip = result.stdout.strip()
            ret = ip
        except subprocess.CalledProcessError as e:
            ret = ''
        return ret

    #下载指定的文件
    def download_file(self, url, local_filename):
        ret = False
        try:
            with requests.get(url, stream=True) as r:
                r.raise_for_status()
                with open(local_filename, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)

            ret = True
        except Exception as e:
            ret  = False
        return ret
    
    #获取镜像列表
    def get_img_list(self):
        try:
            img_arr = []
            url = "http://www.moyunteng.com/api/api.php?type=get_mirror_list2"
            response = urllib.request.urlopen(url)            
            data = response.read()
            #logger.debug(data)
            arr = json.loads(data)
            if arr['code'] == '200':
                for item in arr['data']:
                    img = {}
                    img['name'] = item['name']
                    img['id'] = item['id']
                    img['image'] = item['url']
                    img_arr.append(img)
        except urllib.error.HTTPError as e:
            pass
        except urllib.error.URLError as e:
            pass
        return img_arr 


    def sanitize_filename(self,filename):
        # 定义非法字符的正则表达式（含 FAT32/exFAT 限制）
        #illegal_chars = r'[\\/*?:"<>|()]'  # 注意转义反斜杠
        illegal_chars = r'[\\/*?:"<>|()\s]'  # \s 匹配所有空白符（空格、制表符等）
        # 替换非法字符为下划线
        sanitized = re.sub(illegal_chars, '_', filename)
        # 合并连续的下划线（如 "file__name" → "file_name"）
        sanitized = re.sub(r'_+', '_', sanitized)
        
        # 处理保留名称（如 CON, AUX 等）
        main_part, ext = os.path.splitext(sanitized)
        reserved_names = {
            'CON', 'PRN', 'AUX', 'NUL',
            'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
            'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
        }
        if main_part.upper() in reserved_names:
            main_part += '_'
        
        # 重新组合主名和扩展名
        new_name = main_part + ext
        
        # 去除末尾的点和空格（如 "file." → "file"）
        new_name = new_name.rstrip('. ').strip()
        
        # 处理空文件名（如输入全是非法字符）
        if not new_name:
            new_name = 'unnamed'
        
        return new_name


    
    #使用临时文件存储
    def get_tmp_file_path(self):
        root_path = self.GetRootPath()
        tmp_file_path = os.path.join(root_path, "tmp")
        return tmp_file_path
    
    #初始化临时文件目录
    def init_tmp_file(self):
        file_path = self.get_tmp_file_path()
        if not os.path.exists(file_path):
            os.makedirs(file_path)
        else:
            #清理临时文件
            for file in os.listdir(file_path):
                file_full_path = os.path.join(file_path, file)
                if os.path.isfile(file_full_path):
                    os.remove(file_full_path)

    
    # 设置 key-value 对
    def set_tmpfile_value(self, key, value):
        file_path = self.get_tmp_file_path()
        file_path = os.path.join(file_path, key)
        with open(file_path, 'w') as f:
            json.dump(value, f)

    # 获取 key 对应的 value
    def get_tmpfile_value(self, key):
        try:
            file_path = self.get_tmp_file_path()
            file_path = os.path.join(file_path, key)
            kv_store = None
            if os.path.isfile(file_path):
                with open(file_path, 'r') as f:
                    kv_store = json.load(f)
        except Exception as e:
            if os.path.isfile(file_path):
                os.remove(file_path)
        return kv_store

    # 删除 key-value 对
    def delete_tmpfile_value(self, key):
        file_path = self.get_tmp_file_path()
        file_path = os.path.join(file_path, key)
        if os.path.isfile(file_path):
            os.remove(file_path)
        

    #配置全局一次文件读写模块   

    #生命周期为单次运行期间 每次启动会清理该文件
    def init_kv_file(self):
        kv_file_path = self.get_kv_file_path()
        if os.path.isfile(kv_file_path):
            os.remove(kv_file_path)

    #使用kv存储方式
    def get_kv_file_path(self):
        root_path = self.GetRootPath()
        kv_file_path = os.path.join(root_path, "conf", "run_kv_store.bin")
        return kv_file_path

    # 读取 key-value 存储文件
    def read_kv_store(self):
        kv_file_path = self.get_kv_file_path()
        if os.path.isfile(kv_file_path):
            with open(kv_file_path, 'r') as f:
                kv_store = json.load(f)
        else:
            kv_store = {}
        return kv_store

    # 写入 key-value 存储文件``
    def write_kv_store(self, kv_store):
        kv_file_path = self.get_kv_file_path()
        with open(kv_file_path, 'w') as f:
            json.dump(kv_store, f)

    # 设置 key-value 对
    def set_key_value(self, key, value):
        kv_store = self.read_kv_store()
        kv_store[key] = value
        self.write_kv_store(kv_store)

    # 获取 key 对应的 value
    def get_key_value(self, key):
        kv_store = self.read_kv_store()
        return kv_store.get(key)

    # 删除 key-value 对
    def delete_key_value(self, key):
        kv_store = self.read_kv_store()
        if key in kv_store:
            del kv_store[key]
            self.write_kv_store(kv_store)

   



    #全生命周期key-value 存储模块
    #使用kv存储方式
    def global_get_kv_file_path(self):
        root_path =  self.GetRootPath() + "/backup/"
        if not os.path.exists(root_path):
            os.makedirs(root_path)
        conf_path = os.path.join(root_path, "conf")
        if not os.path.exists(conf_path):
            os.makedirs(conf_path)
        kv_file_path = os.path.join(root_path, "conf", "global_kv_store.bin")
        return kv_file_path

    # 读取 key-value 存储文件
    def global_read_kv_store(self):
        kv_file_path = self.global_get_kv_file_path()
        if os.path.isfile(kv_file_path):
            with open(kv_file_path, 'r') as f:
                kv_store = json.load(f)
        else:
            kv_store = {}
        return kv_store

    # 写入 key-value 存储文件
    def global_write_kv_store(self, kv_store):
        kv_file_path = self.global_get_kv_file_path()
        with open(kv_file_path, 'w') as f:
            json.dump(kv_store, f, indent=4)
            f.flush()
            os.fsync(f.fileno())


    # 设置 key-value 对
    def global_set_key_value(self, key, value):
        kv_store = self.global_read_kv_store()
        kv_store[key] = value
        self.global_write_kv_store(kv_store)

    # 获取 key 对应的 value
    def global_get_key_value(self, key):
        kv_store = self.global_read_kv_store()
        return kv_store.get(key)

    # 删除 key-value 对
    def global_delete_key_value(self, key):
        kv_store = self.global_read_kv_store()
        if key in kv_store:
            del kv_store[key]
            self.global_write_kv_store(kv_store)
    
    #端口探测
    def is_port_open(self, host, port, timeout=1):
        """
        检查指定主机的端口是否处于监听状态。

        参数:
            host (str): 目标主机名或IP地址。
            port (int): 要检测的端口号。
            timeout (int, 可选): 连接超时时间（秒），默认为2秒。

        返回:
            bool: 如果端口处于监听状态返回True，否则返回False。
        """
        try:
            # 使用create_connection自动处理地址解析和连接
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except OSError:
            # 捕获所有与连接相关的错误（如超时、拒绝连接、网络不可达等）
            return False

    #封装一个HTTP GET 请求的方法
    def http_request_get(self, url, timeout=2):
        """
        发送一个HTTP GET请求并返回响应内容。

        参数:
            url (str): 请求的URL。
            timeout (int, 可选): 请求超时时间（秒），默认为2秒。

        返回:
            status, str: 响应内容
            status: 200  返回成功      
            status: 0    失败
        """
        ret = (0, '')
        status_code = 0
        try:
            response = requests.get(url, timeout=timeout)
            status_code = response.status_code
            response.raise_for_status()  # 检查请求是否成功
        except requests.exceptions.HTTPError as errh:
            print(f"HTTP Error: {errh}")
            ret =  (status_code,type(errh).__name__)
        except requests.exceptions.ConnectionError as errc:
            print(f"Error Connecting: {errc}")
            ret =  (status_code,type(errc).__name__)
        except requests.exceptions.Timeout as errt:
            print(f"Timeout Error: {errt}")
            ret =  (status_code,type(errt).__name__)
        except requests.exceptions.RequestException as err:
            print(f"Something went wrong: {err}")
            ret =  (status_code,type(err).__name__)
        else:
            ret =  (status_code,response.text)
        return ret
    

    #封装一个HTTP POST 请求的方法
    def http_request_post(self, url, data=None, timeout=2):
        """
        发送一个HTTP POST请求并返回响应内容。

        参数:
            url (str): 请求的URL。
            data (dict, 可选): 要发送的数据，默认为None。
            timeout (int, 可选): 请求超时时间（秒），默认为2秒。

        返回:
            str: 响应内容。
        """
        ret = (0, '')
        status_code = 0
        try:
            response = requests.post(url, data=data, timeout=timeout)
            status_code = response.status_code
            response.raise_for_status()  # 检查请求是否成功
        except requests.exceptions.HTTPError as errh:
            print(f"HTTP Error: {errh}")
            ret =  (status_code,type(errh).__name__)
        except requests.exceptions.ConnectionError as errc:
            print(f"Error Connecting: {errc}")
            ret =  (status_code,type(errc).__name__)
        except requests.exceptions.Timeout as errt:
            print(f"Timeout Error: {errt}")
            ret =  (status_code,type(errt).__name__)
        except requests.exceptions.RequestException as err:
            print(f"Something went wrong: {err}")
            ret =  (status_code,type(err).__name__)
        else:
            ret =  (status_code,response.text)
        return ret