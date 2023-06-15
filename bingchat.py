import os
import json
import contextlib
from EdgeGPT import Chatbot, ConversationStyle
from hoshino import Service, priv, get_bot
from hoshino.typing import CQEvent

path = os.path.dirname(os.path.abspath(__file__))
bots = {}
cookie = {}

sv_help = '''
[bing xxx] 与bing聊天
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
    global cookies
    with open(os.path.join(path, "cookies.json"), "r") as f:
        cookies = json.load(f)
    if not os.path.exists(os.path.join(path, "history")):
        os.mkdir(os.path.join(path, "history"))
    
    
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


async def get_bing_response(prompt, bing):
    return await bing.ask(prompt=prompt, conversation_style=ConversationStyle.creative)


def get_bing_suggestions(msgs):
    try:
        return [suggest['text'] for suggest in msgs[1]['suggestedResponses']] if msgs[1]['suggestedResponses'] else []
    except Exception:
        return []


def get_bing_urls(msgs):
    try:
        return [f"{i + 1}:{sourceAttribution['providerDisplayName']} {sourceAttribution['seeMoreUrl']}"
                for i, sourceAttribution in enumerate(msgs[1]['sourceAttributions'])]
    except Exception:
        return []


def format_bing_urls(msgs):
    urls = get_bing_urls(msgs)
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


def process_bing_response(response, uid):
    msgs = response['item']['messages']
    user_msg = {
        'author': uid,
        'msg': msgs[0]['text'],
    }
    bot_msg = {
        'author': 'bot',
        'msg': msgs[1]['text'],
    }
    save_to_history(uid, user_msg)
    save_to_history(uid, bot_msg)

    return f"\nbing: {bot_msg['msg']}\n{format_bing_urls(msgs)}{format_bing_suggestions(msgs)}".strip()


async def get_bing_reply(prompt, uid):
    bing = await get_bing(uid)
    response = await get_bing_response(prompt, bing)
    return process_bing_response(response, uid)


async def get_bing(uid: str):
    if uid not in bots:
        bots[uid] = {
            'bot': Chatbot(cookies=cookies),
        }
    return bots[uid]['bot']


async def remove_bot(uid: str):
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


def merge_msg(data, msg, name, uid):  # 合并消息
    data.append({
        "type": "node",
        "data": {
            "name": f"{name}",
            "uin": f"{uid}",
            "content": msg
        },
    })
    return data


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

async def send_bing_reply(bot, ev: CQEvent, msg: str):
    uid = str(ev.user_id)
    try_times = 5
    while try_times:
        try:
            ret = await get_bing_reply(msg.strip(), uid)
            await bot.send_txt2img(ev, ret, at_sender=True)
            break
        except Exception as e:
            err_msg = f"Failed: {e}, 累计尝试次数: {5 - try_times + 1}"
            if try_times == 1:
                err_msg = f"{err_msg}, 已经达到最大尝试次数, 已取消本次请求"
            else:
                err_msg = f"{err_msg}, 正在重新尝试..."
            await remove_bot(uid)
            await bot.send(ev, err_msg, at_sender=True)
            try_times -= 1

@sv.on_prefix('bing')
async def bingchat(bot, ev: CQEvent):
    msg = ev.message.extract_plain_text()
    if msg == "exit":
        await process_exit_event(bot, ev)
    elif msg == "history":
        await process_history_event(bot, ev)
    elif msg == "help":
        await bot.send(ev, "bing xxx: 必应聊天\nbing exit: 清空历史记录,重置会话\nbing history: 查看历史记录\nbing help: 查看帮助", at_sender=True)
    elif msg.strip() == "":
        await bot.send(ev, "请输入内容", at_sender=True)
    else:
        await send_bing_reply(bot, ev, msg)