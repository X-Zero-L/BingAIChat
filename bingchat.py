import asyncio
import base64
import os
import json
import contextlib
import time
from .EdgeGPT.EdgeGPT import Chatbot, ConversationStyle
from .bingImage import bing_img_create
from hoshino import Service, priv, get_bot, aiorequests
from hoshino.typing import CQEvent
from .utils import *
from . import config

path = os.path.dirname(os.path.abspath(__file__))
bots = {}
sv_help = '''
[bing xxx <img>] 与bing聊天,可以附带图片让bing识别,仅第一张图片有效
[bing create xxx] 生成图片
[bing exit] 退出对话(刷新聊天历史记录)
[bing help] 查看帮助
[bing history] 查看历史记录
'''.strip()

sv = Service(
    name='bingchat',
    use_priv=priv.NORMAL,
    manage_priv=priv.SUPERUSER,
    visible=True,
    enable_on_default=True,
    bundle='娱乐',
    help_=sv_help
)   

bot = get_bot()
@bot.on_startup
async def init():
    config.cookies = load_from_json(os.path.join(path, "cookies.json"))
    if not os.path.exists(os.path.join(path, "history")):
        os.mkdir(os.path.join(path, "history"))
    with contextlib.suppress(Exception):
        configJson = load_from_json(os.path.join(path, "config.json"))
        config.proxy = configJson['proxy'] or None # type: ignore


async def get_bing_response(prompt, bing:Chatbot, img_url: str=None): # type: ignore
    resp =  await bing.ask(
        prompt=prompt, conversation_style=ConversationStyle.creative,
        img_url=img_url
    )
    dump_to_json(resp, os.path.join(path, "resp.json"))
    return resp
    
def get_bing_suggestions(msgs):
    try:
        return [suggest['text'] for suggest in msgs['suggestedResponses']] if msgs['suggestedResponses'] else []
    except Exception:
        return []

async def get_bing_urls(msgs):
    try:
        urls = []
        for i, sourceAttribution in enumerate(msgs['sourceAttributions']):
            with contextlib.suppress(Exception):
                url = f"{i + 1}:{sourceAttribution['providerDisplayName']} {sourceAttribution['seeMoreUrl']}"
                # 判断有没有imageLink
                if 'imageLink' in sourceAttribution:
                    try:
                        image = await download_image(sourceAttribution['imageLink'])
                        url += f" {image}"
                    except Exception:
                        url += f" {sourceAttribution['imageLink']}"
                urls.append(url)
        return urls
    except Exception:
        return []
    
async def format_bing_urls(msgs):
    urls = await get_bing_urls(msgs)
    ret = ""
    if urls:
        ret += "\nurls:\n"
        for url in urls:
            ret += f"{url}\n"
    return ret


def format_bing_suggestions(msgs):
    suggestions = get_bing_suggestions(msgs)
    ret = ""
    if suggestions:
        ret += "\nsuggestions:\n"
        for suggestion in suggestions:
            ret += f"{suggestion}\n"
    return ret


async def process_bing_response(response, uid):
    msgs = response['item']['messages']
    user_msg = {
        'author': uid,
        'msg': msgs[0]['text'],
    }
    bot_msg = {
        'author': 'bot',
        'msg': msgs[1]['text'],
    }
    msgs = msgs[1:]
    responseMsg = next((msg for msg in msgs if 'messageType' not in msg), None)
    bot_msg['msg'] = responseMsg['text'] or bot_msg['msg']
    
    
    save_to_history(uid, user_msg)
    save_to_history(uid, bot_msg)

    return f"\nbing: {bot_msg['msg']}\n{await format_bing_urls(responseMsg)}{format_bing_suggestions(responseMsg)}".strip()


async def get_bing_reply(prompt, uid, img_url: str=None): # type: ignore
    bing = await get_bing(uid)
    response = await get_bing_response(prompt, bing, img_url)
    return await process_bing_response(response, uid)


