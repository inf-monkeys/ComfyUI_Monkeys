import asyncio
import os.path
import shutil
import traceback

import requests
import server
import sys
import folder_paths
import json
from comfy.cli_args import args
import websocket
import uuid
import urllib.parse
import urllib.request
import threading
import logging
import boto3
from botocore.client import Config
from .storage import LocalFileStorage

# paths
comfyui_monkeys_path = os.path.dirname(__file__)
comfy_path = os.path.dirname(folder_paths.__file__)
custom_nodes_path = os.path.join(comfy_path, 'custom_nodes')
js_path = os.path.join(comfy_path, "web", "extensions")

config_folder = os.path.join(comfyui_monkeys_path, 'config')
if not os.path.exists(config_folder):
    os.mkdir(config_folder)

s3_config_file = os.path.join(config_folder, 's3.json')

logging.basicConfig(format='[%(name)s] %(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
# 创建日志记录器
logger = logging.getLogger("ComfyUI_Monkey")

try:
    import aiohttp
    from aiohttp import web
except ImportError:
    print("Module 'aiohttp' not installed. Please install it via:")
    print("pip install aiohttp")
    print("or")
    print("pip install -r requirements.txt")
    sys.exit()

JSON_HEADERS = {'Content-type': 'application/json; charset=utf-8'}

client_id = str(uuid.uuid4())
ws = websocket.WebSocket()
ws_url = "ws://127.0.0.1:{}/ws?clientId={}".format(args.port, client_id)


def get_task(prompt_id):
    api = f"http://127.0.0.1:{args.port}/history/{prompt_id}"
    res = requests.get(api)
    return res.json()


def get_asset_url(base_url, filename, subfolder, folder_type):
    s3_enabled = False
    if os.path.exists(s3_config_file):
        try:
            with open(s3_config_file, 'r', encoding="utf-8") as f:
                s3_config = json.load(f)
                s3_enabled = s3_config.get('enabled')
        except Exception as e:
            logger.warning("Load s3 config failed: ", str(e))

    if s3_enabled:
        endpoint_url = s3_config.get('endpoint_url')
        aws_access_key_id = s3_config.get('aws_access_key_id')
        aws_secret_access_key = s3_config.get('aws_secret_access_key')
        region_name = s3_config.get('region_name')
        addressing_style = s3_config.get('addressing_style', 'auto')
        bucket = s3_config.get('bucket')
        public_access_url = s3_config.get('public_access_url')
        key = f'artworks/{uuid.uuid1().hex}.{filename.split(".")[-1]}'
        s3 = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=region_name,
            config=Config(s3={'addressing_style': addressing_style})
        )
        local_path = os.path.join(comfy_path, 'output', subfolder, filename)
        logger.info(f"Start to upload {local_path} to s3")
        with open(local_path, 'rb') as file:
            file_bytes = file.read()
            s3.put_object(Bucket=bucket, Key=key, Body=file_bytes)
            return f'{public_access_url}/{key}'
    else:
        data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
        url_values = urllib.parse.urlencode(data)
        return "{}/view?{}".format(base_url, url_values)


def queue_prompt(task_id, base_url, workflow_json, requirements=None):
    api = f"http://127.0.0.1:{args.port}/prompt"

    if requirements:
        for item in requirements:
            file_path = os.path.join(comfy_path, item.get('path'), item.get('filename'))
            if not os.path.exists(file_path):
                url = item.get('url')
                logging.info(f'Downloading {url} to {file_path}')
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                command = f'wget -q -O {file_path} "{url}"'
                logger.info(f"Run command {command}")
                os.system(command)

    res = requests.post(api, data=json.dumps(workflow_json).encode(), headers=JSON_HEADERS, timeout=5)
    result = res.json()
    prompt_id = result['prompt_id']
    LocalFileStorage.update_task_status(task_id, status="IN_PROGRESS", prompt_id=prompt_id)
    track_progress(task_id, base_url, workflow_json['prompt'], prompt_id)


def get_assets_in_result(base_url, prompt_id):
    output_images = []
    output_videos = []
    result = get_task(prompt_id)
    history = result[prompt_id]
    for node_id in history['outputs']:
        node_output = history['outputs'][node_id]
        if 'images' in node_output:
            for image in node_output['images']:
                image_url = get_asset_url(base_url, image['filename'], image['subfolder'], image['type'])
                output_images.append(image_url)
        elif 'gifs' in node_output:
            for video in node_output['gifs']:
                video_url = get_asset_url(base_url, video['filename'], video['subfolder'], video['type'])
                output_videos.append(video_url)
    return {
        "images": output_images,
        "videos": output_videos
    }


