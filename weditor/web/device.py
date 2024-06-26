# coding: utf-8
#

import abc

import adbutils
import uiautomator2 as u2
import wda
from logzero import logger
from PIL import Image

from . import uidumplib
from .proto import PlatformEnum

import os

class DeviceMeta(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def screenshot(self) -> Image.Image:
        pass

    def dump_hierarchy(self) -> str:
        pass

    @abc.abstractproperty
    def device(self):
        pass


class _AndroidMock(DeviceMeta):
    def __init__(self,data_fp):
        self.data_fp = data_fp
        self.index = 0
        self.resolution = (1080, 2400)
        self.maxindex = max([int(item.split(".")[0]) for item in os.listdir(data_fp) if item.endswith(".xml")])
    
    def setIndex(self, index):
        self.index = index
    
    def screenshot(self) -> Image:
        screenshot_path = os.path.join(self.data_fp, f"{self.index}.png")
        return Image.open(screenshot_path)


    def dump_hierarchy(self) -> str:
        hierarchy_path = os.path.join(self.data_fp, f"{self.index}.xml")
        with open(hierarchy_path, "r") as f:
            return f.read()
    
    def dump_hierarchy2(self):
        hierarchy_path = os.path.join(self.data_fp, f"{self.index}.xml")
        with open(hierarchy_path, "r") as f:
            page_xml = f.read()
        page_json = uidumplib.android_hierarchy_to_json(
            page_xml.encode('utf-8'))
        
        current_fp = os.path.join(self.data_fp, f"{self.index}.activity")
        with open(current_fp, "r") as f:
            current_activity = f.read()
        current_package = current_activity.split("/")[0]
        return {
            "xmlHierarchy": page_xml,
            "jsonHierarchy": page_json,
            "activity": current_activity,
            "packageName":current_package,
            "windowSize": self.resolution,
        }
    
    @property
    def device(self):
        return "AndroidMock"

class _AndroidADB(DeviceMeta):
    def __init__(self, device_url: str):
        if not device_url:
            self._d = adbutils.device()
        else:
            self._d = adbutils.device(device_url)
    
    def screenshot(self) -> Image:
        return self._d.screenshot()
    
    def dump_hierarchy(self) -> str:
        return self._d.dump_hierarchy()
    
    def dump_hierarchy2(self):
        current = self._d.app_current()
        page_xml = self._d.dump_hierarchy()
        page_json = uidumplib.android_hierarchy_to_json(
            page_xml.encode('utf-8'))
        return {
            "xmlHierarchy": page_xml,
            "jsonHierarchy": page_json,
            "activity": current.activity,
            "packageName": current.package,
            "windowSize": self._d.window_size(),
        }

    @property
    def device(self):
        return self._d
        
class _AndroidUiautomatorDevice(DeviceMeta):
    def __init__(self, device_url):
        d = u2.connect(device_url)
        # 登陆界面无法截图，就先返回空图片
        d.settings["fallback_to_blank_screenshot"] = True
        self._d = d

    def screenshot(self):
        return self._d.screenshot()

    def dump_hierarchy(self):
        return uidumplib.get_android_hierarchy(self._d)

    def dump_hierarchy2(self):
        current = self._d.app_current()
        page_xml = self._d.dump_hierarchy(pretty=True)
        # 临时增加测试
        # import adbutils
        page_json = uidumplib.android_hierarchy_to_json(
            page_xml.encode('utf-8'))
        return {
            "xmlHierarchy": page_xml,
            "jsonHierarchy": page_json,
            "activity": current['activity'],
            "packageName": current['package'],
            "windowSize": self._d.window_size(),
        }

    @property
    def device(self):
        return self._d


class _AppleDevice(DeviceMeta):
    def __init__(self, device_url):
        logger.info("ios connect: %s", device_url)
        if device_url == "":
            c = wda.USBClient()
        else:
            c = wda.Client(device_url)
        self._client = c
        self.__scale = c.scale

    def screenshot(self):
        try:
            return self._client.screenshot(format='pillow')
        except:
            import tidevice
            return tidevice.Device().screenshot()

    def dump_hierarchy(self):
        return uidumplib.get_ios_hierarchy(self._client, self.__scale)

    def dump_hierarchy2(self):
        return {
            "jsonHierarchy":
            uidumplib.get_ios_hierarchy(self._client, self.__scale),
            "windowSize":
            self._client.window_size(),
        }

    @property
    def device(self):
        return self._client


cached_devices = {}


def connect_device(platform: PlatformEnum, device_url: str):
    """
    Returns:
        deviceId (string)
    """
    device_id = platform + ":" + device_url
    if platform == PlatformEnum.AndroidMock:
        # device_url is the data folder path
        d = _AndroidMock(device_url)

    elif platform == PlatformEnum.AndroidUIAutomator2:
        d = _AndroidUiautomatorDevice(device_url)
    elif platform == PlatformEnum.AndroidADB:
        d = _AndroidADB(device_url)
    elif platform == PlatformEnum.IOS:
        d = _AppleDevice(device_url)
    else:
        raise ValueError("Unknown platform", platform)

    cached_devices[device_id] = d
    return device_id


def get_device(id):
    d = cached_devices.get(id)
    if d is None:
        platform, uri = id.split(":", maxsplit=1)
        connect_device(platform, uri)
    return cached_devices[id]
