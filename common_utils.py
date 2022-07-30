import hashlib
import os
import subprocess
import tarfile
import time


def execute_cmd_quietly(cmd):
    code = os.system(cmd)
    if code != 0:
        raise Exception("命令执行失败")
    return code


def execute_cmd(cmd, quietly=False):
    if not quietly:
        print(cmd)
    code = os.system(cmd)
    if code != 0:
        if quietly:
            raise Exception("命令执行失败")
        else:
            raise Exception("命令执行失败" + cmd)
    return code


def extract_tar(tar_path, target_path):
    try:
        tar = tarfile.open(tar_path, "r:gz")
        file_names = tar.getnames()
        for file_name in file_names:
            tar.extract(file_name, target_path)
        tar.close()
    except Exception as e:
        raise Exception(e)


def get_date_tag():
    now = int(time.time())
    timeArray = time.localtime(now)
    date_tag = time.strftime("%Y%m%dT%H%M%SZ", timeArray)
    return date_tag


def get_git_short_commit_id():
    return subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD']).decode().replace("\n", "")


def get_file_md5(path):
    md5 = hashlib.md5()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            md5.update(chunk)
    return md5.hexdigest()


def get_file_size(path):
    return os.path.getsize(path)