async def get_bing(uid: str):
    global bots
    uid = "1"
    if uid not in bots:
        bots[uid] = {
            'bot': Chatbot(cookies=config.cookies, proxy=config.proxy), # type: ignore
            'time': time.time()
        }
    if time.time() - bots[uid]['time'] > 60 * 10:
        await remove_bot(uid)
        return await get_bing(uid)
    return bots[uid]['bot']


async def remove_bot(uid: str):
    global bots
    uid = "1"
    if uid in bots:
        with contextlib.suppress(Exception):
            await bots[uid]['bot'].close()
        del bots[uid]


def get_history(uid: str):
    return load_from_json(os.path.join(path, "history", f"{uid}.json"))


def save_to_history(uid: str, msg: dict):
    history = get_history(uid)
    history.append(msg)
    dump_to_json(history, os.path.join(path, "history", f"{uid}.json"))

def merge_history_data(history, uid, uname, bid, bname):
    data = []
    for msg in history:
        if msg['author'] == 'user':
            merge_msg(data, msg['msg'], uname, uid)
        else:
            merge_msg(data, msg['msg'], bname, bid)
    return data


def get_history_reply(uid: str, uname: str, bname: str, bid: str):
    history = get_history(uid)
    return merge_history_data(history, uid, uname, bid, bname)

async def process_exit_event(bot, ev: CQEvent):
    uid = str(ev.user_id)
    remove_file(os.path.join(path, "history", f"{uid}.json"))
    await remove_bot(uid)
    await bot.send(ev, "清空历史记录成功", at_sender=True)


async def process_history_event(bot, ev: CQEvent):
    uid = str(ev.user_id)
    bid = str(ev.self_id)
    gid = str(ev.group_id)
    member_info = await bot.get_group_member_info(group_id=gid, user_id=uid)
    uname = (member_info["card"] or member_info["nickname"])
    bname = bot.config.NICKNAME
    history = get_history_reply(uid, uname, bname, bid)
    if not history:
        await bot.send(ev, "暂无历史记录", at_sender=True)
        return
    await bot.send_group_forward_msg(group_id=gid, messages=history)
    
async def send_bing_reply(bot, ev: CQEvent, msg: str, img_url: str=None):
    uid = str(ev.user_id)
    try_times = 5
    lastErr = None
    while try_times:
        try:
            ret = await get_bing_reply(msg.strip(), uid, img_url)
            await bot.send(ev, ret, at_sender=True)
            break
        except Exception as e:
            # e的类型
            type_e = type(e)
            if lastErr == type_e:
                await bot.send(ev, f"Failed: {e}, 不试了", at_sender=True)
                await remove_bot(uid)
                break
            err_msg = f"Failed: {e}, 累计尝试次数: {5 - try_times + 1}"
            lastErr = type_e
            if try_times == 1:
                err_msg = f"{err_msg}, 已经达到最大尝试次数, 已取消本次请求"
            else:
                err_msg = f"{err_msg}, 正在重新尝试..."
            await remove_bot(uid)
            await bot.send(ev, err_msg, at_sender=True)
            try_times -= 1

# 群号锁
locks = {}

@sv.on_prefix('bing')
async def bingchat(bot, ev: CQEvent):
    #gid = str(ev.group_id)
    gid = "1" # 临时改成所有群共用一个锁
    lock = locks.setdefault(gid, asyncio.Lock())
    msg = ev.message.extract_plain_text().strip()
    # 判断有没有锁
    if lock.locked():
        await bot.send(ev, "当前还有人在使用bing, 已加入队列，请耐心等待", at_sender=True)
    async with lock:
        if msg == "exit":
            await process_exit_event(bot, ev)
        elif msg == "history":
            await process_history_event(bot, ev)
        elif msg == "help":
            global sv_help
            await bot.send(ev, sv_help, at_sender=True)
        elif msg.strip() == "":
            await bot.send(ev, "请输入内容", at_sender=True)
        elif msg.startswith("create"):
            await bot.send(ev, await bing_img_create(msg[6:]), at_sender=True)
        else:
            img_url = next(
                (
                    ev_msg.data["url"]
                    for ev_msg in ev.message
                    if ev_msg.type == "image"
                ),
                None,
            )
            await send_bing_reply(bot, ev, msg, img_url) # type: ignore
