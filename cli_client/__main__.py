import warnings
warnings.filterwarnings("ignore") # 忽略所有警告

import asyncio
import base64
import os
import urllib

from uuid import uuid4

import asyncclick as click
import httpx

from a2a.client import A2ACardResolver, A2AClient
from a2a.extensions.common import HTTP_EXTENSION_HEADER
from a2a.types import (
    FilePart,
    FileWithBytes,
    GetTaskRequest,
    JSONRPCErrorResponse,
    Message,
    MessageSendConfiguration,
    MessageSendParams,
    Part,
    SendMessageRequest,
    SendStreamingMessageRequest,
    Task,
    TaskArtifactUpdateEvent,
    TaskQueryParams,
    TaskState,
    TaskStatusUpdateEvent,
    TextPart, Role,
)


@click.command() # 命令行参数设置
@click.option('--agent', default='http://127.0.0.1:10001') # 智能体URL
@click.option(
'--bearer-token',
    help='Bearer token for authentication.',
    envvar='A2A_CLI_BEARER_TOKEN',
) # 验证秘钥
@click.option('--session', default=0) # 会话ID
@click.option('--history', default=False) # 是否使用历史记录
@click.option('--use_push_notifications', default=False) # 推送通知
@click.option('--push_notification_receiver', default='http://localhost:5000') # 推送接收地址
@click.option('--header', multiple=True) # 头部参数
@click.option(
    '--enabled_extensions',
    default='',
    help='Comma-separated list of extension URIs to enable (sets X-A2A-Extensions header).',
) # 扩展功能
async def cli( # 命令行函数
    agent, # 智能体URL
    bearer_token, # 验证秘钥
    session, # 会话ID
    history, # 是否使用历史记录
    use_push_notifications: bool, # 推送通知
    push_notification_receiver: str, # 推送接收地址
    header, # 头部参数
    enabled_extensions, # 扩展功能
):

    # 构建HTTP头部请求字典
    headers = {h.split('=')[0]: h.split('=')[1] for h in header} # 获取所有头部参数
    if bearer_token: # 如果有验证秘钥
        headers['Authorization'] = f'Bearer {bearer_token}' # 设置验证秘钥

    # 处理并且设置A2A扩展功能头部
    if enabled_extensions: # 如果有扩展功能
        ext_list = [
            ext.strip() for ext in enabled_extensions.split(',') if ext.strip()
        ] # 获取所有扩展功能
        if ext_list: # 如果有扩展功能
            headers[HTTP_EXTENSION_HEADER] = ', '.join(ext_list) # 设置扩展功能头部
    print(f'Will use headers: {headers}') # 打印头部参数

    # 构建http客户端
    async with httpx.AsyncClient(timeout=300, headers=headers) as httpx_client:
        # 1. 获取Agent card
        card_resolver = A2ACardResolver(httpx_client, agent) # 创建智能体卡片解析器
        card = await card_resolver.get_agent_card() # 获取智能体卡片

        print('======= Agent Card ========') 
        print(card.model_dump_json(exclude_none=True)) # 打印智能体卡片

        notif_receiver_parsed = urllib.parse.urlparse(
            push_notification_receiver
        ) # 解析推送通知接收地址
        notification_receiver_host = notif_receiver_parsed.hostname # 推送通知地址
        notification_receiver_port = notif_receiver_parsed.port # 推送通知端口

        # 推送通知系统
        if use_push_notifications: # 如果使用推送通知
            from push_notification_listener import (
                PushNotificationListener,
            ) # 导入推送通知监听对象

            push_notification_listener = PushNotificationListener(
                host=notification_receiver_host, # 地址
                port=notification_receiver_port, # 端口
            ) # 创建推送通知监听对象
            push_notification_listener.start() # 启动推送通知监听

        # 配置A2A客户端
        client = A2AClient(httpx_client, agent_card=card) # 创建A2A客户端

        continue_loop = True # 是否继续循环
        streaming = card.capabilities.streaming # 是否支持流失输出
        # 上下文保持
        context_id = str(session) if session > 0 else uuid4().hex # 上下文ID

        # 核心交互循环
        while continue_loop: # 不断循环
            print('=========  starting a new task ======== ') # 开始一个新任务
            continue_loop, _, task_id = await completeTask( # 执行一个任务
                client, # 客户端
                streaming, # 是否支持流式输出
                use_push_notifications, # 是否使用推送通知
                notification_receiver_host, # 推送接收地址
                notification_receiver_port, # 推送接收端口
                None, # 任务ID
                context_id, # 上下文ID
            )

            if history and continue_loop: # 如果使用历史记录
                print('========= history ======== ') # 打印历史信息
                task_response = await client.get_task( # 获取任务结果
                    GetTaskRequest(  # 使用正确的请求对象
                        id=str(uuid4()),  # 需要唯一的请求ID
                        params=TaskQueryParams(id=task_id, history_length=10) # 请求参数
                    )
                )
                print(
                    task_response.model_dump_json(
                        include={'result': {'history': True}}
                    )
                ) #打印结果

