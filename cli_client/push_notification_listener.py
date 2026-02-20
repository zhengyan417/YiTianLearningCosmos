import asyncio
import threading

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response

class PushNotificationListener: # 推送通知监听器
    def __init__( # 初始化
        self,
        host, # 地址
        port, # 端口
    ):
        self.host = host # 地址
        self.port = port # 端口
        self.loop = asyncio.new_event_loop()   # 创建一个新的事件循环
        self.thread = threading.Thread(
            target=lambda loop: loop.run_forever(), args=(self.loop,)
        )   # 创建一个新的线程
        self.thread.daemon = True # 设置守护线程
        self.thread.start()  # 启动线程

    # 运行远程服务器
    def start(self):
        try:
            asyncio.run_coroutine_threadsafe( # 运行携程
                self.start_server(),
                self.loop,
            )
            print('======= push notification listener started =======') # 打印启动信息
        except Exception as e: # 捕获异常
            print(e) # 打印错误信息


    async def start_server(self): # 启动服务器
        import uvicorn

        self.app = Starlette() # 创建一个Web应用
        self.app.add_route(
            '/notify', self.handle_notification, methods=['POST']
        ) # 添加路由
        self.app.add_route(
            '/notify', self.handle_validation_check, methods=['GET']
        ) # 添加路由

        config = uvicorn.Config(
            self.app, host=self.host, port=self.port, log_level='critical'
        ) # 创建配置信息
        self.server = uvicorn.Server(config) # 创建服务器
        await self.server.serve() # 启动服务器

    async def handle_validation_check(self, request: Request): # 处理验证
        validation_token = request.query_params.get('validationToken') # 获取验证秘钥
        print(
            f'\npush notification verification received => \n{validation_token}\n'
        ) # 打印验证秘钥

        if not validation_token: # 如果没有验证秘钥
            return Response(status_code=400) # 返回错误状态码

        return Response(content=validation_token, status_code=200) # 返回成功状态码

    async def handle_notification(self, request: Request): # 处理推送通知
        data = await request.json() # 获取数据

        print(f'\npush notification received => \n{data}\n') # 打印接收到的数据
        return Response(status_code=200) # 返回接收成功状态码