def track_progress(task_id, base_url, prompt, prompt_id):
    node_ids = list(prompt.keys())
    finished_nodes = []
    ws.connect(ws_url)
    cached = False
    while True:
        out = ws.recv()
        if isinstance(out, str):
            print(f"receive message: {out[0:200]}")
            message = json.loads(out)
            if message['type'] == 'progress':
                data = message['data']
                current_step = data['value']
                print('In K-Sampler -> Step: ', current_step, ' of: ', data['max'])
            if message['type'] == 'execution_cached':
                data = message['data']
                for itm in data['nodes']:
                    if itm not in finished_nodes:
                        finished_nodes.append(itm)
                        print('Progess: ', len(finished_nodes), '/', len(node_ids), ' Tasks done')
            if message['type'] == 'executing':
                data = message['data']
                if data['node'] not in finished_nodes:
                    finished_nodes.append(data['node'])
                    print('Progess: ', len(finished_nodes), '/', len(node_ids), ' Tasks done')
                if data['node'] is None and data['prompt_id'] == prompt_id:
                    break  # Execution is done
            if message['type'] == 'status':
                queue_remaining = message.get('data', {}).get('status', {}).get('exec_info', {}).get('queue_remaining')
                if queue_remaining == 0:
                    cached = True
                    break
        else:
            continue

    status = "COMPLETED" if len(finished_nodes) >= len(node_ids) or cached else "FAILED"
    kwargs = {}
    if status == 'COMPLETED':
        try:
            kwargs['data'] = get_assets_in_result(base_url, prompt_id)
        except Exception as e:
            traceback.print_exc()
            kwargs['status'] = 'FAILED'
            kwargs['errMsg'] = str(e)
    LocalFileStorage.update_task_status(task_id=task_id, status=status, **kwargs)


@server.PromptServer.instance.routes.get("/monkeys/healthz")
async def health_check(request):
    return web.json_response({
        "success": True
    })


@server.PromptServer.instance.routes.get("/monkeys/all-models")
async def get_all_models(request):
    sub_folders = [
        'checkpoints',
        'clip',
        'clip_vision',
        'controlnet',
        'diffusers',
        'embeddings',
        'gligen',
        'hypernetworks',
        'ipadapter',
        'loras',
        'style_models',
        'unet',
        'upscale_models',
        'vae',
        'vae_approx',
        'instanceid'
    ]
    data = {}
    for sub_folder in sub_folders:
        try:
            filenames = folder_paths.get_filename_list(sub_folder)
            data[sub_folder] = filenames
        except Exception as e:
            data[sub_folder] = []
    return web.json_response(data)


@server.PromptServer.instance.routes.get("/monkeys/tasks/{task_id}")
async def get_prompt_execution_status(request):
    task_id = request.match_info.get('task_id')
    data = LocalFileStorage.get_task(task_id)
    if 'status' not in data:
        data['status'] = 'PENDING'
    return web.json_response(data)


@server.PromptServer.instance.routes.get("/monkeys/logs/<string:prompt_id>")
async def get_prompt_logs(request, prompt_id):
    pass


def get_base_url(request):
    host = request.host
    scheme = request.scheme
    return f"{scheme}://{host}"


@server.PromptServer.instance.routes.post("/monkeys/text-to-image")
async def text_to_image(request):
    json_data = await request.json()

    template_filename = os.path.join(os.path.dirname(__file__), "templates", "text_to_image.json")
    with open(template_filename, "r", encoding='utf-8') as f:
        workflow_template_str = f.read()

    task_id = uuid.uuid4()
    model_name = json_data.get('modelName')
    prompt = json_data.get('prompt')
    negative_prompt = json_data.get('negativePrompt')
    sampling_step = json_data.get('samplingStep')
    cfg_scale = json_data.get('cfgScale')
    width = json_data.get('width')
    height = json_data.get('height')
    batch_count = json_data.get('batchCount')
    requirements = json_data.get('requirements', [])
    workflow_str = workflow_template_str.replace("<ModelName>", model_name).replace("<Prompt>", prompt).replace(
        "<NegativePrompt>", negative_prompt).replace("\"<SamplingStep>\"", str(sampling_step)).replace("\"<CfgScale>\"",
                                                                                                       str(cfg_scale)).replace(
        "\"<Width>\"", str(width)).replace("\"<Height>\"", str(height)).replace("\"<BatchCount>\"",
                                                                                str(batch_count)).replace(
        "<FilenamePrefix>",
        "ComfyUI")
    workflow_json = json.loads(workflow_str)
    workflow_json['client_id'] = client_id
    logger.info("Receive new text to image task.")
    base_url = get_base_url(request)

    LocalFileStorage.start_task(task_id, workflow_json)
    t = threading.Thread(target=queue_prompt, args=(task_id, base_url, workflow_json, requirements))
    t.start()

    return web.json_response({
        "__monkeyLogUrl": f"/monkeys/logs/{task_id}",
        "__monkeyResultUrl": f"/monkeys/tasks/{task_id}",
    })


