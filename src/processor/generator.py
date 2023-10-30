import json
from datetime import datetime
from typing import Optional

import openai
import tomli
from jinja2 import Environment
from openai.error import APIError, RateLimitError, Timeout, TryAgain
from retry import retry

from src import logger
from src.common.consts import LLM_TEMPERATURE, MAX_OUTPUT_TOKENS, MODEL_TYPE_INFOS, OPENAI_RETRIES, PROMPT_DIR
from src.utils.llm import num_tokens_from_messages

prompt_path = PROMPT_DIR / "prompt.toml"
with prompt_path.open("rb") as f:
    prompt_dict = tomli.load(f)


def get_model_name_adapt_to_prompt_len(prompts: list[dict], reduce_prompt_idx: Optional[int] = None):
    model_name = None
    while model_name is None:
        for model_info in MODEL_TYPE_INFOS:
            num_tokens = num_tokens_from_messages(prompts)
            total_num_tokens = num_tokens + MAX_OUTPUT_TOKENS

            if total_num_tokens <= model_info["max_tokens"]:
                model_name = model_info["name"]
                break
        if model_name is None:
            if reduce_prompt_idx is None:
                raise ValueError(
                    f"Input({total_num_tokens} tokens) is too large. Please reduce the number of tokens in the prompt."
                )
            else:
                logger.warning(f"total_num_tokens {total_num_tokens} is too large.")

            num_chars_to_remove = int((total_num_tokens - model_info["max_tokens"]) * 1.5)
            assert num_chars_to_remove > 0, f"Reduce the PRESS RELEASEs prompt by {num_chars_to_remove} chars."
            prompts[reduce_prompt_idx]["content"] = prompts[reduce_prompt_idx]["content"][:-num_chars_to_remove]
            if len(prompts[1]["content"]) < 5:
                raise ValueError(
                    f"The length of prompts[1]['content'], '{prompts[1]['content']}'  is too short. Please check the input."
                )

    return model_name, prompts


def construct_prompt(
    input_text: str,
    **kwargs,
) -> list[dict]:
    kwargs.update(input_text=input_text)

    prompts = []
    for k, p in prompt_dict.items():
        if k.startswith("prompt"):
            content = Environment().from_string(p["content"]).render(**kwargs)
            if content:
                prompts.append({"role": p["role"], "content": content})
    return prompts


async def request_llm(input_text: str):
    def response_metainfo_str(usage_response: dict, start_datetime: datetime):
        entry = {
            "datetime": datetime.now().isoformat(),
            "prompt": usage_response["prompt_tokens"],
            "completion": usage_response["completion_tokens"],
            "total": usage_response["total_tokens"],
            "response_time(s)": (datetime.now() - start_datetime).total_seconds(),
        }
        return json.dumps(entry)

    prompts = construct_prompt(input_text=input_text)

    model_name, _ = get_model_name_adapt_to_prompt_len(prompts=prompts)
    t = datetime.now()
    resp = await achat_completion(
        model=model_name,
        messages=prompts,
        temperature=LLM_TEMPERATURE,
        max_tokens=MAX_OUTPUT_TOKENS,
    )
    content = resp["choices"][0]["message"]["content"]
    token_usage = resp["usage"]

    logger.info(f"LLM Response: {resp}")
    logger.info(f"Metainfo of LLM Response : {response_metainfo_str(token_usage, t)}")
    prompts_str = "\n\n".join([f"{p['role']}: {p['content']}" for p in prompts])
    return content, model_name, token_usage, prompts_str


@retry(
    exceptions=(APIError, Timeout, TryAgain, RateLimitError), tries=OPENAI_RETRIES, delay=2, backoff=2, jitter=(1, 3)
)
async def achat_completion(model, messages: list[str], temperature=0.0, max_tokens=None, stream=False):
    try:
        return await openai.ChatCompletion.acreate(
            model=model, messages=messages, temperature=temperature, max_tokens=max_tokens, stream=stream
        )
    except (APIError, Timeout, TryAgain) as e:
        logger.error("Error during OpenAI inference: ", e)
        raise e
    except RateLimitError as e:
        logger.error("Rate limit error during OpenAI inference: ", e)  # TODO: how to handle ratelimiterror?
        raise e
    except Exception as e:
        logger.error("Unexpected error in OpenAI inference", e)
        raise e
