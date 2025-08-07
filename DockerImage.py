import ipaddress
from urllib.parse import urlparse
import requests
import logging
import json
import os
import tarfile
import hashlib
import sys
import io


class DockerImage:
    class Imageinfo:
        def __init__(self, host, name, version, hash="", authed=False, auth_info=""):
                self.host = host
                self.name = name
                self.version = version
                self.hash = hash
                self.authed = authed
                self.token = auth_info

    def getProtocol(self, tag: str):
        try:
            # Parse the host part to extract the domain or IP
            parsed_host = tag.host.split(':')[0]
            # Try to parse as an IP address
            ipaddress.ip_address(parsed_host)
            return "http"
        except ValueError:
            # If parsing fails, it's likely a domain name
            return "https"
    def fetchHash(self, imageObj: Imageinfo):
        url = f"{self.getProtocol(imageObj)}://{imageObj.host}/v2/{imageObj.name}/manifests/{imageObj.version}"

        # if debug:
        #     logging.basicConfig(level=logging.DEBUG)
        #     logging.debug(url)

        # Create a new HTTP request
        headers = {
            "Accept": "application/vnd.docker.distribution.manifest.v2+json"
        }
        try:
            resp = requests.head(url, headers=headers)
            resp.raise_for_status()  # Raise an error for bad responses
        except requests.RequestException as e:
            return str(e)

        for name, values in resp.headers.items():
            for value in values:
                if name.lower() == "etag":
                    imageObj.hash = value.strip('"')
                    return None

        return "not found head"

    def trimParam(self, input: str, key: str):
        input = input.strip()
        if input.startswith(key):
            value = input[len(key):]
            return value.strip('"')
        return ""

    def doAuth(self, imageObj: Imageinfo, info: str):
        # Bearer realm="https://dockerauth.cn-hangzhou.aliyuncs.com/auth",service="registry.aliyuncs.com:cn-hangzhou:26842",scope="repository:whsyf/dobox:pull"
        parts = info[len("Bearer "):].split(',')

        realm = ""
        service = ""
        scope = ""

        for part in parts:
            if "realm=" in part:
                realm = self.trimParam(part, "realm=")
            elif "service=" in part:
                service = self.trimParam(part, "service=")
            elif "scope=" in part:
                scope = self.trimParam(part, "scope=")

        if not all([realm, service, scope]):
            return None, f"info parse fail, {info}"

        url = f"{realm}?service={service}&scope={scope}"

        resp = requests.get(url)
        logging.debug("%d, %s", resp.status_code, resp.content.decode())
        resp.raise_for_status()

        imageObj.token = json.loads(resp.content)["token"]

        return self.fetchManifest(imageObj)

    def fetchManifest(self, imageObj: Imageinfo):
        hash = imageObj.hash if imageObj.hash else imageObj.version
        url = f"{self.getProtocol(imageObj)}://{imageObj.host}/v2/{imageObj.name}/manifests/{hash}"
        logging.debug(f"fetchManifest: {url}")

        headers = {
            "Accept": "application/vnd.docker.distribution.manifest.v2+json",
        }

        if imageObj.token != "":
            headers["Authorization"] = f"Bearer {imageObj.token}"

        try:
            resp = requests.get(url, headers=headers)
            logging.debug("%d, %s", resp.status_code, resp.content.decode())
            resp.raise_for_status()
        except requests.RequestException as e:
            if resp.status_code == 401:
                www_authenticate = resp.headers.get("Www-Authenticate")
                if www_authenticate and not imageObj.authed:
                    imageObj.authed = True
                    manifest, err = self.doAuth(imageObj, www_authenticate)
                    if err:
                        return None, err
                    return manifest, None
            return None, f"failed to fetch manifest with status code: {resp.status_code}"

        return json.loads(resp.content), None

    def parseImageName(self, tag: str):
        parts = tag.split('/', 1)
        result = self.Imageinfo(auth_info="", host="", name="", version="")
        if len(parts) != 2:
            return None

        result.host = parts[0]

        image_parts = parts[1].split(':', 1)
        if len(image_parts) == 2:
            result.name = image_parts[0]
            result.version = image_parts[1]
        else:
            result.name = image_parts[0]
            result.version = "latest"

        return result

    def toStr(self, size: int):
        units = ["B", "KB", "MB", "GB", "TB", "PB", "EB"]
        if size < 0:
            return f"{size}B"
        unit_index = 0
        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024.0
            unit_index += 1
        return f"{size:.1f}{units[unit_index]}"


    #从指定docker 地址下载docker 镜像到本地
    def downloadImage(self, tag: str, output_tar: str):
        imageObj = self.parseImageName(tag)

        logging.debug(f"{imageObj.host}, {imageObj.name}, {imageObj.version}")

        if "aliyuncs.com" not in imageObj.host:
            err = self.fetchHash(imageObj)
            if err:
                logging.error(err)

        # Fetch manifest
        manifest, err = self.fetchManifest(imageObj)
        if err:
            return f"failed to fetch manifest: {err}"

        # Create tar file
        with tarfile.open(output_tar, "w") as tar_file:
            layer_file_names = []

            digest = manifest["config"]["digest"]
            size = manifest["config"]["size"]

            config_file_name = digest.replace("sha256:", "") + ".json"

            logging.info(f"Downloading conf file => [{self.toStr(size)}] {config_file_name}")
            err = self.downloadAndAddToTar(tar_file, imageObj, digest, size, config_file_name)
            if err:
                return f"failed to download config: {err}"

            count = len(manifest["layers"])
            for i, layer in enumerate(manifest["layers"]):
                digest = layer["digest"]
                size = layer["size"]

                layer_file_name = digest.replace("sha256:", "") + "/layer.tar"
                layer_file_names.append(layer_file_name)

                logging.info(f"Downloading layer {i+1}/{count} => [{self.toStr(size)}] {layer_file_name}")
                err = self.downloadAndAddToTar(tar_file, imageObj, digest, size, layer_file_name)
                if err:
                    return f"failed to download layer {i+1}: {err}"

            manifests = [
                {
                    "config": config_file_name,
                    "repo_tags": [tag],
                    "layers": layer_file_names
                }
            ]

            data = json.dumps(manifests).encode('utf-8')
            logging.debug(data.decode())
            self.addTarEntry(tar_file, "manifest.json", data)

        return True

    def addTarEntry(self, tw, name, data):
        ti = tarfile.TarInfo(name=name)
        ti.size = len(data)
        tw.addfile(ti, io.BytesIO(data))

    # 下载配置文件和镜像文件
    def downloadAndAddToTar(self, tw: tarfile, imageObj: Imageinfo, digest: str, size: int, tar_name: str):
        url = f"{self.getProtocol(imageObj)}://{imageObj.host}/v2/{imageObj.name}/blobs/{digest}"

        logging.debug(f"{url} => {tar_name}")

        headers = {}
        if imageObj.token:
            headers["Authorization"] = f"Bearer {imageObj.token}"

        try:
            resp = requests.get(url, headers=headers)
            resp.raise_for_status()
        except requests.RequestException as e:
            return str(e)

        # Add blob to tar
        ti = tarfile.TarInfo(name=tar_name)
        ti.size = size
        tw.addfile(ti, io.BytesIO(resp.content))

        return None

    def calculateSha256(self, file_path):
        # Open the file for reading
        with open(file_path, "rb") as file:
            # Create a new SHA-256 hash object
            hasher = hashlib.sha256()

            # Copy the file content to the hash object
            for chunk in iter(lambda: file.read(4096), b""):
                hasher.update(chunk)

            # Get the hash sum as a hexadecimal string
            hash_string = hasher.hexdigest()

        return hash_string