@server.PromptServer.instance.routes.post("/monkeys/image-to-image")
async def image_to_image(request):
    json_data = await request.json()

    template_filename = os.path.join(os.path.dirname(__file__), "templates", "text_to_image.json")
    with open(template_filename, "r", encoding='utf-8') as f:
        workflow_template_str = f.read()

    task_id = uuid.uuid4()
    model_name = json_data.get('modelName')
    prompt = json_data.get('prompt')
    negative_prompt = json_data.get('negativePrompt')
    sampling_step = json_data.get('samplingStep')
    cfg_scale = json_data.get('cfgScale')
    image_path = json_data.get('imagePath')
    requirements = json_data.get('requirements', [])
    workflow_str = (workflow_template_str
                    .replace("<ModelName>", model_name)
                    .replace("<Prompt>", prompt)
                    .replace("<NegativePrompt>", negative_prompt)
                    .replace("\"<SamplingStep>\"", str(sampling_step))
                    .replace("\"<CfgScale>\"", str(cfg_scale))
                    .replace("<imagePath>", image_path))
    workflow_json = json.loads(workflow_str)
    workflow_json['client_id'] = client_id
    logger.info("Receive new image to image task.")
    base_url = get_base_url(request)

    LocalFileStorage.start_task(task_id, workflow_json)
    t = threading.Thread(target=queue_prompt, args=(task_id, base_url, workflow_json, requirements))
    t.start()

    return web.json_response({
        "__monkeyLogsUrl": f"/monkeys/logs/{task_id}",
        "__monkeyResultUrl": f"/monkeys/tasks/{task_id}",
    })


@server.PromptServer.instance.routes.post("/monkeys/run-prompt")
async def run_prompt_api(request):
    json_data = await request.json()
    task_id = uuid.uuid4()
    workflow_json = json_data.get('prompt')
    requirements = json_data.get('requirements', [])
    workflow_json['client_id'] = client_id
    logger.info("Receive new image to image task.")
    base_url = get_base_url(request)

    t = threading.Thread(target=queue_prompt, args=(task_id, base_url, workflow_json, requirements))
    t.start()

    return web.json_response({
        "__monkeyLogsUrl": f"/monkeys/logs/{task_id}",
        "__monkeyResultUrl": f"/monkeys/tasks/{task_id}",
    })


async def test_s3_connection(json_data):
    endpoint_url = json_data.get('endpoint_url')
    aws_access_key_id = json_data.get('aws_access_key_id')
    aws_secret_access_key = json_data.get('aws_secret_access_key')
    region_name = json_data.get('region_name')
    addressing_style = json_data.get('addressing_style', 'auto')
    bucket = json_data.get('bucket')
    s3 = boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        region_name=region_name,
        config=Config(s3={'addressing_style': addressing_style})
    )
    s3.head_bucket(Bucket=bucket)


@server.PromptServer.instance.routes.post("/monkeys/test-s3")
async def test_s3(request):
    json_data = await request.json()
    try:
        await asyncio.wait_for(test_s3_connection(json_data), timeout=3)
        return web.json_response({
            "success": True
        })
    except Exception as e:
        return web.json_response({
            "success": False,
            "errMsg": str(e)
        })


@server.PromptServer.instance.routes.post("/monkeys/save-s3-config")
async def save_s3_config(request):
    json_data = await request.json()
    enabled = json_data.get('enabled')
    endpoint_url = json_data.get('endpoint_url')
    aws_access_key_id = json_data.get('aws_access_key_id')
    aws_secret_access_key = json_data.get('aws_secret_access_key')
    region_name = json_data.get('region_name')
    addressing_style = json_data.get('addressing_style', 'auto')
    public_access_url = json_data.get('public_access_url')
    bucket = json_data.get('bucket')
    with open(s3_config_file, 'w') as f:
        f.write(json.dumps({
            "enabled": enabled,
            "endpoint_url": endpoint_url,
            "aws_access_key_id": aws_access_key_id,
            "aws_secret_access_key": aws_secret_access_key,
            "region_name": region_name,
            "addressing_style": addressing_style,
            "bucket": bucket,
            "public_access_url": public_access_url
        }))
    return web.json_response({
        "success": True
    })


@server.PromptServer.instance.routes.get("/monkeys/get-s3-config")
async def get_s3_config(request):
    if os.path.exists(s3_config_file):
        try:
            with open(s3_config_file, 'r', encoding="utf-8") as f:
                return web.json_response({
                    "success": True,
                    "data": json.load(f)
                })
        except Exception as e:
            return web.json_response({
                "success": False,
                "errMsg": str(e)
            })
    else:
        return web.json_response({
            "success": False
        })


def setup_js():
    import nodes
    js_dest_path = os.path.join(js_path, "comfyui-monkeys")

    if hasattr(nodes, "EXTENSION_WEB_DIRS"):
        if os.path.exists(js_dest_path):
            shutil.rmtree(js_dest_path)
    else:
        logger.warning(f"Your ComfyUI version is outdated. Please update to the latest version.")
        # setup js
        if not os.path.exists(js_dest_path):
            os.makedirs(js_dest_path)
        js_src_path = os.path.join(comfyui_monkeys_path, "js", "comfyui-monkeys.js")

        print(f"### ComfyUI_Monkeys: Copy .js from '{js_src_path}' to '{js_dest_path}'")
        shutil.copy(js_src_path, js_dest_path)


WEB_DIRECTORY = "js"
setup_js()

NODE_CLASS_MAPPINGS = {}
