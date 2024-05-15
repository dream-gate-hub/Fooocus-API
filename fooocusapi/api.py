import uvicorn

from typing import List, Optional
from fastapi import Depends, FastAPI, Header, Query, Response, UploadFile, APIRouter, Depends
from fastapi.params import File
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from fooocusapi.args import args
from fooocusapi.models import *
from fooocusapi.api_utils import req_to_params, generate_async_output, generate_streaming_output, generate_image_result_output, api_key_auth
import fooocusapi.file_utils as file_utils
from fooocusapi.parameters import GenerationFinishReason, ImageGenerationResult
from fooocusapi.task_queue import TaskType
from fooocusapi.worker import worker_queue, process_top, blocking_get_task_result
from fooocusapi.models_v2 import *
from fooocusapi.img_utils import base64_to_stream, read_input_image

from modules.util import HWC3
import random

import torch
from PIL import Image
from transformers import CLIPSegProcessor, CLIPSegForImageSegmentation
from scipy.ndimage import gaussian_filter
import matplotlib.cm as cm
import numpy as np
import cv2
import os
import time
from typing import Dict
from io import BytesIO
import base64


##############

negative_prompts = [
"""
worst quality, large head, low quality, extra digits, bad eye, EasyNegativeV2, ng_deepnegative_v1_75t,bad hands, bad arms, missing fingers, missing arms, missing hands, missing digit, missing limbs, extra digit, fewer digits, fused hands, poorly drawn hands, poorly drawn hands, three hands, fewer digits, fused fingers, extra fingers, extra limbs, extra arms, malformed limbs, too many fingers, mutated hands, urgly arms, abnormal hands, poorly drawn digit, poorly drawn hands, abnormal digit, one hand with more than five digit, too long digit, boken limb,bad anatomy,text, signature, watermark, username, artist name, stamp, title, subtitle, date, footer, header,multipul angle, two shot, split view, grid view
""",
"""
bad anatomy, bad hands, mutated hand, text, error, missing fingers
"""
]

class Image_Style(BaseModel):
    id: int = 0

