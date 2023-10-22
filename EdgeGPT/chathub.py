import asyncio
import json
import os
import ssl
import sys
from time import time
from typing import Generator
from typing import List
from typing import Union
import requests
from requests_toolbelt import MultipartEncoder
import random,string
import aiohttp
import certifi
import httpx
from BingImageCreator import ImageGenAsync
import urllib.parse

from .constants import DELIMITER
from .constants import HEADERS
from .constants import HEADERS_INIT_CONVER
from .conversation import Conversation
from .conversation_style import CONVERSATION_STYLE_TYPE
from .request import ChatHubRequest
from .utilities import append_identifier
from .utilities import get_ran_hex
from .utilities import guess_locale

ssl_context = ssl.create_default_context()
ssl_context.load_verify_locations(certifi.where())


class ChatHub:
    def __init__(
        self,
        conversation: Conversation,
        proxy: str = None, # type: ignore
        cookies: Union[List[dict], None] = None,
    ) -> None:
        self.aio_session = None
        self.request: ChatHubRequest
        self.loop: bool
        self.task: asyncio.Task
        self.request = ChatHubRequest(
            conversation_signature=conversation.struct["conversationSignature"],
            encrypted_conversation_signature=conversation.struct["encryptedConversationSignature"],
            client_id=conversation.struct["clientId"],
            conversation_id=conversation.struct["conversationId"],
        )
        self.cookies = cookies
        self.proxy: str = proxy
        proxy = ( # type: ignore
            proxy
            or os.environ.get("all_proxy")
            or os.environ.get("ALL_PROXY")
            or os.environ.get("https_proxy")
            or os.environ.get("HTTPS_PROXY")
            or None
        )
        if proxy is not None and proxy.startswith("socks5h://"):
            proxy = "socks5://" + proxy[len("socks5h://") :]
        self.session = httpx.AsyncClient(
            proxies=proxy,
            timeout=900,
            headers=HEADERS_INIT_CONVER,
        )

    async def get_conversation(
        self,
        conversation_id: str = None, # type: ignore
        conversation_signature: str = None, # type: ignore
        encrypted_conversation_signature: str = None, # type: ignore
        client_id: str = None, # type: ignore
    ) -> dict:
        conversation_id = conversation_id or self.request.conversation_id
        conversation_signature = (
            conversation_signature or self.request.conversation_signature
        )
        encrypted_conversation_signature = (
                encrypted_conversation_signature or self.request.encrypted_conversation_signature
        )
        client_id = client_id or self.request.client_id
        url = f"https://sydney.bing.com/sydney/GetConversation?conversationId={conversation_id}&source=cib&participantId={client_id}&conversationSignature={conversation_signature}&encryptedConversationSignature={encrypted_conversation_signature}&traceId={get_ran_hex()}"
        response = await self.session.get(url)
        return response.json()

    async def get_activity(self) -> dict:
        url = "https://www.bing.com/turing/conversation/chats"
        headers = HEADERS_INIT_CONVER.copy()
        if self.cookies is not None:
            for cookie in self.cookies:
                if cookie["name"] == "_U":
                    headers["Cookie"] = f"SUID=A; _U={cookie['value']};"
                    break
        response = await self.session.get(url, headers=headers)
        return response.json()
        
    async def upload_image(self, img_url: str,conversation_style: CONVERSATION_STYLE_TYPE = None) -> None:
        convotone = conversation_style.name # type: ignore
        convotone = convotone[0].upper() + convotone[1:]
        data = {
            "knowledgeRequest": {
                "imageInfo": {
                    "url": img_url,
                },
                "knowledgeRequest": {
                    "invokedSkills": ["ImageById"],
                    "subscriptionId": "Bing.Chat.Multimodal",
                    "invokedSkillsRequestData": {"enableFaceBlur": True},
                    "convoData": {
                        "convoid": "",#self.request.conversation_id,
                        "convotone": convotone,
                    },
                },
            },
            #"imageBase64": img_base64,
        }
        data = {k:json.dumps(v) if isinstance(v,dict) else v for k,v in data.items()}
        headers = HEADERS_INIT_CONVER.copy()
        headers["accept"] = "*/*"
        if self.cookies is not None:
            for cookie in self.cookies:
                if cookie["name"] == "_U":
                    headers["Cookie"] = f"SUID=A; _U={cookie['value']};"
                    break
        boundary = "----WebKitFormBoundary" + ''.join(random.sample(string.ascii_letters + string.digits, 16))
        m = MultipartEncoder(fields=data,boundary=boundary)
        headers["content-type"] = m.content_type
        headers["accept"] = "*/*"
        headers["origin"] = "https://www.bing.com"
        headers["referer"] = "https://www.bing.com/"
        headers["sec-ch-ua"] = '"Chromium";v="94", "Google Chrome";v="94", ";Not A Brand";v="99"'
        headers["sec-ch-ua-mobile"] = "?0"
        headers["sec-ch-ua-platform"] = '"Windows"'
        headers["sec-fetch-dest"] = "empty"
        headers["sec-fetch-mode"] = "cors"
        headers["sec-fetch-site"] = "same-site"
        try:
            resp = requests.post(
                "https://www.bing.com/images/kblob",
                headers=headers,
                data=m,
                proxies={"http":self.proxy,"https":self.proxy}
            )
            print(resp.status_code,resp.text)
            resp = resp.json()
        except Exception as e:
            print(e)
            return None
        self.blob_id = resp["blobId"]
        self.processed_blob_id = resp["processedBlobId"]
        #print("blob_id:", self.blob_id)
        #print("processed_blob_id:", self.processed_blob_id)
        return resp["blobId"],resp["processedBlobId"] # type: ignore

    async def ask_stream(
        self,
        prompt: str,
        wss_link: str = None, # type: ignore
        conversation_style: CONVERSATION_STYLE_TYPE = None,
        raw: bool = False,
        webpage_context: Union[str, None] = None,
        search_result: bool = False,
        locale: str = guess_locale(),
        img_url: str = None,  # 用于上传图片到bing # type: ignore
    ) -> Generator[bool, Union[dict, str], None]: # type: ignore
        """ """
        if self.request.encrypted_conversation_signature is not None:
            wss_link = wss_link or "wss://sydney.bing.com/sydney/ChatHub"
            wss_link += f"?sec_access_token={urllib.parse.quote(self.request.encrypted_conversation_signature)}"
        cookies = {}
        processedBlobId,blobId = None,None
        if self.cookies is not None:
            for cookie in self.cookies:
                cookies[cookie["name"]] = cookie["value"]
        if img_url is not None:
            _ = await self.upload_image(img_url,conversation_style=conversation_style)
            blobId,processedBlobId = _ # type: ignore
        self.aio_session = aiohttp.ClientSession(cookies=cookies)
        # Check if websocket is closed
        wss = await self.aio_session.ws_connect(
            wss_link or "wss://sydney.bing.com/sydney/ChatHub",
            ssl=ssl_context,
            headers=HEADERS,
            proxy=self.proxy,
        )
        await self._initial_handshake(wss)
        # Construct a ChatHub request
        self.request.update(
            prompt=prompt,
            conversation_style=conversation_style,
            webpage_context=webpage_context,
            search_result=search_result,
            locale=locale,
            processedBlobId=processedBlobId,
            blobId=blobId
        )
        # Send request
        await wss.send_str(append_identifier(self.request.struct))
        self.processed_blob_id = None
        self.blob_id = None
        draw = False
        resp_txt = ""
        result_text = ""
        resp_txt_no_link = ""
        retry_count = 5
        while not wss.closed:
            msg = await wss.receive_str()
            if not msg:
                retry_count -= 1
                if retry_count == 0:
                    raise Exception("No response from server")
                continue
            if isinstance(msg, str):
                objects = msg.split(DELIMITER)
            else:
                continue
            for obj in objects:
                if int(time()) % 6 == 0:
                    await wss.send_str(append_identifier({"type": 6}))
                if obj is None or not obj:
                    continue
                response = json.loads(obj)
                # print(response)
                if response.get("type") == 1 and response["arguments"][0].get(
                    "messages",
                ):
                    if not draw:
                        if (
                            response["arguments"][0]["messages"][0].get(
                                "messageType",
                            )
                            == "GenerateContentQuery"
                        ):
                            try:
                                async with ImageGenAsync(
                                    all_cookies=self.cookies, # type: ignore
                                ) as image_generator:
                                    images = await image_generator.get_images(
                                        response["arguments"][0]["messages"][0]["text"],
                                    )
                                for i, image in enumerate(images):
                                    resp_txt = f"{resp_txt}\n![image{i}]({image})"
                                draw = True
                            except Exception as e:
                                print(e)
                                continue
                        if (
                            (
                                response["arguments"][0]["messages"][0]["contentOrigin"]
                                != "Apology"
                            )
                            and not draw
                            and not raw
                        ):
                            resp_txt = result_text + response["arguments"][0][
                                "messages"
                            ][0]["adaptiveCards"][0]["body"][0].get("text", "")
                            resp_txt_no_link = result_text + response["arguments"][0][
                                "messages"
                            ][0].get("text", "")
                            if response["arguments"][0]["messages"][0].get(
                                "messageType",
                            ):
                                resp_txt = (
                                    resp_txt
                                    + response["arguments"][0]["messages"][0][
                                        "adaptiveCards"
                                    ][0]["body"][0]["inlines"][0].get("text")
                                    + "\n"
                                )
                                result_text = (
                                    result_text
                                    + response["arguments"][0]["messages"][0][
                                        "adaptiveCards"
                                    ][0]["body"][0]["inlines"][0].get("text")
                                    + "\n"
                                )
                        if not raw:
                            yield False, resp_txt # type: ignore

                elif response.get("type") == 2:
                    if response["item"]["result"].get("error"):
                        await self.close()
                        raise Exception(
                            f"{response['item']['result']['value']}: {response['item']['result']['message']}",
                        )
                    if draw:
                        cache = response["item"]["messages"][1]["adaptiveCards"][0][
                            "body"
                        ][0]["text"]
                        response["item"]["messages"][1]["adaptiveCards"][0]["body"][0][
                            "text"
                        ] = (cache + resp_txt)
                    if (
                        response["item"]["messages"][-1]["contentOrigin"] == "Apology"
                        and resp_txt
                    ):
                        response["item"]["messages"][-1]["text"] = resp_txt_no_link
                        response["item"]["messages"][-1]["adaptiveCards"][0]["body"][0][
                            "text"
                        ] = resp_txt
                        print(
                            "Preserved the message from being deleted",
                            file=sys.stderr,
                        )
                    await wss.close()
                    if not self.aio_session.closed:
                        await self.aio_session.close()
                    yield True, response # type: ignore
                    return
                if response.get("type") != 2:
                    if response.get("type") == 6:
                        await wss.send_str(append_identifier({"type": 6}))
                    elif response.get("type") == 7:
                        await wss.send_str(append_identifier({"type": 7}))
                    elif raw:
                        yield False, response # type: ignore

    async def _initial_handshake(self, wss) -> None:
        await wss.send_str(append_identifier({"protocol": "json", "version": 1}))
        await wss.receive_str()
        await wss.send_str(append_identifier({"type": 6}))

    async def delete_conversation(
        self,
        conversation_id: str = None, # type: ignore
        conversation_signature: str = None, # type: ignore
        encrypted_conversation_signature: str = None, # type: ignore
        client_id: str = None, # type: ignore
    ) -> None:
        conversation_id = conversation_id or self.request.conversation_id
        conversation_signature = (
            conversation_signature or self.request.conversation_signature
        )
        encrypted_conversation_signature = (
                encrypted_conversation_signature or self.request.encrypted_conversation_signature
        )
        client_id = client_id or self.request.client_id
        url = "https://sydney.bing.com/sydney/DeleteSingleConversation"
        await self.session.post(
            url,
            json={
                "conversationId": conversation_id,
                "conversationSignature": conversation_signature,
                "encryptedConversationSignature": encrypted_conversation_signature,
                "participant": {"id": client_id},
                "source": "cib",
                "optionsSets": ["autosave"],
            },
        )

    async def close(self) -> None:
        await self.session.aclose()
