import os
import sys
import time

import paramiko

from config import *

deploy_config = get_config()
print("using config {}, wait 10 seconds for double check".format(type(deploy_config).__name__))
time.sleep(10)

def init_jumpserver():
    jumpbox = paramiko.SSHClient()

    jumpbox.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    jumpbox.connect(BaseConfig.JUMP_IP, username="root", port=deploy_config.JUMP_PORT, key_filename=deploy_config.SSH_KEY_FILE)
    stdin, stdout, stderr = jumpbox.exec_command("hostname -I | awk '{print $1}'")
    jumpbox_inner_ip = None
    for line in stdout:
        jumpbox_inner_ip = line

    return jumpbox, jumpbox_inner_ip


def init_worker_root_connection(jumpbox, jumpbox_inner_ip, worker_ip):
    jumpbox_transport = jumpbox.get_transport()
    src_addr = (jumpbox_inner_ip, deploy_config.JUMP_PORT)

    target_addr = worker_ip
    dest_addr = (target_addr, 22)
    jumpbox_channel = jumpbox_transport.open_channel("direct-tcpip", dest_addr, src_addr)

    target = paramiko.SSHClient()
    target.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    target.connect(target_addr, username='root', password="QAZ2wsx!@#", sock=jumpbox_channel)
    return target


def init_worker_mars_connection(jumpbox, jumpbox_inner_ip, worker_ip):
    jumpbox_transport = jumpbox.get_transport()
    src_addr = (jumpbox_inner_ip, deploy_config.JUMP_PORT)

    target_addr = worker_ip
    dest_addr = (target_addr, 22)
    jumpbox_channel = jumpbox_transport.open_channel("direct-tcpip", dest_addr, src_addr)

    target = paramiko.SSHClient()
    target.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    target.connect(target_addr, username='mars', password="marsPWD", sock=jumpbox_channel)
    return target


def print_buffer(stdout):
    for line in stdout:
        print(line)


def exec_cmd(worker_connection, command, is_shell=False):
    print("executing ", command)
    if is_shell:
        chan = worker_connection.invoke_shell()
        out = chan.recv(9999)
        commands = command.split(";")
        for cmd in commands:
            print("sending", cmd)
            chan.send('{}\n'.format(cmd))
            while not chan.recv_ready():
                time.sleep(1)
            s = chan.recv(40960)
            print(s)
    else:
        _, stdout, stderr = worker_connection.exec_command(command + " 2>&1", get_pty=True)
        stdstr = ""
        stdout.channel.settimeout(1800)
        while not stdout.channel.exit_status_ready():
            try:
                out = stdout.channel.recv(1024).decode("utf-8")
            except Exception as e:
                print("timeout")
                raise e
            stdstr += out
            print(out)
        print(str(stdstr))
        return str(stdstr)


# 执行初始化创建用户指令，暂不初始化外挂磁盘
def initial_vms(worker_connections):
    for worker_connection in worker_connections:
        stdout = exec_cmd(worker_connection, "grep -c '^mars:' /etc/passwd")
        print(str(stdout))
        if "1" in str(stdout):
            print("already exists, skip")
            return

        exec_cmd(worker_connection, "useradd -s /bin/bash -d /home/mars -m mars")
        exec_cmd(worker_connection, "echo \"mars:marsPWD\" | chpasswd")
        exec_cmd(worker_connection, "echo \"mars ALL=(ALL) NOPASSWD:ALL\" >> /etc/sudoers")
        exec_cmd(worker_connection, "sudo -H -u mars bash -c 'mkdir /home/mars/.ssh'")
        exec_cmd(worker_connection, "rm -rf /home/mars/.ssh/id_rsa")
        exec_cmd(worker_connection,
                 "sudo -H -u mars bash -c 'ssh-keygen -t rsa -b 2048 -f /home/mars/.ssh/id_rsa -q -N \"\"'")


def upload_excel(worker_connection):
    exec_cmd(worker_connection, "rm -rf /home/mars/MARS_CONF.xlsx")
    exec_cmd(worker_connection, "rm -rf /home/mars/BaseDeploy/MARS_CONF.xlsx")
    exec_cmd(worker_connection, "rm -rf /home/mars/mars_charts/MARS_CONF.xlsx")
    ftp_client = worker_connection.open_sftp()
    ftp_client.put(deploy_config.excel_path, "/home/mars/MARS_CONF.xlsx")
    ftp_client.close()