class ImageStyle():
    def __init__(self, model: str, styles: List[str] = ["Fooocus V2", "Fooocus Masterpiece"], sdxl_fast: bool = False, use_default: bool = False, guidance_scale: int = 1, cfg: int = 4, steps: int = 8, sampler_name: str = "dpmpp_sde_gpu", scheduler_name: str = "sgm_uniform", negative_prompt: int = 0):
        self.model = model  
        self.styles = styles
        self.negative_prompt = negative_prompts[negative_prompt]
        
        if use_default:
            if sdxl_fast:
                self.guidance_scale = 1
                self.cfg = 4
                self.steps = 15
                self.sampler_name = "dpmpp_sde_gpu"
                self.scheduler_name = "sgm_uniform"
            else:
                self.guidance_scale = 4
                self.cfg = 7
                self.steps = 50
                self.sampler_name = "dpmpp_2m_sde_gpu"
                self.scheduler_name = "karras"
        else:
            self.guidance_scale = guidance_scale
            self.cfg = cfg
            self.steps = steps
            self.sampler_name = sampler_name
            self.scheduler_name = scheduler_name

    """
    fast
    ImageStyle("218xl_turbotest.safetensors", sdxl_fast = True),                     
    ImageStyle("aamXLAnimeMix_v10HalfturboEulera.safetensors", sdxl_fast = True),    
    ImageStyle("atomixAnimeXL_v10.safetensors", sdxl_fast = True, cfg = 2, steps = 8, sampler_name = "dpmpp_sde_gpu", scheduler_name = "sgm_uniform"),                    
    ImageStyle("bluePencilXLLCM_v310Lcm.safetensors", sdxl_fast = True),             
    ImageStyle("bluePencilXLLCM_v500Lightning.safetensors", sdxl_fast = True, cfg = 2, steps = 15, sampler_name = "dpmpp_sde_gpu", scheduler_name = "sgm_uniform"),      
    ImageStyle("breakdomainxl_V06d.safetensors", sdxl_fast = True, use_default = True),                  
    ImageStyle("dreamshaperXL_alpha2Xl10.safetensors", sdxl_fast = True),            
    ImageStyle("duchaitenNijiuncen_v10LightningTCD.safetensors", sdxl_fast = True, cfg = 5, steps = 12, sampler_name = "euler_ancestral"),
    ImageStyle("envyStarlightXL01Lightning_v10.safetensors", sdxl_fast = True, cfg = 5, steps = 8, sampler_name = "euler_ancestral"),
    ImageStyle("envyturboagendaxl01Anime_v11.safetensors", sdxl_fast = True, cfg = 2.5, steps = 8, sampler_name = "dpmpp_2m_sde", scheduler_name = "karras"),
    ImageStyle("juggernautXL_v9Rdphoto2Lightning.safetensors", sdxl_fast = True, cfg = 2, steps = 6, sampler_name = "dpmpp_sde", scheduler_name = "karras"),
    ImageStyle("level4XL_alphaV02.safetensors", sdxl_fast = True, cfg = 3, steps = 8, sampler_name = "dpmpp_sde", scheduler_name = "karras"),
    ImageStyle("odemXL_v2.safetensors", sdxl_fast = True),
    ImageStyle("osorubeshixlKakkoii_v10.safetensors", sdxl_fast = True, cfg = 3, steps = 8, sampler_name = "euler_ancestral", scheduler_name = "karras"),
    ImageStyle("reproductionLCM_v2.safetensors", sdxl_fast = True),
    ImageStyle("vibrantHorizonTurbo_v20.safetensors", sdxl_fast = True, cfg = 3.5, steps = 10, sampler_name = "dpmpp_2m_sde", scheduler_name = "karras"),
    ImageStyle("vxpXLTURBO_vxpXLV15.safetensors", sdxl_fast = True, cfg = 3, steps = 8, sampler_name = "euler_ancestral", scheduler_name = "karras"),

    ImageStyle("7thAnimeXLA_v10.safetensors", use_default=True),
    ImageStyle("afroditexlNudePeople_31.safetensors", use_default=True),
    ImageStyle("copaxTimelessxlSDXL1_v12.safetensors", use_default=True),
    ImageStyle("everclearPNYByZovya_v2VAE.safetensors", use_default=True),
    ImageStyle("fullyREALXL_v90Vividreal.safetensors", cfg = 4, steps = 60, sampler_name = "DPM++ 2M SDE"),
    ImageStyle("iniverseMixXLSFWNSFW_v75Real.safetensors", use_default=True),
    ImageStyle("PVCStyleModelMovable_beta25Realistic.safetensors", use_default=True),
    ImageStyle("tPonynai3_v35.safetensors", use_default=True),
    ImageStyle("zavychromaxl_v60.safetensors", use_default=True),

    ImageStyle("holoanimeXL_v27.safetensors", use_default=True),
    ImageStyle("pilgrim2DSDXL_v50.safetensors", use_default=True),
    ImageStyle("raemuXL_v30.safetensors", use_default=True),
    ImageStyle("randommaxxArtMerge_v10.safetensors", use_default=True),


    sdxl
    ImageStyle("aamXLAnimeMix_v10.safetensors", use_default=True),
    ImageStyle("animagineXL_v20.safetensors", use_default=True),
    ImageStyle("animagineXLV31_v31.safetensors", guidance_scale = 4, cfg = 7, steps = 30, sampler_name = "euler_ancestral", scheduler_name = "karras"),
    ImageStyle("animaPencilXL_v300.safetensors", use_default=True),
    ImageStyle("animeIllustDiffusion_v08.safetensors", use_default=True),
    ImageStyle("AnythingXL_xl.safetensors", use_default=True),
    ImageStyle("artium_v20.safetensors", use_default=True),
    ImageStyle("bluePencilXL_v401.safetensors", use_default=True),
    ImageStyle("bluePencilXL_v600.safetensors", use_default=True),
    ImageStyle("CHEYENNE_v16.safetensors", use_default=True),
    ImageStyle("counterfeitxl_v25.safetensors", use_default=True),
    ImageStyle("dreamshaperXL_alpha2Xl10.safetensors", use_default=True),
    ImageStyle("hassakuXLSfwNsfw_betaV06.safetensors", use_default=True),
    ImageStyle("himawarimix_xlV6.safetensors", use_default=True),
    ImageStyle("juggernautXL_version6Rundiffusion.safetensors", use_default=True),
    ImageStyle("matrixHentaiPlusXL_v16.safetensors", use_default=True),
    ImageStyle("protovisionXLHighFidelity3D.safetensors", use_default=True),
    ImageStyle("reproductionSDXL_2v12.safetensors", use_default=True),
    ImageStyle("sdvn7Nijistylexl_v1.safetensors", use_default=True),
    ImageStyle("sdxlUnstableDiffusers_nihilmania.safetensors", use_default=True),
    ImageStyle("sdxlYamersAnime_stageAnima.safetensors", use_default=True),
    ImageStyle("ponyDiffusionV6XL_v6StartWithThisOne.safetensors", use_default=True),
    ImageStyle("starlightXLAnimated_v3.safetensors", use_default=True),
    ImageStyle("sdxlNijiSpecial_sdxlNijiSE.safetensors", use_default=True),

    在用
    ImageStyle("AnythingXL_xl.safetensors", use_default=True),
    ImageStyle("animaPencilXL_v300.safetensors", use_default=True),
    ImageStyle("sdxlYamersAnime_stageAnima.safetensors", use_default=True),
    ImageStyle("duchaitenNijiuncen_v10LightningTCD.safetensors", sdxl_fast = True, cfg = 5, steps = 12, sampler_name = "euler_ancestral"),
    ImageStyle("animagineXL_v20.safetensors", use_default=True),
    ImageStyle("atomixAnimeXL_v10.safetensors", sdxl_fast = True, cfg = 2, steps = 8, sampler_name = "dpmpp_sde_gpu", scheduler_name = "sgm_uniform"), 
    ImageStyle("breakdomainxl_V06d.safetensors", sdxl_fast = True, use_default = True),  
    ImageStyle("sdvn7Nijistylexl_v1.safetensors", use_default=True),
    ImageStyle("envyStarlightXL01Lightning_v10.safetensors", sdxl_fast = True, cfg = 5, steps = 8, sampler_name = "euler_ancestral"),
    ImageStyle("CHEYENNE_v16.safetensors", use_default=True),
    ImageStyle("juggernautXL_v9Rdphoto2Lightning.safetensors", sdxl_fast = True, cfg = 2, steps = 6, sampler_name = "dpmpp_sde", scheduler_name = "karras"),
    ImageStyle("ponyDiffusionV6XL_v6StartWithThisOne.safetensors", use_default=True),
    ImageStyle("sdxlNijiSpecial_sdxlNijiSE.safetensors", use_default=True),
    """
