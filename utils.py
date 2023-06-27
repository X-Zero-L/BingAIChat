import base64
import os
import json
from hoshino import aiorequests
def remove_file(file_name):
    if os.path.exists(file_name):
        os.remove(file_name)


def dump_to_json(data, file_name):
    with open(file_name, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def load_from_json(file_name):
    if not os.path.exists(file_name):
        return []
    with open(file_name, 'r', encoding='utf-8') as f:
        return json.load(f)
    
async def download_image(url,proxy = None):
    resp = await aiorequests.get(url, proxies={'http': proxy, 'https': proxy} if proxy else None)
    content = await resp.content
    # 将返回的二进制数据转为base64
    return f"[CQ:image,file=base64://{base64.b64encode(content).decode()}]"

async def async_download_images(urls,proxy = None):
    images = []
    for url in urls:
        images.append(await download_image(url,proxy))
    return images