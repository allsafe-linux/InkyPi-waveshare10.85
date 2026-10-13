from plugins.base_plugin.base_plugin import BasePlugin
from utils.app_utils import resolve_path
from openai import OpenAI
from PIL import Image, ImageDraw, ImageFont
from utils.image_utils import resize_image
from utils.llm_providers import (
    get_provider_config, get_providers_for_ui, get_models_for_provider,
    build_openai_client, get_env_key_for_provider, PROVIDER_ORDER
)
from io import BytesIO
from datetime import datetime
import json
import logging
import textwrap

logger = logging.getLogger(__name__)

DEFAULT_PROVIDER = "minimax"


class AIText(BasePlugin):
    def generate_settings_template(self):
        template_params = super().generate_settings_template()
        provider_id = template_params.get("provider", DEFAULT_PROVIDER)
        cfg = get_provider_config(provider_id)
        template_params["providers"] = get_providers_for_ui()
        template_params["text_models"] = get_models_for_provider(provider_id, "text")
        template_params["default_provider"] = DEFAULT_PROVIDER
        # All models keyed by provider, for JS to switch on change
        all_text_models = {pid: get_models_for_provider(pid, "text") for pid in PROVIDER_ORDER}
        template_params["all_text_models_json"] = json.dumps(all_text_models)
        # API key info (env var) - dynamic per provider
        if cfg:
            template_params["api_key"] = {
                "required": True,
                "service": cfg["display_name"],
                "expected_key": cfg["env_key"],
            }
        else:
            template_params["api_key"] = {
                "required": True,
                "service": "LLM",
                "expected_key": "LLM_API_KEY",
            }
        template_params["style_settings"] = True
        return template_params

    def generate_image(self, settings, device_config):
        provider_id = settings.get("provider", DEFAULT_PROVIDER)
        cfg = get_provider_config(provider_id)
        if not cfg:
            raise RuntimeError(f"Unknown provider: {provider_id}")

        # API key: from env var (custom override or default)
        env_key = (settings.get("apiKeyEnv") or "").strip() or cfg["env_key"]
        api_key = device_config.load_env_key(env_key)
        if not api_key:
            raise RuntimeError(
                f"{cfg['display_name']} API Key not configured. "
                f"Set environment variable: {env_key}"
            )

        title = settings.get("title")
        text_model = settings.get("textModel")
        if not text_model:
            # Default to first model in provider's list
            text_model = cfg["text_models"][0] if cfg["text_models"] else None
        if not text_model:
            raise RuntimeError(f"Text Model is required for {cfg['display_name']}.")
        if text_model not in cfg["text_models"]:
            # Fallback to first if user-provided model is invalid
            text_model = cfg["text_models"][0]

        text_prompt = settings.get("textPrompt", "")
        if not text_prompt.strip():
            raise RuntimeError("Text Prompt is required.")

        # Optional custom base URL override
        custom_base_url = (settings.get("customBaseUrl") or "").strip() or None

        try:
            ai_client = build_openai_client(api_key, provider_id, custom_base_url)
            prompt_response = AIText.fetch_text_prompt(ai_client, text_model, text_prompt)
        except Exception as e:
            logger.error(f"Failed to make {cfg['display_name']} request: {str(e)}")
            raise RuntimeError(f"{cfg['display_name']} request failure, please check logs.")

        dimensions = device_config.get_resolution()
        if device_config.get_config("orientation") == "vertical":
            dimensions = dimensions[::-1]

        image_template_params = {
            "title": title,
            "content": prompt_response,
            "plugin_settings": settings
        }

        image = self.render_image(dimensions, "ai_text.html", "ai_text.css", image_template_params)
        return image

    @staticmethod
    def fetch_text_prompt(ai_client, model, text_prompt):
        logger.info(f"Getting random text prompt from input {text_prompt}, model: {model}")

        system_content = (
            "You are a highly intelligent text generation assistant. Generate concise, "
            "relevant, and accurate responses tailored to the user\'s input. The response "
            "should be 70 words or less. "
            "IMPORTANT: Do not rephrase, reword, or provide an introduction. Respond directly "
            "to the request without adding explanations or extra context. "
            "IMPORTANT: If the response naturally requires a newline for formatting, provide "
            "the \'\\n\' newline character explicitly for every new line. For regular sentences "
            "or paragraphs do not provide the new line character. "
            f"For context, today is {datetime.today().strftime('%Y-%m-%d')}"
        )
        user_content = text_prompt

        response = ai_client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_content},
            ],
            temperature=1
        )
        prompt = response.choices[0].message.content.strip()
        logger.info(f"Generated random text prompt: {prompt}")
        return prompt