image_styles = [

    ImageStyle("animagineXL_v20.safetensors", use_default=True),
    ImageStyle("envyStarlightXL01Lightning_v10.safetensors", sdxl_fast = True, cfg = 5, steps = 8, sampler_name = "euler_ancestral"),
    ImageStyle("AnythingXL_xl.safetensors", use_default=True),
    ImageStyle("sdxlYamersAnime_stageAnima.safetensors", use_default=True),
    ImageStyle("sdvn7Nijistylexl_v1.safetensors", use_default=True),
    ImageStyle("duchaitenNijiuncen_v10LightningTCD.safetensors", sdxl_fast = True, cfg = 5, steps = 12, sampler_name = "euler_ancestral"),
    ImageStyle("sdxlNijiSpecial_sdxlNijiSE.safetensors", use_default=True),
    ImageStyle("animaPencilXL_v300.safetensors", use_default=True),
    ImageStyle("atomixAnimeXL_v10.safetensors", sdxl_fast = True, cfg = 2, steps = 8, sampler_name = "dpmpp_sde_gpu", scheduler_name = "sgm_uniform"), 
    ImageStyle("juggernautXL_v9Rdphoto2Lightning.safetensors", sdxl_fast = True, cfg = 2, steps = 6, sampler_name = "dpmpp_sde", scheduler_name = "karras"),
    ImageStyle("CHEYENNE_v16.safetensors", use_default=True),
    ImageStyle("breakdomainxl_V06d.safetensors", sdxl_fast = True, use_default = True),  
    
]

def overwrite_style_params(req: Text2ImgRequest, imageStyle: ImageStyle, id: int, upscale: bool = False, extend_prompt: bool = True) -> Text2ImgRequest:
    req.image_style = id
    req.base_model_name = imageStyle.model
    if extend_prompt :
        req.prompt = "(masterpiece), ultra-detailed, (illustration), ultra-detailed, (extremely delicate eyes:1.3), masterpiece, best quality, " + req.prompt
    req.negative_prompt = imageStyle.negative_prompt
    req.guidance_scale = imageStyle.guidance_scale
    req.style_selections = imageStyle.styles
    req.advanced_params.adaptive_cfg = imageStyle.cfg   
    req.advanced_params.overwrite_step = imageStyle.steps
    req.advanced_params.sampler_name = imageStyle.sampler_name
    req.advanced_params.scheduler_name = imageStyle.scheduler_name
    if upscale:
        req.advanced_params.overwrite_step = int(imageStyle.steps * 0.6)
    return req


# Help Function for head detection
def tensor_to_numpy(tensor: torch.Tensor) -> np.ndarray:
    """Convert a tensor to a numpy array and scale its values to 0-255."""
    array = tensor.numpy().squeeze()
    return (array * 255).astype(np.uint8)

def numpy_to_tensor(array: np.ndarray) -> torch.Tensor:
    """Convert a numpy array to a tensor and scale its values from 0-255 to 0-1."""
    array = array.astype(np.float32) / 255.0
    return torch.from_numpy(array)[None,]

def apply_colormap(mask: torch.Tensor, colormap) -> np.ndarray:
    """Apply a colormap to a tensor and convert it to a numpy array."""
    colored_mask = colormap(mask.numpy())[:, :, :3]
    return (colored_mask * 255).astype(np.uint8)

def resize_image(image: np.ndarray, dimensions: Tuple[int, int]) -> np.ndarray:
    """Resize an image to the given dimensions using linear interpolation."""
    return cv2.resize(image, dimensions, interpolation=cv2.INTER_LINEAR)

def overlay_image(background: np.ndarray, foreground: np.ndarray, alpha: float) -> np.ndarray:
    """Overlay the foreground image onto the background with a given opacity (alpha)."""
    return cv2.addWeighted(background, 1 - alpha, foreground, alpha, 0)

def dilate_mask(mask: torch.Tensor, dilation_factor: float) -> torch.Tensor:
    """Dilate a mask using a square kernel with a given dilation factor."""
    kernel_size = int(dilation_factor * 2) + 1
    kernel = np.ones((kernel_size, kernel_size), np.uint8)
    mask_dilated = cv2.dilate(mask.numpy(), kernel, iterations=1)
    return torch.from_numpy(mask_dilated)

#load model for head detection

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow access from all sources
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all request headers
)

secure_router = APIRouter(
    dependencies=[Depends(api_key_auth)]
)

img_generate_responses = {
    "200": {
        "description": "PNG bytes if request's 'Accept' header is 'image/png', otherwise JSON",
        "content": {
            "application/json": {
                "example": [{
                    "base64": "...very long string...",
                    "seed": "1050625087",
                    "finish_reason": "SUCCESS"
                }]
            },
            "application/json async": {
                "example": {
                    "job_id": 1,
                    "job_type": "Text to Image"
                }
            },
            "image/png": {
                "example": "PNG bytes, what did you expect?"
            }
        }
    }
}


def get_task_type(req: Text2ImgRequest) -> TaskType:
    if isinstance(req, ImgUpscaleOrVaryRequest) or isinstance(req, ImgUpscaleOrVaryRequestJson):
        return TaskType.img_uov
    elif isinstance(req, ImgPromptRequest) or isinstance(req, ImgPromptRequestJson):
        return TaskType.img_prompt
    elif isinstance(req, ImgInpaintOrOutpaintRequest) or isinstance(req, ImgInpaintOrOutpaintRequestJson):
        return TaskType.img_inpaint_outpaint
    else:
        return TaskType.text_2_img


