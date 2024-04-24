from .EdgeGPT.ImageGen import ImageGenAsync
import os
from .utils import async_download_images
from . import config
path = os.path.dirname(os.path.abspath(__file__))

class ImageGenConfig:
    def __init__(self, cookies, quiet: bool = True):
        # self.output_dir = output_dir
        self.quiet = quiet
        self.cookies = cookies
        self.U = self.get_U()
        
        
    def get_U(self):
        if self.cookies is not None:
            for cookie in self.cookies:
                if cookie["name"] == "_U":
                    return cookie["value"]
                

async def async_image_gen(prompt):
    image_gen_config = ImageGenConfig(
        # output_dir=os.path.join(path, "imgoutput"),
        quiet=True,
        cookies = config.cookies
    )
    async with ImageGenAsync(auth_cookie = image_gen_config.U, quiet = image_gen_config.quiet, proxy=config.proxy) as image_generator:
        return await image_generator.get_images(prompt) # url list
        # await image_generator.save_images(images, output_dir=image_gen_config.output_dir)
        
async def bing_img_create(prompt):
    try:
        urls = await async_image_gen(prompt)
        return "\n".join(urls)
    except Exception as e:
        return f"图片生成失败：{e}"
