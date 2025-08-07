import subprocess
import os,sys,platform
from common.logger import logger
import urllib.request
import urllib.error
from common.ToolsKit import ToolsKit

class dockerComposeApi(object):

    def __init__(self):
        tools = ToolsKit()
        root_path = tools.GetRootPath()
        #self.cfg_dir = os.getcwd() + "/tmp/" 
        self.cfg_dir = root_path + "/tmp/"
        if os.path.exists(self.cfg_dir) == False:
            os.mkdir(self.cfg_dir)
        
        if sys.platform == "linux":
            if platform.machine() == 'aarch64':         
                self.dc_cmd = root_path + "/tools/arm/docker-compose"
            else:
                self.dc_cmd = root_path + "/tools/linux/docker-compose"
        elif sys.platform == "darwin":
            if platform.machine() == 'x86_64':         
                self.dc_cmd = root_path + "/tools/mac_intelchip/docker-compose"
            else:  #arm64
                self.dc_cmd = root_path + "/tools/mac_applesilicon/docker-compose"
        else:
            self.dc_cmd = root_path + "/tools/win/docker-compose.exe"
            #self.dc_cmd = os.getcwd() + "/_internal/tools/win/docker-compose.exe"
    

    """单例模式"""
    @classmethod
    def get_instance(cls, *args, **kwargs):
        if not hasattr(dockerComposeApi, "_instance"):
            dockerComposeApi._instance = dockerComposeApi(*args, **kwargs)
        return dockerComposeApi._instance
    
    #执行shell 命令
    def _exec_cmd(self, shell_command):
        try:
            ret = False
            # p = subprocess.Popen(['ls', '-l'], stdout=subprocess.PIPE)
            # out, err = p.communicate()
            output = subprocess.check_output(shell_command, shell=True)
            #print("Shell command executed successfully.")
            #print("Output:")
            #print(output.decode('utf-8'))
            ret = output.decode('utf-8')
        except subprocess.CalledProcessError as e:
            logger.debug("Error executing shell command :",shell_command)
            logger.debug("Return code:", e.returncode)
            logger.debug("Error message:", e.output.decode('utf-8'))
        return ret

    #允许后台执行
    def _run_cmd(self, shell_command):
        try:
            ret = False
            # p = subprocess.Popen(['ls', '-l'], stdout=subprocess.PIPE)
            # out, err = p.communicate()
            output = subprocess.run(shell_command, shell=True)
            #print("Shell command executed successfully.")
            #print("Output:")
            #print(output.decode('utf-8'))
            #print(f"return_code:{output.returncode}")
            ret = output.returncode
        except subprocess.CalledProcessError as e:
            logger.debug("Error executing shell command :",shell_command)
            logger.debug("Return code:", e.returncode)
            logger.debug("Error message:", e.output.decode('utf-8'))
        return ret 

    #安装docker compose 文件
    def run(self, ip, url):
        ret = False
        if os.path.exists(self.dc_cmd) == True:
            local_dir = os.getcwd() + "/tmp/" 
            if os.path.exists(local_dir) == False:
                os.mkdir(local_dir)
            file_path = local_dir + "tmp.yml"
            if os.path.exists(file_path) == True:
                os.remove(file_path)
            try:
                urllib.request.urlretrieve(url, file_path)
                cmd = f"{self.dc_cmd} --host {ip}:2375 --file {file_path} up -d --force-recreate --build"
                exit_code = self._run_cmd(cmd)
                logger.debug(f"exec code:{exit_code}")
                if exit_code == 0:
                    ret = True
            except urllib.error.HTTPError as e:
                logger.debug(f"HTTPError: {e.code} - {e.reason}")
                ret = False
            except urllib.error.URLError as e:
                logger.debug(f"URLError: {e.reason}")
                ret = False
        else:
            logger.debug(f"docker-compose {self.dc_cmd} not found!")
        return  ret