def call_worker(req: Text2ImgRequest, accept: str, priority: bool = False,step2req: bool = False) -> Response | AsyncJobResponse | List[GeneratedImageResult]:  
    #priority =True :the task will be done first   step2req =True : for 2 step task's first step used for waiting 
    if accept == 'image/png':
        streaming_output = True
        # image_number auto set to 1 in streaming mode
        req.image_number = 1
    else:
        streaming_output = False
    """
    req.base_model_name = "atomixAnimeXL_v10.safetensors"
    req.advanced_params.overwrite_step = 8
    req.advanced_params.adaptive_cfg = 2
    req.guidance_scale = 1
    req.advanced_params.sampler_name = "dpmpp_sde_gpu"
    req.advanced_params.scheduler_name = "sgm_uniform"
    """

    print(f"图片风格：{req.image_style}")
    print(f"图片prompt：{req.prompt}")

    task_type = get_task_type(req)
    params = req_to_params(req)
    async_task = worker_queue.add_task(task_type, params, req.webhook_url, priority,step2req)

    if async_task is None:
        # add to worker queue failed
        failure_results = [ImageGenerationResult(im=None, seed='', finish_reason=GenerationFinishReason.queue_is_full)]

        if streaming_output:
            return generate_streaming_output(failure_results)
        if req.async_process:
            return AsyncJobResponse(job_id='',
                                    job_type=get_task_type(req),
                                    job_stage=AsyncJobStage.error,
                                    job_progress=0,
                                    job_status=None,
                                    job_step_preview=None,
                                    job_result=failure_results)
        else:
            return generate_image_result_output(failure_results, False)

    if req.async_process:
        # return async response directly
        return generate_async_output(async_task)
    
    # blocking get generation result
    results = blocking_get_task_result(async_task.job_id)

    if streaming_output:
        return generate_streaming_output(results)
    else:
        return generate_image_result_output(results, req.require_base64, req.image_style)


def stop_worker():
    process_top()



@app.get("/")
def home():
    return Response(content='Swagger-UI to: <a href="/docs">/docs</a>', media_type="text/html")


@app.get("/ping", description="Returns a simple 'pong' response")
def ping():
    return Response(content='pong', media_type="text/html")

@secure_router.post("/v1/generation/text-to-image-upscale",response_model=List[GeneratedImageResult] | AsyncJobResponse, responses=img_generate_responses)
def text2imgAndUpscale_generation(text_to_image_req: Text2ImgRequest, up_scale_req: ImgUpscaleOrVaryRequestJson, accept: str = Header(None),
                        accept_query: str | None = Query(None, alias='accept', description="Parameter to overvide 'Accept' header, 'image/png' for output bytes")):

    #up_scale_req.upscale_value = 1.5

    if up_scale_req.upscale_value<=1:
        return text2img_generation(req=text_to_image_req,accept=accept,accept_query=accept_query)
    if accept_query is not None and len(accept_query) > 0:
        accept = accept_query
    text_to_image_req.require_base64=True
    step1 = call_worker(text_to_image_req, accept,step2req=True)
    up_scale_req.input_image=step1[0].base64
    
    up_scale_req.input_image = base64_to_stream(up_scale_req.input_image)

    default_image_promt = ImagePrompt(cn_img=None)
    image_prompts_files: List[ImagePrompt] = []
    for img_prompt in up_scale_req.image_prompts:
        img_prompt.cn_img = base64_to_stream(img_prompt.cn_img)
        image = ImagePrompt(cn_img=img_prompt.cn_img,
                            cn_stop=img_prompt.cn_stop,
                            cn_weight=img_prompt.cn_weight,
                            cn_type=img_prompt.cn_type)
        image_prompts_files.append(image)
    while len(image_prompts_files) <= 4:
        image_prompts_files.append(default_image_promt)
    up_scale_req.image_prompts = image_prompts_files
    return call_worker(up_scale_req, accept,priority=True)


@secure_router.post("/v2/generation/text-to-image",response_model=List[GeneratedImageResult] | AsyncJobResponse, responses=img_generate_responses)
def text2img_generation(text_to_image_req: Text2ImgRequest, up_scale_req: ImgUpscaleOrVaryRequestJson, image_style: Image_Style, accept: str = Header(None),
                        accept_query: str | None = Query(None, alias='accept', description="Parameter to overvide 'Accept' header, 'image/png' for output bytes")):
    
    if (image_style.id == -1) or (image_style.id>=len(image_styles)):
        image_style.id = random.randint(0, len(image_styles)-1)
    style = image_styles[image_style.id]
    text_to_image_req = overwrite_style_params(text_to_image_req, style, image_style.id)
    if text_to_image_req.advanced_params.overwrite_step != 50:
        up_scale_req.upscale_value = 1.5
    up_scale_req = overwrite_style_params(up_scale_req, style, image_style.id, upscale=True)
    
    text_to_image_req.image_style = image_style.id
    up_scale_req.image_style = image_style.id

    if up_scale_req.upscale_value<=1:
        return text2img_generation(req=text_to_image_req,accept=accept,accept_query=accept_query)
    if accept_query is not None and len(accept_query) > 0:
        accept = accept_query
    text_to_image_req.require_base64=True
    step1 = call_worker(text_to_image_req, accept,step2req=True)
    up_scale_req.input_image=step1[0].base64
    
    up_scale_req.input_image = base64_to_stream(up_scale_req.input_image)

    default_image_promt = ImagePrompt(cn_img=None)
    image_prompts_files: List[ImagePrompt] = []
    for img_prompt in up_scale_req.image_prompts:
        img_prompt.cn_img = base64_to_stream(img_prompt.cn_img)
        image = ImagePrompt(cn_img=img_prompt.cn_img,
                            cn_stop=img_prompt.cn_stop,
                            cn_weight=img_prompt.cn_weight,
                            cn_type=img_prompt.cn_type)
        image_prompts_files.append(image)
    while len(image_prompts_files) <= 4:
        image_prompts_files.append(default_image_promt)
    up_scale_req.image_prompts = image_prompts_files
    return call_worker(up_scale_req, accept,priority=True)


