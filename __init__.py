import asyncio
import os.path

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

PROMPTID_TO_PROMPT_MAP = {}
PROMPTID_TO_STATUS_MAP = {}


async def get_task(prompt_id):
    api = f"http://127.0.0.1:{args.port}/history/{prompt_id}"
    async with aiohttp.ClientSession() as session:
        async with session.get(api) as response:
            result = await response.json()
            return result


def get_image_url(base_url, filename, subfolder, folder_type):
    data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
    url_values = urllib.parse.urlencode(data)
    return "{}/view?{}".format(base_url, url_values)


async def queue_prompt(workflow_json):
    api = f"http://127.0.0.1:{args.port}/prompt"
    async with aiohttp.ClientSession() as session:
        async with session.post(api, json=workflow_json) as response:
            result = await response.json()
            print(result)
            return result['prompt_id']


async def get_assets_in_result(base_url, prompt_id):
    output_images = []
    output_videos = []
    result = await get_task(prompt_id)
    history = result[prompt_id]
    for node_id in history['outputs']:
        node_output = history['outputs'][node_id]
        if 'images' in node_output:
            for image in node_output['images']:
                image_url = get_image_url(base_url, image['filename'], image['subfolder'], image['type'])
                output_images.append(image_url)
        elif 'gifs' in node_output:
            for video in node_output['gifs']:
                video_url = get_image_url(base_url, video['filename'], video['subfolder'], video['type'])
                output_videos.append(video_url)
    return {
        "images": output_images,
        "videos": output_videos
    }


def track_progress(prompt, prompt_id):
    node_ids = list(prompt.keys())
    finished_nodes = []
    ws.connect(ws_url)
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
            # if message['type'] == 'status':
            #     queue_remaining = message.get('data', {}).get('status', {}).get('exec_info', {}).get('queue_remaining')
            #     if queue_remaining == 0:
            #         break
        else:
            continue

    PROMPTID_TO_STATUS_MAP[prompt_id] = 'FINISHED'


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
        filenames = folder_paths.get_filename_list(sub_folder)
        data[sub_folder] = filenames
    return web.json_response(data)


@server.PromptServer.instance.routes.get("/monkeys/history/{prompt_id}")
async def get_prompt_execution_status(request):
    prompt_id = request.match_info.get('prompt_id')
    status = PROMPTID_TO_STATUS_MAP.get(prompt_id)
    if status == 'FINISHED':
        result = await get_assets_in_result("http://localhost:8188", prompt_id)
        return web.json_response({"status": "FINISHED", "data": result})
    else:
        return web.json_response({"status": "IN_PROGRESS"})


@server.PromptServer.instance.routes.get("/monkeys/logs/<string:prompt_id>")
async def get_prompt_logs(request, prompt_id):
    pass


@server.PromptServer.instance.routes.post("/monkeys/text-to-image")
async def text_to_image(request):
    json_data = await request.json()

    template_filename = os.path.join(os.path.dirname(__file__), "templates", "text_to_image.json")
    with open(template_filename, "r", encoding='utf-8') as f:
        workflow_template_str = f.read()

    model_name = json_data.get('modelName')
    prompt = json_data.get('prompt')
    negative_prompt = json_data.get('negativePrompt')
    sampling_step = json_data.get('samplingStep')
    cfg_scale = json_data.get('cfgScale')
    width = json_data.get('width')
    height = json_data.get('height')
    batch_count = json_data.get('batchCount')
    await asyncio.sleep(3)
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
    prompt_id = await queue_prompt(workflow_json)
    logger.info(f"Start prompt, prompt_id={prompt_id}")

    PROMPTID_TO_PROMPT_MAP[prompt_id] = workflow_json['prompt']

    t = threading.Thread(target=track_progress, args=(workflow_json['prompt'], prompt_id))
    t.start()

    return web.json_response({
        "__monkeyLogUrl": f"/monkeys/history/{prompt_id}",
        "__monkeyResultUrl": f"/monkeys/logs/{prompt_id}",
    })


@server.PromptServer.instance.routes.post("/monkeys/image-to-image")
async def image_to_image(request):
    json_data = await request.json()

    template_filename = os.path.join(os.path.dirname(__file__), "templates", "image_to_image.json")
    with open(template_filename, "r", encoding='utf-8') as f:
        workflow_template_str = f.read()

    workflow_json = json.loads(workflow_template_str)
    workflow_json['client_id'] = client_id
    logger.info("Receive new image to image task.")
    prompt_id = await queue_prompt(workflow_json)
    logger.info(f"Start prompt, prompt_id={prompt_id}")

    PROMPTID_TO_PROMPT_MAP[prompt_id] = workflow_json['prompt']

    t = threading.Thread(target=track_progress, args=(workflow_json['prompt'], prompt_id))
    t.start()

    return web.json_response({
        "__monkeyLogsUrl": f"/monkeys/logs/{prompt_id}",
        "__monkeyResultUrl": f"/monkeys/history/{prompt_id}",
    })
