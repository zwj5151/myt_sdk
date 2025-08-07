from common.dockerApi import dockerApi
from common.ToolsKit import ToolsKit
import os
import shutil
from common.logger import logger

#该类为执行 myt盒子的rom文件操作
class mytRomHandle(object):

    MYTOLED_MD5 = "E836548ABDC0DB96A50689E97209E958"

    def __init__(self,ip = "172.17.0.1"):
        #获取当前主机的固件信息
        self.ip = ip
        self.getinfo = self.getRomInfo()

    #获取当前主机的固件信息
    def getRomInfo(self):
        try:
            #api = dockerApi("172.17.0.1")
            api = dockerApi(self.ip)
            cmd = "getinfo"
            exec_ret = api.SDK_SHELL_COMMAD_HOST(cmd)
            if exec_ret == False:
                exec_ret = ""
            else:
                #解析返回的信息
                #start|1548421155|{"ip":"192.168.30.1","hwaddr":"62:A9:7F:36:61:31","cputemp":37,"cpuload":"4%","memtotal":"15944","memuse":"6762","mmctotal":"239280","mmcuse":"77273","version":"2024.v0.2.0-202408081541","deviceId":"7b44d9766fb439dd2d3dc45bf6c82b30","model":"c1"}|end
                arr = exec_ret.split("|")
                exec_ret = arr[2]
                #将数据保存到字典中
                tools = ToolsKit()
                tools.set_key_value("getinfo",exec_ret)
   
            #print(exec_ret)
        except Exception as e:
            logger.debug("Exception Error:" + str(e))
            exec_ret = ""
        return exec_ret

    def updateRomEvents(self):
        try:
            self.updateQ1Rom()
        except Exception as e:
            logger.debug("Exception Error:" + str(e))

    def updateQ1Rom(self):
        try:
            if 'q1' in self.getinfo:
                api = dockerApi(self.ip)
                cmd = "md5sum /usr/share/mytgui/mytOled | awk '{print $1}'"
                exec_ret = api.SDK_SHELL_COMMAD_HOST(cmd)
                exec_ret = exec_ret.strip()
                if len(exec_ret) != 32:
                    logger.debug("获取md5值失败!")
                else:
                    if exec_ret.strip() != self.MYTOLED_MD5.lower():
                        #执行更新操作
                        tools = ToolsKit()
                        root_path = tools.GetRootPath()
                        file_path = os.path.join(root_path, "tools")
                        file_path = os.path.join(file_path, "mytOled")
                        #1 本地拷贝到共享目录
                        dest_path = os.path.join(root_path, "backup")
                        dest_file = os.path.join(dest_path, "mytOled")
                        if os.path.exists(dest_file):
                            os.remove(dest_file)
                        
                        shutil.copy(file_path, dest_file)

                        #2 从共享目录拷贝到主机
                        cmd = f"cp /mmc/data/sdk_backup/mytOled /usr/share/mytgui/mytOled && chmod +x /usr/share/mytgui/mytOled"
                        exec_ret = api.SDK_SHELL_COMMAD_HOST(cmd)
                        #logger.debug(exec_ret)
                        tools = ToolsKit()
                        cmd = "/etc/init.d/mytgui restart"
                        tools.ssh_client_shell(self.ip, cmd)
                        os.remove(dest_file)
                    else:
                        logger.debug("当前主机的固件已是最新版本!")
        except Exception as e:
            logger.debug("Exception Error:" + str(e))
