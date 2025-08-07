import ctypes
import sys
import time
import os
from common.logger import logger
import platform
from common.ToolsKit import ToolsKit

# myt rpc  lib
class myt_pc_svr(object):    
    def __init__(self) -> None:
        if sys.platform != "linux":
            tools = ToolsKit()
            root_path = tools.GetRootPath()
            
            self._lib_PATH = root_path + "/lib/myt_winSDK.dll"
            #self._lib_PATH = root_path + "/lib/MYTDLL.dll"
            #self._lib_PATH = os.path.dirname(os.path.abspath(__file__)) + "/../lib/myt_winSDK.dll"
            logger.debug(f"myt_pc_svr lib path:{self._lib_PATH}")

    def init(self, path):
        self._dll = ctypes.WinDLL(self._lib_PATH)
        self.path = path

    #extrainfo   "192.168.181.27:10034#192.168.181.27:10010"  ip+port
    def run(self, ip, vport, cport, name, extraInfo = None):
        ret = False
        if platform.machine() != 'aarch64':         #arm板不支持该接口
            import win32gui
            import win32con
            hwnd = win32gui.GetForegroundWindow()
            pid = os.getpid()
            #extrainfo = "192.168.181.27:10034#192.168.181.27:10010"
            #(const char* ip, int vport, int cport, const char* name,int orient, const char* exec, HWND parentHwnd, DWORD parent_pid);
            #(const WCHAR* ip, int vport, int cport, const WCHAR* name, int orient, const WCHAR* exec, HWND parentHwnd, DWORD parent_pid, const WCHAR* extra = NULL);
            self._dll.mytSDK_createWindows_W.argtypes = [ctypes.c_wchar_p, ctypes.c_int, ctypes.c_int, ctypes.c_wchar_p,  ctypes.c_int,  ctypes.c_wchar_p, ctypes.c_int, ctypes.c_int, ctypes.c_wchar_p]
            self._dll.mytSDK_createWindows_W.restype  = ctypes.c_int
            #self._handle = self._dll.mytSDK_createWindows_W(bytes(ip, "utf-8"), vport,cport,  bytes(name, "GBK"), 0, bytes(self.path, encoding = "GBK"), hwnd,  pid, None)
            self._handle = self._dll.mytSDK_createWindows_W(ip, vport,cport,  name, 0, self.path, hwnd,  pid, extraInfo)
            t =0
            while True:                
                hwnd = win32gui.FindWindow(None, name)
                if hwnd!=0 :
                    win32gui.SetWindowPos(hwnd,win32con.HWND_TOPMOST, 0, 0, 0, 0, win32con.SWP_NOMOVE |   win32con.SWP_NOSIZE )
                    ret = True
                    break
                t=t+1
                if t>4: break
                time.sleep(0.25)
        return ret
                
