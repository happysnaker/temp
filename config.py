import os


class BaseConfig:
    excel_path = "./zhilian.xlsx"
    # mars_charts版本
    mars_charts_version = "2022.06.23"
    # 火山服务器节点
    worker_ips = ["192.168.1.125", "192.168.1.119", "192.168.1.105"]
    # ！需要与excel中的一致！
    # 控制台：https://${env_name}.pri-customer.vemarsdev.com/
    # 下发端：https://${env_name}-api.pri-customer.vemarsdev.com/
    env_name = "zhilian"
    # 常量
    JUMP_IP = "221.194.149.20"
    JUMP_PORT = 22422
    NGINX_IP = "192.168.0.122"
    SSH_KEY_FILE = os.getenv('HOME') + '/.ssh/id_rsa'
    BIG_IMAGE_URL = "http://sf3-cdn-tos.toutiaostatic.com/obj/mars-pri-release/release/large/mars_build_image.1.0.0-image.tar.gz"
    BASE_DEPLOY_URL = "https://sf3-cdn-tos.toutiaostatic.com/obj/mars-pri-release/minibase/BaseDeploy-mars-release-1.0.10.tar.gz"

    def __init__(self):
        self.MARS_CHARTS_URL = "http://sf3-cdn-tos.toutiaostatic.com/obj/mars-pri-release/charts/mars_charts.{}.tar".format(
            self.mars_charts_version)


class ZhilianConfig(BaseConfig):
    excel_path = "./zhilian.xlsx"
    # mars_charts版本
    mars_charts_version = "2022.06.23"
    # 火山服务器节点
    worker_ips = ["192.168.1.125", "192.168.1.119", "192.168.1.105"]
    # ！需要与excel中的一致！
    # 控制台：https://${env_name}.pri-customer.vemarsdev.com/
    # 下发端：https://${env_name}-api.pri-customer.vemarsdev.com/
    env_name = "zhilian"


class DepponConfig(BaseConfig):
    excel_path = "./deppon.xlsx"
    # mars_charts版本
    mars_charts_version = "2022.06.303"
    # 火山服务器节点
    worker_ips = ["192.168.1.126", "192.168.1.112"]
    # ！需要与excel中的一致！
    # 控制台：https://${env_name}.pri-customer.vemarsdev.com/
    # 下发端：https://${env_name}-api.pri-customer.vemarsdev.com/
    env_name = "happysnaker"


def get_config():
    return DepponConfig()