@secure_router.post("/v1/generation/text-to-image", response_model=List[GeneratedImageResult] | AsyncJobResponse, responses=img_generate_responses)
def text2img_generation(req: Text2ImgRequest, accept: str = Header(None),
                        accept_query: str | None = Query(None, alias='accept', description="Parameter to overvide 'Accept' header, 'image/png' for output bytes")):
    if accept_query is not None and len(accept_query) > 0:
        accept = accept_query
    return call_worker(req, accept)


@secure_router.post("/v2/generation/text-to-image-with-ip", response_model=List[GeneratedImageResult] | AsyncJobResponse, responses=img_generate_responses)
def text_to_img_with_ip(req: Text2ImgRequestWithPrompt,
                        accept: str = Header(None),
                        accept_query: str | None = Query(None, alias='accept', description="Parameter to overvide 'Accept' header, 'image/png' for output bytes")):
    if accept_query is not None and len(accept_query) > 0:
        accept = accept_query

    default_image_promt = ImagePrompt(cn_img=None)
    image_prompts_files: List[ImagePrompt] = []
    for img_prompt in req.image_prompts:
        img_prompt.cn_img = base64_to_stream(img_prompt.cn_img)
        image = ImagePrompt(cn_img=img_prompt.cn_img,
                            cn_stop=img_prompt.cn_stop,
                            cn_weight=img_prompt.cn_weight,
                            cn_type=img_prompt.cn_type)
        image_prompts_files.append(image)

    while len(image_prompts_files) <= 4:
        image_prompts_files.append(default_image_promt)

    req.image_prompts = image_prompts_files

    return call_worker(req, accept)


@secure_router.post("/v1/generation/image-upscale-vary", response_model=List[GeneratedImageResult] | AsyncJobResponse, responses=img_generate_responses)
def img_upscale_or_vary(input_image: UploadFile, req: ImgUpscaleOrVaryRequest = Depends(ImgUpscaleOrVaryRequest.as_form),
                        accept: str = Header(None),
                        accept_query: str | None = Query(None, alias='accept', description="Parameter to overvide 'Accept' header, 'image/png' for output bytes")):
    if accept_query is not None and len(accept_query) > 0:
        accept = accept_query

    return call_worker(req, accept)


@secure_router.post("/v2/generation/image-upscale-vary", response_model=List[GeneratedImageResult] | AsyncJobResponse, responses=img_generate_responses)
def img_upscale_or_vary_v2(req: ImgUpscaleOrVaryRequestJson,
                           accept: str = Header(None),
                           accept_query: str | None = Query(None, alias='accept', description="Parameter to overvide 'Accept' header, 'image/png' for output bytes")):
    if accept_query is not None and len(accept_query) > 0:
        accept = accept_query

    req.input_image = base64_to_stream(req.input_image)

    default_image_promt = ImagePrompt(cn_img=None)
    image_prompts_files: List[ImagePrompt] = []
    for img_prompt in req.image_prompts:
        img_prompt.cn_img = base64_to_stream(img_prompt.cn_img)
        image = ImagePrompt(cn_img=img_prompt.cn_img,
                            cn_stop=img_prompt.cn_stop,
                            cn_weight=img_prompt.cn_weight,
                            cn_type=img_prompt.cn_type)
        image_prompts_files.append(image)
    while len(image_prompts_files) <= 4:
        image_prompts_files.append(default_image_promt)
    req.image_prompts = image_prompts_files

    return call_worker(req, accept)


@secure_router.post("/v3/generation/image-upscale-vary", response_model=List[GeneratedImageResult] | AsyncJobResponse, responses=img_generate_responses)
def img_upscale_or_vary_v3(image_upscale_or_vary_req: ImgUpscaleOrVaryRequestJson, image_style: Image_Style,
                           accept: str = Header(None),
                           accept_query: str | None = Query(None, alias='accept', description="Parameter to overvide 'Accept' header, 'image/png' for output bytes")):
    
    if (image_style.id == -1) or (image_style.id>=len(image_styles)):
        image_style.id = random.randint(0, len(image_styles)-1)

    vary_mode = image_upscale_or_vary_req.advanced_params.overwrite_vary_strength >= 0

    style = image_styles[image_style.id]
    image_upscale_or_vary_req = overwrite_style_params(image_upscale_or_vary_req, style, image_style.id, not vary_mode, extend_prompt=False)
    
    if accept_query is not None and len(accept_query) > 0:
        accept = accept_query

    if image_upscale_or_vary_req.prompt == "":
        from extras.wd14tagger import default_interrogator as default_interrogator_anime
        interrogator = default_interrogator_anime
        image = base64_to_stream(image_upscale_or_vary_req.input_image)
        img = HWC3(read_input_image(image))
        result = interrogator(img)
        image_upscale_or_vary_req.prompt = result

    image_upscale_or_vary_req.input_image = base64_to_stream(image_upscale_or_vary_req.input_image)
    default_image_promt = ImagePrompt(cn_img=None)
    image_prompts_files: List[ImagePrompt] = []
    for img_prompt in image_upscale_or_vary_req.image_prompts:
        img_prompt.cn_img = base64_to_stream(img_prompt.cn_img)
        image = ImagePrompt(cn_img=img_prompt.cn_img,
                            cn_stop=img_prompt.cn_stop,
                            cn_weight=img_prompt.cn_weight,
                            cn_type=img_prompt.cn_type)
        image_prompts_files.append(image)
    while len(image_prompts_files) <= 4:
        image_prompts_files.append(default_image_promt)
    image_upscale_or_vary_req.image_prompts = image_prompts_files

    return call_worker(image_upscale_or_vary_req, accept)


