# BingAIChat

## 简介

- 适用于HoshinoBot的bing聊天插件

## 部署

- 在`hoshino/modules`下执行：

    ```shell
    git clone https://github.com/X-Zero-L/BingAIChat.git
    pip install -r BingAIChat/requirements.txt
    ```

- 获取Cookie

  - 要求
    - 一个可以访问必应聊天的微软账户 <https://bing.com/chat> (可选，视所在地区而定)
    - 需要在 New Bing 支持的国家或地区（中国大陆需使用VPN）
  - 步骤
    1. 安装 [Chrome](https://chrome.google.com/webstore/detail/cookie-editor/hlkenndednhfkekhgcdicdfddnkalmdm) 或 [Firefox](https://addons.mozilla.org/en-US/firefox/addon/cookie-editor/) 的 cookie editor 扩展
    2. 移步到 [bing.com](https://bing.com)
    3. 打开扩展程序
    4. 点击右下角的"导出" ，然后点击"导出为 JSON" (将会把内容保存到你的剪贴板上)
    5. 把你剪贴板上的内容粘贴到 `BingAIChat/cookies.json` 文件中（如果没有则新建）

- 添加代理（如果需要）

  - 在`BingAIChat/config.json.example`中修改`proxy`变量

    ```json
    {
        "proxy": "你的代理地址" # 例如：http://127.0.0.1:7890
    }
    ```

  - 重命名`BingAIChat/config.json.example`为`BingAIChat/config.json`

- 在`hoshino/config/__bot__.py`中加入`BingAIChat`模块

    ```python
    MODULES_ON = {
        ...
        'BingAIChat',#bing聊天插件
        ...
    }
    ```

- 重启bot

## 使用

- `bing [文本内容] [图片]`：bing聊天,内容为必填,图片为可选,如果带有图片,bing会进行识别
- `bing create [prompt]`：bing绘图
- `bing exit`：重置会话，清空聊天记录
- `bing help`：查看帮助
- `bing history`：查看聊天记录

## 注意事项

- 在初次使用本插件生成图片之前，请进入bing的官方网站[bingImageCreate](https://www.bing.com/images/create)，手动生成一张图片。(对话也一样）
- 如果遇到验证码问题，目前的解决办法是你自己去网页和bing进行一次对话，一般情况不需要更新cookies，如果对话后还无法解决问题，再更换新的cookies
- 当前修改为单例以应对bing的并发会话限制,可自行删除对应代码,分别是群锁部分和被硬编码的实例uid部分