async def completeTask( # 任务处理函数
    client: A2AClient, # A2A客户端
    streaming, # 是否支持流式输出
    use_push_notifications: bool, # 是否使用推送通知
    notification_receiver_host: str, # 推送接收地址
    notification_receiver_port: int, # 推送接收端口
    task_id, # 任务ID
    context_id, # 上下文ID
):
    # 用户输入收集
    prompt = await click.prompt(
        '\nWhat do you want to send to the agent? (:q or quit to exit)'
    ) # 获取用户输入
    if prompt == ':q' or prompt == 'quit': # 如果输入退出
        return False, None, None # 任务结束

    # 消息构建
    message = Message( # 创建消息对象
        role=Role.user, # 角色
        parts=[TextPart(text=prompt)], # 内容
        message_id=str(uuid4()), # 消息ID
        task_id=task_id, # 任务ID
        context_id=context_id, # 上下文ID
    )

    # 传输文件的功能
    file_path = await click.prompt(
        'Select a file path to attach? (press enter to skip)',
        default='',
        show_default=False,
    ) # 获取文件路径
    file_path = str(file_path) # 文件路径转换为字符串
    if file_path and file_path.strip() != '': # 如果文件路径存在
        with open(file_path, 'rb') as f: # 打开文件
            file_content = base64.b64encode(f.read()).decode('utf-8') # 解码文件内容
            file_name = os.path.basename(file_path) # 获取文件名

        message.parts.append( # 将文件内容加入消息里面
            Part( # 构建文件内容
                root=FilePart( # 创建文件内容
                    file=FileWithBytes(name=file_name, bytes=file_content) # 文件内容
                )
            )
        )

    payload = MessageSendParams( # 创建消息配送负载
        message=message, # 消息
        configuration=MessageSendConfiguration(
            accepted_output_modes=['text'],
        ), # 配置
    )

    # 配置推送系统
    if use_push_notifications: # 如果使用推送通知
        payload['pushNotification'] = {
            # 推送地址端口
            'url': f'http://{notification_receiver_host}:{notification_receiver_port}/notify',
            'authentication': {
                'schemes': ['bearer'],
            }, # 认证
        } # 将推送地址加入负载

    taskResult = None # 初始化任务结果
    message = None # 初始化消息
    task_completed = False # 初始化任务完成状态

    # 流式通信
    if streaming: # 如果支持流式输出
        response_stream = client.send_message_streaming( # 流式发送消息
            SendStreamingMessageRequest( # 请求对象
                id=str(uuid4()), # 请求id
                params=payload, # 参数
            )
        )
        async for result in response_stream: # 流式获取结果
            if isinstance(result.root, JSONRPCErrorResponse): # 如果是错误结果
                print( 
                    f'错误: {result.root.error}, 上下文ID: {context_id}, 任务ID: {task_id}'
                ) # 输出错误信息
                return False, context_id, task_id # 任务结束
            event = result.root.result # 获取事件
            context_id = event.context_id # 获取上下文ID
            if isinstance(event, Task):  # 如果是任务
                task_id = event.id # 获取任务ID
            elif isinstance(event, TaskStatusUpdateEvent) or isinstance(
                event, TaskArtifactUpdateEvent
            ): # 如果是任务状态更新事件或者任务结果更新事件
                task_id = event.task_id # 获取任务ID
                if (
                    isinstance(event, TaskStatusUpdateEvent)
                    and event.status.state == 'completed'
                ): # 如果是任务状态更新为完成
                    task_completed = True # 任务完成
            elif isinstance(event, Message): # 如果是消息
                message = event # 获取消息
            print(f'stream event => {event.model_dump_json(exclude_none=True)}') # 打印事件
 
        if task_id and not task_completed: # 如果任务ID存在并且没有完成
            taskResultResponse = await client.get_task( # 获取任务结果
                GetTaskRequest( # 请求对象
                    id=str(uuid4()), # 请求ID
                    params=TaskQueryParams(id=task_id), # 请求参数
                )
            )
            if isinstance(taskResultResponse.root, JSONRPCErrorResponse): # 如果出现错误
                print(
                    f'Error: {taskResultResponse.root.error}, context_id: {context_id}, task_id: {task_id}'
                ) # 打印错误
                return False, context_id, task_id # 人物完成
            taskResult = taskResultResponse.root.result # 获取任务结果
    # 非流式通信
    else:
        event = None # 事件初始化
        try:
            event = await client.send_message( # 发送消息
                SendMessageRequest( # 请求对象
                    id=str(uuid4()), # 请求ID
                    params=payload, # 参数
                )
            )
            event = event.root.result # 获取事件结果
        except Exception as e: # 异常捕获
            print('在发送消息的时候出现错误', e) # 打印错误
        if not context_id: # 如果上下文ID不存在
            context_id = event.context_id # 获取上下文ID
        if isinstance(event, Task): # 如果是任务
            if not task_id: # 如果任务ID不存在
                task_id = event.id # 更新任务ID
            taskResult = event # 获取任务结果
        elif isinstance(event, Message): # 如果消息
            message = event # 获取消息

    if message: # 如果消息存在
        print(f'\n{message.model_dump_json(exclude_none=True)}') # 打印消息
        return True, context_id, task_id # 任务完成
    if taskResult: # 如果任务结果存在
        
        task_content = taskResult.model_dump_json( # 获取任务结果内容(不要文件)
            exclude={
                'history': {
                    '__all__': {
                        'parts': {
                            '__all__': {'file'},
                        },
                    },
                },
            },
            exclude_none=True,
        )
        print(f'\n{task_content}') # 打印任务结果

        state = TaskState(taskResult.status.state) # 获取任务状态
        if state.name == TaskState.input_required.name: # 如果任务状态要求输出
            return ( 
                await completeTask( # 递归调用
                    client, # 客户端
                    streaming, # 是否支持流失输出
                    use_push_notifications, # 是否使用推送通知
                    notification_receiver_host, # 推送接收地址
                    notification_receiver_port, # 推送接收端口
                    task_id, # 任务ID
                    context_id, # 上下文ID
                ),
                context_id, # 上下文ID
                task_id, # 任务ID
            )

        return True, context_id, task_id # 任务成功完成
    return True, context_id, task_id # 任务完成

if __name__ == '__main__':
    asyncio.run(cli()) # 运行命令行