@secure_router.post("/v1/generation/image-inpaint-outpaint", response_model=List[GeneratedImageResult] | AsyncJobResponse, responses=img_generate_responses)
def img_inpaint_or_outpaint(input_image: UploadFile, req: ImgInpaintOrOutpaintRequest = Depends(ImgInpaintOrOutpaintRequest.as_form),
                            accept: str = Header(None),
                            accept_query: str | None = Query(None, alias='accept', description="Parameter to overvide 'Accept' header, 'image/png' for output bytes")):
    if accept_query is not None and len(accept_query) > 0:
        accept = accept_query

    return call_worker(req, accept)


@secure_router.post("/v2/generation/image-inpaint-outpaint", response_model=List[GeneratedImageResult] | AsyncJobResponse, responses=img_generate_responses)
def img_inpaint_or_outpaint_v2(req: ImgInpaintOrOutpaintRequestJson,
                               accept: str = Header(None),
                               accept_query: str | None = Query(None, alias='accept', description="Parameter to overvide 'Accept' header, 'image/png' for output bytes")):
    if accept_query is not None and len(accept_query) > 0:
        accept = accept_query

    req.input_image = base64_to_stream(req.input_image)
    if req.input_mask is not None:
        req.input_mask = base64_to_stream(req.input_mask)
    default_image_promt = ImagePrompt(cn_img=None)
    image_prompts_files: List[ImagePrompt] = []
    for img_prompt in req.image_prompts:
        img_prompt.cn_img = base64_to_stream(img_prompt.cn_img)
        image = ImagePrompt(cn_img=img_prompt.cn_img,
                            cn_stop=img_prompt.cn_stop,
                            cn_weight=img_prompt.cn_weight,
                            cn_type=img_prompt.cn_type)
        image_prompts_files.append(image)
    while len(image_prompts_files) <= 4:
        image_prompts_files.append(default_image_promt)
    req.image_prompts = image_prompts_files

    return call_worker(req, accept)


@secure_router.post("/v1/generation/image-prompt", response_model=List[GeneratedImageResult] | AsyncJobResponse, responses=img_generate_responses)
def img_prompt(cn_img1: Optional[UploadFile] = File(None),
               req: ImgPromptRequest = Depends(ImgPromptRequest.as_form),
               accept: str = Header(None),
               accept_query: str | None = Query(None, alias='accept', description="Parameter to overvide 'Accept' header, 'image/png' for output bytes")):
    if accept_query is not None and len(accept_query) > 0:
        accept = accept_query

    return call_worker(req, accept)


@secure_router.post("/v2/generation/image-prompt", response_model=List[GeneratedImageResult] | AsyncJobResponse, responses=img_generate_responses)
def img_prompt_v2(req: ImgPromptRequestJson,
               accept: str = Header(None),
               accept_query: str | None = Query(None, alias='accept', description="Parameter to overvide 'Accept' header, 'image/png' for output bytes")):
    if accept_query is not None and len(accept_query) > 0:
        accept = accept_query

    if req.prompt == "" and len(req.image_prompts) > 0:
        from extras.wd14tagger import default_interrogator as default_interrogator_anime
        interrogator = default_interrogator_anime
        image = base64_to_stream(req.image_prompts[0].cn_img)
        img = HWC3(read_input_image(image))
        req.prompt = interrogator(img)

    if req.input_image is not None:
        req.input_image = base64_to_stream(req.input_image)
    if req.input_mask is not None:
        req.input_mask = base64_to_stream(req.input_mask)

    default_image_promt = ImagePrompt(cn_img=None)
    image_prompts_files: List[ImagePrompt] = []
    for img_prompt in req.image_prompts:
        img_prompt.cn_img = base64_to_stream(img_prompt.cn_img)
        image = ImagePrompt(cn_img=img_prompt.cn_img,
                            cn_stop=img_prompt.cn_stop,
                            cn_weight=img_prompt.cn_weight,
                            cn_type=img_prompt.cn_type)
        image_prompts_files.append(image)

    while len(image_prompts_files) <= 4:
        image_prompts_files.append(default_image_promt)

    req.image_prompts = image_prompts_files

    return call_worker(req, accept)


@secure_router.post("/v2/generation/image-prompt-upscale", response_model=List[GeneratedImageResult] | AsyncJobResponse, responses=img_generate_responses)
def img_prompt_upscale(image_prompt_req: ImgPromptRequestJson,up_scale_req: ImgUpscaleOrVaryRequestJson, 
               accept: str = Header(None),
               accept_query: str | None = Query(None, alias='accept', description="Parameter to overvide 'Accept' header, 'image/png' for output bytes")):

    #up_scale_req.upscale_value = 1.5

    if up_scale_req.upscale_value<=1:
        return img_prompt_v2(req=image_prompt_req,accept=accept,accept_query=accept_query)
    if accept_query is not None and len(accept_query) > 0:
        accept = accept_query

    if image_prompt_req.input_image is not None:
        image_prompt_req.input_image = base64_to_stream(image_prompt_req.input_image)
    if image_prompt_req.input_mask is not None:
        image_prompt_req.input_mask = base64_to_stream(image_prompt_req.input_mask)

    default_image_promt = ImagePrompt(cn_img=None)
    image_prompts_files: List[ImagePrompt] = []
    for img_prompt in image_prompt_req.image_prompts:
        img_prompt.cn_img = base64_to_stream(img_prompt.cn_img)
        image = ImagePrompt(cn_img=img_prompt.cn_img,
                            cn_stop=img_prompt.cn_stop,
                            cn_weight=img_prompt.cn_weight,
                            cn_type=img_prompt.cn_type)
        image_prompts_files.append(image)

    while len(image_prompts_files) <= 4:
        image_prompts_files.append(default_image_promt)

    image_prompt_req.image_prompts = image_prompts_files

    image_prompt_req.require_base64=True
    step1 = call_worker(image_prompt_req, accept,step2req=True)
    up_scale_req.input_image=step1[0].base64
    
    up_scale_req.input_image = base64_to_stream(up_scale_req.input_image)

    default_image_promt = ImagePrompt(cn_img=None)
    image_prompts_files: List[ImagePrompt] = []
    for img_prompt in up_scale_req.image_prompts:
        img_prompt.cn_img = base64_to_stream(img_prompt.cn_img)
        image = ImagePrompt(cn_img=img_prompt.cn_img,
                            cn_stop=img_prompt.cn_stop,
                            cn_weight=img_prompt.cn_weight,
                            cn_type=img_prompt.cn_type)
        image_prompts_files.append(image)
    while len(image_prompts_files) <= 4:
        image_prompts_files.append(default_image_promt)
    up_scale_req.image_prompts = image_prompts_files
    return call_worker(up_scale_req, accept,priority=True)

