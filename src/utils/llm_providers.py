"""LLM provider registry for AI plugins.
Single source of truth for base_url, model list, env key name.
Used by both ai_text and ai_image plugins.

To add a new provider: add entry to LLM_PROVIDERS and add id to PROVIDER_ORDER.
"""
import logging
import requests
from openai import OpenAI

logger = logging.getLogger(__name__)


# Order matters: this is the order shown in the UI dropdown
PROVIDER_ORDER = [
    "minimax",
    "deepseek",
    "qwen",
    "glm",
    "kimi",
    "doubao",
    "hunyuan",
    "wenxin",
]


LLM_PROVIDERS = {
    "minimax": {
        "display_name": "Minimax M3",
        "base_url": "https://api.minimax.chat/v1",  # PATCH: verify URL
        "text_models": ["MiniMax-Text-01", "MiniMax-M3"],
        "image_models": [],
        "env_key": "MINIMAX_API_KEY",
    },
    "deepseek": {
        "display_name": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "text_models": ["deepseek-chat", "deepseek-reasoner"],
        "image_models": [],
        "env_key": "DEEPSEEK_API_KEY",
    },
    "qwen": {
        "display_name": "Qwen (DashScope)",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "text_models": ["qwen-max", "qwen-plus", "qwen-turbo", "qwen-long"],
        "image_models": ["qwen-image-plus", "qwen-image"],
        "env_key": "DASHSCOPE_API_KEY",
    },
    "glm": {
        "display_name": "GLM (Zhipu)",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "text_models": ["glm-4-plus", "glm-4-air", "glm-4-flash"],
        "image_models": ["cogview-3"],
        "env_key": "ZHIPUAI_API_KEY",
    },
    "kimi": {
        "display_name": "Kimi (Moonshot)",
        "base_url": "https://api.moonshot.cn/v1",
        "text_models": ["moonshot-v1-128k", "moonshot-v1-32k", "moonshot-v1-8k"],
        "image_models": [],
        "env_key": "MOONSHOT_API_KEY",
    },
    "doubao": {
        "display_name": "Doubao (Volcengine)",
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "text_models": ["doubao-pro-32k", "doubao-pro-4k", "doubao-lite-32k"],
        "image_models": [],
        "env_key": "VOLCENGINE_API_KEY",
    },
    "hunyuan": {
        "display_name": "Hunyuan (Tencent)",
        "base_url": "https://hunyuan.tencent.com",
        "text_models": ["hunyuan-pro", "hunyuan-standard"],
        "image_models": [],
        "env_key": "HUNYUAN_API_KEY",
    },
    "wenxin": {
        "display_name": "Wenxin (Baidu)",
        "base_url": "https://aip.baidubce.com",
        "text_models": ["ernie-4.0", "ernie-3.5", "ernie-speed"],
        "image_models": [],
        "env_key": "QIANFAN_ACCESS_KEY",
    },
}


def get_provider_config(provider_id):
    """Returns provider config dict, or None if provider not found."""
    return LLM_PROVIDERS.get(provider_id)


def get_providers_for_ui():
    """Returns ordered list of (id, display_name) for UI dropdown."""
    return [(pid, LLM_PROVIDERS[pid]["display_name"]) for pid in PROVIDER_ORDER]


def get_models_for_provider(provider_id, model_type="text"):
    """Returns list of model names for a provider and type ('text' or 'image')."""
    cfg = get_provider_config(provider_id)
    if not cfg:
        return []
    key = f"{model_type}_models"
    return cfg.get(key, [])


def build_openai_client(api_key, provider_id, custom_base_url=None):
    """
    Build an OpenAI-compatible client for the given provider.
    custom_base_url: optional override for the provider's default base_url.
    Most Chinese providers (DeepSeek, Qwen, GLM, Kimi, Doubao) use the
    OpenAI protocol so the openai Python client works with just a different
    base_url.
    """
    cfg = get_provider_config(provider_id)
    if not cfg:
        raise ValueError(f"Unknown provider: {provider_id}")

    base_url = custom_base_url or cfg["base_url"]
    logger.info(f"Building OpenAI client for provider={provider_id} base_url={base_url}")
    return OpenAI(api_key=api_key, base_url=base_url)


def get_env_key_for_provider(provider_id):
    """Returns the default env var name for the provider's API key."""
    cfg = get_provider_config(provider_id)
    if not cfg:
        return None
    return cfg.get("env_key")