def is_file_exists(worker_connection, filepath):
    stdout = exec_cmd(worker_connection, "ls {}".format(filepath))
    if "No such file or directory" in stdout:
        return False
    else:
        return True


def download_basedeploy(worker_connection):
    if is_file_exists(worker_connection, "/home/mars/BaseDeploy"):
        print("skip download baseDeploy")
        return

    exec_cmd(worker_connection, "rm -rf BaseDeploy-mars-release-1.0.*")
    exec_cmd(worker_connection, "wget %s" % deploy_config.BASE_DEPLOY_URL)
    exec_cmd(worker_connection, "tar zxvf BaseDeploy-mars-release-1.0.10.tar.gz")


def deploy_basedeploy(worker_connection):
    exec_cmd(worker_connection, "cp /home/mars/MARS_CONF.xlsx /home/mars/BaseDeploy")
    exec_cmd(worker_connection,
             "cd /home/mars/BaseDeploy;cp ~/.ssh/id_rsa ./Deploy.key;cp ~/.ssh/id_rsa.pub ./Deploy.key.pub;cp ~/.ssh/id_rsa ./Mars.key;cp ~/.ssh/id_rsa.pub ./Mars.key.pub")
    stdout = exec_cmd(worker_connection, "cd /home/mars/BaseDeploy;./configure.sh")
    if "Cannot run configure.sh again after installation" not in stdout and "Modify init/env.sh." not in stdout:
        print("failed configure")
        sys.exit(1)
    stdout = exec_cmd(worker_connection, "cd /home/mars/BaseDeploy;./install.sh")
    if "Congratulations!" not in stdout and "Installation has been finished, will not install again." not in stdout:
        print("failed base deploy")
        sys.exit(1)


def download_mars_charts(worker_connection):
    if not is_file_exists(worker_connection, "/home/mars/{}".format(os.path.basename(deploy_config.MARS_CHARTS_URL))):
        exec_cmd(worker_connection, "rm -rf mars_charts.*")
        exec_cmd(worker_connection, "wget {}".format(deploy_config.MARS_CHARTS_URL))
        if is_file_exists(worker_connection, "/home/mars/mars_charts/offline-image"):
            exec_cmd(worker_connection, "mv mars_charts/offline-image offline-image")
        exec_cmd(worker_connection, "rm -rf mars_charts")
        exec_cmd(worker_connection, "mkdir -p mars_charts")
        exec_cmd(worker_connection, "tar xvf mars_charts.*.tar -C mars_charts")
        exec_cmd(worker_connection, "mv offline-image mars_charts/offline-image")
    exec_cmd(worker_connection, "cp /home/mars/MARS_CONF.xlsx /home/mars/mars_charts")

    # donwload big image
    if not is_file_exists(worker_connection, "/home/mars/mars_charts/offline-image/{}"
            .format(os.path.basename(deploy_config.BIG_IMAGE_URL))):
        exec_cmd(worker_connection, "mkdir /home/mars/mars_charts/offline-image")
        exec_cmd(worker_connection, "cd /home/mars/mars_charts/offline-image; wget {} -O temp.file; mv temp.file {}"
                 .format(deploy_config.BIG_IMAGE_URL, os.path.basename(deploy_config.BIG_IMAGE_URL)))