@secure_router.post("/v2/generation/image-to-image", response_model=List[GeneratedImageResult] | AsyncJobResponse, responses=img_generate_responses)
def img_to_img_generation(image_prompt_req: ImgPromptRequestJson,up_scale_req: ImgUpscaleOrVaryRequestJson, image_style: Image_Style,
               accept: str = Header(None),
               accept_query: str | None = Query(None, alias='accept', description="Parameter to overvide 'Accept' header, 'image/png' for output bytes")):
    
    if (image_style.id == -1) or (image_style.id>=len(image_styles)):
        image_style.id = random.randint(0, len(image_styles)-1)
    
    style = image_styles[image_style.id]
    image_prompt_req = overwrite_style_params(image_prompt_req, style, image_style.id)
    if image_prompt_req.advanced_params.overwrite_step != 50:
        up_scale_req.upscale_value = 1.5
    up_scale_req = overwrite_style_params(up_scale_req, style, image_style.id, upscale=True)

    image_prompt_req.image_style = image_style.id
    up_scale_req.image_style = image_style.id

    if up_scale_req.upscale_value<=1:
        return img_prompt_v2(req=image_prompt_req,accept=accept,accept_query=accept_query)
    if accept_query is not None and len(accept_query) > 0:
        accept = accept_query

    if image_prompt_req.prompt == "" and len(image_prompt_req.image_prompts) > 0:
        from extras.wd14tagger import default_interrogator as default_interrogator_anime
        interrogator = default_interrogator_anime
        image = base64_to_stream(image_prompt_req.image_prompts[0].cn_img)
        img = HWC3(read_input_image(image))
        result = interrogator(img)
        image_prompt_req.prompt = result
        up_scale_req.prompt = result

    if image_prompt_req.input_image is not None:
        image_prompt_req.input_image = base64_to_stream(image_prompt_req.input_image)
    if image_prompt_req.input_mask is not None:
        image_prompt_req.input_mask = base64_to_stream(image_prompt_req.input_mask)

    default_image_promt = ImagePrompt(cn_img=None)
    image_prompts_files: List[ImagePrompt] = []
    for img_prompt in image_prompt_req.image_prompts:
        img_prompt.cn_img = base64_to_stream(img_prompt.cn_img)
        image = ImagePrompt(cn_img=img_prompt.cn_img,
                            cn_stop=img_prompt.cn_stop,
                            cn_weight=img_prompt.cn_weight,
                            cn_type=img_prompt.cn_type)
        image_prompts_files.append(image)

    while len(image_prompts_files) <= 4:
        image_prompts_files.append(default_image_promt)

    image_prompt_req.image_prompts = image_prompts_files

    image_prompt_req.require_base64=True
    step1 = call_worker(image_prompt_req, accept,step2req=True)
    up_scale_req.input_image=step1[0].base64
    
    up_scale_req.input_image = base64_to_stream(up_scale_req.input_image)

    default_image_promt = ImagePrompt(cn_img=None)
    image_prompts_files: List[ImagePrompt] = []
    for img_prompt in up_scale_req.image_prompts:
        img_prompt.cn_img = base64_to_stream(img_prompt.cn_img)
        image = ImagePrompt(cn_img=img_prompt.cn_img,
                            cn_stop=img_prompt.cn_stop,
                            cn_weight=img_prompt.cn_weight,
                            cn_type=img_prompt.cn_type)
        image_prompts_files.append(image)
    while len(image_prompts_files) <= 4:
        image_prompts_files.append(default_image_promt)
    up_scale_req.image_prompts = image_prompts_files
    return call_worker(up_scale_req, accept,priority=True)


@secure_router.get("/v1/generation/query-job", response_model=AsyncJobResponse, description="Query async generation job")
def query_job(req: QueryJobRequest = Depends()):
    queue_task = worker_queue.get_task(req.job_id, True)
    if queue_task is None:
        result = AsyncJobResponse(job_id="",
                                 job_type=TaskType.not_found,
                                 job_stage=AsyncJobStage.error,
                                 job_progress=0,
                                 job_status="Job not found")
        content = result.model_dump_json()
        return Response(content=content, media_type='application/json', status_code=404)
    return generate_async_output(queue_task, req.require_step_preview)


@secure_router.get("/v1/generation/job-queue", response_model=JobQueueInfo, description="Query job queue info")
def job_queue():
    return JobQueueInfo(running_size=len(worker_queue.queue), finished_size=len(worker_queue.history), last_job_id=worker_queue.last_job_id)


