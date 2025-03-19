import os
import time
import yaml
from bilibili_api import Credential,sync,Geetest,login_v2,GeetestType,select_client
from typing import Optional
import questionary
import asyncio

from common.utils import CountryCodeValidator
from common.logger import get_logger

select_client("aiohttp")

class CookieManager:
    def __init__(self,config_dir:str = "config") -> None:
        """
            初始化配置目录并创建cookies存储路径
            
            参数:
                config_dir: 配置文件根目录路径，默认为当前目录下的'config'文件夹
                            该参数用于指定配置文件存储的基础目录
            
            返回值:
                None
        """
        self.logger = get_logger(__name__)
        self.cookies_dir = os.path.join(config_dir, 'cookies')
        if not os.path.exists(self.cookies_dir):
            os.makedirs(self.cookies_dir, exist_ok=True)
            self.logger.info(f"创建cookies目录{self.cookies_dir}")

    def save_cookies(self, credential: Credential, alias: str) -> bool:
        """
        将凭证对象的cookies保存到指定别名的YAML文件

        参数:
            credential (Credential): 需要保存的凭证对象，包含cookies信息
            alias (str): 用于标识cookie文件的别名，将作为文件名组成部分

        返回:
            bool: 保存成功返回True，保存过程中出现任何异常则返回False
        """
        try:
            # 从凭证对象提取cookies并构建文件路径
            cookies = credential.get_cookies()
            file_path = self._get_filepath(alias)
            
            # 序列化cookies并写入YAML文件
            with open(file_path, 'w') as file:
                yaml.dump(cookies, file)
            
            self.logger.info(f"保存cookies成功: {alias}")
            return True
        except Exception as e:
            # 异常处理及日志记录
            self.logger.error(f"保存cookies失败: {str(e)}")
            return False        
    def load_cookies(self, alias: str) -> Optional[Credential]:
        """
        加载指定别名的cookie凭证文件

        参数:
            alias: cookies配置的别名标识，用于生成对应的凭证文件名

        返回值:
            Credential: 包含cookies的凭证对象实例，加载失败时返回None

        """
        try:
            # 尝试加载指定别名的cookie文件
            file_path = self._get_filepath(alias)
            with open(file_path, 'r') as file:
                cookies = yaml.safe_load(file)
            
            # 创建凭证对象并验证有效性
            credential = Credential(cookies=cookies)
            if sync(credential.check_refresh()):
                self.logger.info(f"加载cookies成功: {alias}.yaml")
            else:
                self.logger.warning("cookies已过期,需要重新登陆")
                self.login_user(alias)
            return credential

        except FileNotFoundError:
            # 处理文件不存在异常
            self.logger.error(f"加载cookies失败: 文件不存在 {alias}.yaml")
            return None
    def list_accounts(self) -> list:
        """列出所有已保存的账号"""
        return [f.split('.')[0] for f in os.listdir(self.cookies_dir) 
                if f.endswith('.yaml')]
    def _get_filepath(self, alias: str) -> str:
        """获取账号对应的文件路径"""
        return os.path.join(self.cookies_dir, f"{alias}.yaml")
    async def login_user(self, alias: str) -> Credential:
        """
        交互式登录入口

        参数:
            alias: cookies配置的别名标识，用于生成对应的凭证文件名

        返回值:
            Credential: 包含cookies的凭证对象实例，加载失败时返回None
        """
        gee = Geetest() #实例化极验测试类
        await gee.generate_test(type_=GeetestType.LOGIN) # 生成登陆
        gee.start_geetest_server() # 在本地部署网页端测试服务
        self.logger.info("使用浏览器打开链接完成人机验证：",gee.get_geetest_server_url()) # 获取本地服务链接
        while not gee.has_done():
            await asyncio.sleep(0.5)  
        gee.close_geetest_server() # 关闭部署的网页端测试服务
        self.logger.debug("result:", gee.get_result())

        # 选择登录方式
        login_type = await questionary.select(
            "请选择登录方式：",
            choices=[
                {"name": "终端二维码登录", "value": "termqr"},
                {"name": "账号密码登录", "value": "pwd"},
                {"name": "手机验证码登录", "value": "sms"},
                {"name": "取消", "value": "exit"}
            ]
        ).ask_async()

        if login_type == "exit":
            raise KeyboardInterrupt("用户取消登录")

        credential = None

        if login_type == "termqr":
            #终端二维码登录
            qr = login_v2.QrCodeLogin(platform=login_v2.QrCodeLoginChannel.WEB) # 生成二维码登录实例，平台选择网页端
            await qr.generate_qrcode() # 生成二维码
            print(qr.get_qrcode_terminal()) # 生成终端二维码文本，打印
            while not qr.has_done():     
                self.logger.info(await qr.check_state()) # 检查状态
                asyncio.sleep(1) 
            credential = qr.get_credential()
            
        elif login_type == "pwd":
            # 账号密码登陆
            username = await questionary.text(
                message="请输入密码",
                validate=lambda a: (True if len(a) > 0 else "密码不能为空")
            ).ask_async()
            password = await questionary.password(
                message="请输入密码",
                validate=lambda a: (True if len(a) > 0 else "密码不能为空")
            ).ask_async()
            credential =await login_v2.login_with_password(username=username, password=password, geetest=gee)               # 调用接口登陆
            
        elif login_type == "sms":
            # 手机号验证码登录
            countrycode = await questionary.text(
                message="请输入国家代码",
                validate=CountryCodeValidator
            ).ask_async()
            phonenumber = await questionary.text(
                message="请输入手机号",
                validate=lambda a: (True if len(a) > 0 else "手机号不能为空")
            ).ask_async()
            
            phone = login_v2.PhoneNumber(phonenumber, countrycode)
            captcha_id = await login_v2.send_sms(phonenumber=phone, geetest=gee)# 发送验证码
            print("captcha_id:", captcha_id)     

            sms_code = await questionary.text(
                message="请输入短信验证码：",
                validate=lambda val: len(val)==6 and val.isdigit() or "请输入6位数字验证码"
            ).ask_async()

            credential = await login_v2.login_with_sms(
                phonenumber=phone, code=sms_code, captcha_id=captcha_id             # 调用接口登陆
            )

        # 安全验证
        if isinstance(credential, login_v2.LoginCheck):
            gee = Geetest()# 实例化极验测试类
            await gee.generate_test(type_=GeetestType.VERIFY) # 生成测试

            gee.start_geetest_server() # 在本地部署网页端测试服务
            self.logger.info("使用浏览器打开链接完成人机验证：",gee.get_geetest_server_url()) # 获取本地服务链接
            while not gee.has_done():  
                asyncio.sleep(0.5)                                                    
            gee.close_geetest_server() # 关闭部署的网页端测试服务
            self.logger.info("result:", gee.get_result())
            await credential.send_sms(gee) # 发送验证码
            
            sms_code = questionary.text(
                message="请输入短信验证码：",
                validate=lambda val: len(val)==6 and val.isdigit() or "请输入6位数字验证码"
            ).ask_async()
            credential = await credential.complete_check(sms_code)  

        if credential and self.save_cookies(credential, alias=alias):
            self.logger.info(f"登录成功: {alias}")
            return credential
        raise RuntimeError("登录失败")