def install_mars_charts(worker_connection):
    stdout = exec_cmd(worker_connection,
                      "export PYTHON_HOME=$HOME/pyenv/python3.7;export PATH=\"$PYTHON_HOME/usr/bin:$PATH\";"
                      "cd /home/mars/mars_charts;bash ./mars.sh gen_conf")
    if "gen_conf success!!!" not in stdout:
        print("gen_conf failed")
        sys.exit(1)
    stdout = exec_cmd(worker_connection,
                      "export PYTHON_HOME=$HOME/pyenv/python3.7;export PATH=\"$PYTHON_HOME/usr/bin:$PATH\";"
                      "cd /home/mars/mars_charts;bash ./mars.sh check")
    if "check success!!!" not in stdout:
        print("check failed")
        sys.exit(1)
    stdout = exec_cmd(worker_connection,
                      "export PYTHON_HOME=$HOME/pyenv/python3.7;export PATH=\"$PYTHON_HOME/usr/bin:$PATH\";"
                      "cd /home/mars/mars_charts;bash ./mars.sh download")
    if "download success!!!" not in stdout:
        print("check failed")
        sys.exit(1)
    install_start_time = time.time()
    stdout = exec_cmd(worker_connection,
                      "export PYTHON_HOME=$HOME/pyenv/python3.7;export PATH=\"$PYTHON_HOME/usr/bin:$PATH\";"
                      "cd /home/mars/mars_charts;bash ./mars.sh install")
    if "install success!!!" not in stdout:
        print("install failed")
        sys.exit(1)
    # 如果install大于10分钟，那么就是第一次安装，休息会儿再restart下
    if time.time() - install_start_time > 10 * 60:
        print("success install, wait 5min")
        time.sleep(300)
    stdout = exec_cmd(worker_connection,
                      "export PYTHON_HOME=$HOME/pyenv/python3.7;export PATH=\"$PYTHON_HOME/usr/bin:$PATH\";"
                      "cd /home/mars/mars_charts;bash ./mars.sh restart")
    if "restart success!!!" not in stdout:
        print("restart failed")
        sys.exit(1)


def deploy_on_main_server(worker_connection):
    upload_excel(worker_connection)
    download_basedeploy(worker_connection)
    deploy_basedeploy(worker_connection)
    download_mars_charts(worker_connection)
    install_mars_charts(worker_connection)


def init_copy_ssh_id(worker_connection, worker_ips):
    for ip in worker_ips:
        exec_cmd(worker_connection, "sudo yum -y update && sudo yum install -y sshpass")
        exec_cmd(worker_connection, "ssh-keyscan {} >> $HOME/.ssh/known_hosts".format(ip))
        exec_cmd(worker_connection, "sshpass -p marsPWD ssh-copy-id mars@{}".format(ip))


def add_nginx_config(nginx_connection, ip, env_name):
    nginx_file = "server {\n    listen       80;\n    listen  [::]:80;\n    server_name  $<env_name$>.pri-customer.vemarsdev.com $<env_name$>-api.pri-customer.vemarsdev.com;\n    client_max_body_size 2000M;\n\n    #access_log  /var/log/nginx/host.access.log  main;\n\n    location / {\n        proxy_connect_timeout 600s;\n        proxy_read_timeout 600s;\n        proxy_send_timeout 600s;\n        proxy_set_header Host $host;\n        proxy_set_header X-Real-IP $remote_addr;\n        proxy_pass_request_headers      on;\n\t    proxy_pass http://$<ip$>:80;\n    }\n}"\
        .replace("$<env_name$>", env_name).replace("$<ip$>", ip)
    conf_file_path = f"/root/{env_name}.conf"
    exec_cmd(nginx_connection, f"echo '{nginx_file}' > {conf_file_path}")
    exec_cmd(nginx_connection, f"docker cp {conf_file_path} nginx:/etc/nginx/conf.d/")
    stdout = exec_cmd(nginx_connection, "docker exec -it nginx nginx -s reload")
    if "signal process started" not in stdout:
        print("nginx failed")
        sys.exit(1)


def init_jump_copy_ssh_id(jumpbox, ip):
    exec_cmd(jumpbox, "ssh-keyscan {} >> $HOME/.ssh/known_hosts".format(ip))
    exec_cmd(jumpbox, "sshpass -p marsPWD ssh-copy-id mars@{}".format(ip))


def deploy(worker_ips):
    jumpbox, jumpbox_inner_ip = init_jumpserver()
    worker_connections = []
    for worker_ip in worker_ips:
        worker_connections.append(init_worker_root_connection(jumpbox, jumpbox_inner_ip, worker_ip))

    initial_vms(worker_connections)

    mars_worker_connections = []
    for worker_ip in worker_ips:
        mars_worker_connections.append(init_worker_mars_connection(jumpbox, jumpbox_inner_ip, worker_ip))

    init_copy_ssh_id(mars_worker_connections[0], worker_ips)

    init_jump_copy_ssh_id(jumpbox, worker_ips[0])

    deploy_on_main_server(mars_worker_connections[0])

    nginx_connection = init_worker_root_connection(jumpbox, jumpbox_inner_ip, deploy_config.NGINX_IP)
    add_nginx_config(nginx_connection, worker_ips[0], deploy_config.env_name)


if __name__ == '__main__':
    deploy(deploy_config.worker_ips)