@secure_router.get("/v1/generation/job-history", response_model=JobHistoryResponse | dict, description="Query historical job data")
def get_history(job_id: str = None, page: int = 0, page_size: int = 20):
    # Fetch and return the historical tasks
    queue = [JobHistoryInfo(job_id=item.job_id, is_finished=item.is_finished) for item in worker_queue.queue]
    if not args.persistent:
        history = [JobHistoryInfo(job_id=item.job_id, is_finished=item.is_finished) for item in worker_queue.history]
        return JobHistoryResponse(history=history, queue=queue)
    else:
        from fooocusapi.sql_client import query_history
        history = query_history(task_id=job_id, page=page, page_size=page_size)
        return {
            "history": history,
            "queue": queue
        }


@secure_router.post("/v1/generation/stop", response_model=StopResponse, description="Job stoping")
def stop():
    stop_worker()
    return StopResponse(msg="success")


@secure_router.post("/v1/tools/describe-image", response_model=DescribeImageResponse)
def describe_image(image: UploadFile, type: DescribeImageType = Query(DescribeImageType.photo, description="Image type, 'Photo' or 'Anime'")):
    if type == DescribeImageType.photo:
        from extras.interrogate import default_interrogator as default_interrogator_photo
        interrogator = default_interrogator_photo
    else:
        from extras.wd14tagger import default_interrogator as default_interrogator_anime
        interrogator = default_interrogator_anime
    img = HWC3(read_input_image(image))
    result = interrogator(img)
    return DescribeImageResponse(describe=result)


@secure_router.get("/v1/engines/all-models", response_model=AllModelNamesResponse, description="Get all filenames of base model and lora")
def all_models():
    import modules.config as config
    return AllModelNamesResponse(model_filenames=config.model_filenames, lora_filenames=config.lora_filenames)


@secure_router.post("/v1/engines/refresh-models", response_model=AllModelNamesResponse, description="Refresh local files and get all filenames of base model and lora")
def refresh_models():
    import modules.config as config
    config.update_all_model_names()
    return AllModelNamesResponse(model_filenames=config.model_filenames, lora_filenames=config.lora_filenames)


@secure_router.get("/v1/engines/styles", response_model=List[str], description="Get all legal Fooocus styles")
def all_styles():
    from modules.sdxl_styles import legal_style_names
    return legal_style_names


@secure_router.post("/GenerateHeadMask",response_model=dict,description="the dir of the headmask")
def GenerateHeadMask(image: UploadFile, threshold = 0.1, blur = 1.0, dilation_factor = 1):

    prompt = 'head'
    #threshold=0.1
    #blur=1.0
    #dilation_factor=1

    # Decode the base64 image
    image_data = read_input_image(image)
    image_np = np.array(image_data, dtype=np.uint8)
    
    i = Image.fromarray(image_np,mode="RGB")
    input_prc = processor(text=prompt, images=i, padding="max_length", return_tensors="pt")
    with torch.no_grad():
        outputs = model(**input_prc)
    tensor = torch.sigmoid(outputs[0])

    # Apply a threshold to the original tensor to cut off low values
    tensor_thresholded = torch.where(tensor > threshold, tensor, torch.tensor(0, dtype=torch.float))

    # Apply Gaussian blur to the thresholded tensor
    tensor_smoothed = gaussian_filter(tensor_thresholded.numpy(), sigma=blur)
    tensor_smoothed = torch.from_numpy(tensor_smoothed)

    # Normalize the smoothed tensor to [0, 1]
    mask_normalized = (tensor_smoothed - tensor_smoothed.min()) / (tensor_smoothed.max() - tensor_smoothed.min())

    # Dilate the normalized mask
    mask_dilated = dilate_mask(mask_normalized, dilation_factor)

    # Convert the mask to a heatmap and a binary mask
    binary_mask = apply_colormap(mask_dilated, cm.Greys_r)

    # Overlay the heatmap and binary mask on the original image
    dimensions = (image_np.shape[1], image_np.shape[0])
    binary_mask_resized = resize_image(binary_mask, dimensions)

    grey = cv2.cvtColor(binary_mask_resized,cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(grey, 20, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    bounding_boxes = []
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        # Increase the bounding box margin by 100px, ensuring it doesn't exceed image dimensions
        #x = max(x - 100, 0)
        #y = max(y - 100, 0)
        #w = min(w + 200, image_np.shape[1] - x)
        #h = min(h + 200, image_np.shape[0] - y)
        bounding_boxes.append({'x': x, 'y': y, 'w': w, 'h': h})

    # Save and encode the binary mask to base64 for output
    #timestamp = int(time.time())
    #buffered = BytesIO()
    #Image.fromarray(binary_mask_resized).save(buffered, format="PNG")
    #buffered.seek(0)
    #img_base64 = base64.b64encode(buffered.getvalue()).decode()
    
    #ans = {"image_base64": img_base64, 'bounding_boxes': bounding_boxes}
    ans = {'bounding_boxes': bounding_boxes}
    return ans



# 当前文件的路径
current_file_path = __file__
# 当前文件所在的目录
current_directory = os.path.dirname(current_file_path)

# 当前目录的上一级目录
parent_directory = os.path.dirname(current_directory)

processor = CLIPSegProcessor.from_pretrained("{}".format(parent_directory) + "/models/clipseg/models--CIDAS--clipseg-rd64-refined/snapshots/583b388deb98a04feb3e1f816dcdb8f3062ee205")
model = CLIPSegForImageSegmentation.from_pretrained("{}".format(parent_directory) + "/models/clipseg/models--CIDAS--clipseg-rd64-refined/snapshots/583b388deb98a04feb3e1f816dcdb8f3062ee205")




app.mount("/files", StaticFiles(directory=file_utils.output_dir), name="files")

app.include_router(secure_router)

def start_app(args):
    file_utils.static_serve_base_url = args.base_url + "/files/"
    uvicorn.run("fooocusapi.api:app", host=args.host,
                port=args.port, log_level=args.log_level)


