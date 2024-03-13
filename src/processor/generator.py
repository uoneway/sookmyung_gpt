import json
from datetime import datetime
from typing import Optional

import openai
import streamlit as st
import tomli
from jinja2 import Environment
from openai.error import APIError, RateLimitError, Timeout, TryAgain
from retry import retry

from src import logger
from src.common.consts import LLM_TEMPERATURE, MAX_OUTPUT_TOKENS, MODEL_TYPE_INFOS, OPENAI_RETRIES, PROMPT_DIR, TO_JSON
from src.common.models import reset_category_strenum, reset_prompt_per_category_dict
from src.utils.io import load_json
from src.utils.llm import num_tokens_from_messages

# Read .toml files and build the category_option_dict
if "prompt_per_category_dict" not in st.session_state:
    reset_prompt_per_category_dict()

if "Category" not in st.session_state:
    reset_category_strenum()

Category = st.session_state["Category"]


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
                    f"The length of prompts[1]['content'], '{prompts[1]['content']}' is too short. "
                    + "Please check the input."
                )

    return model_name, prompts


class Generator:
    prompt_templates_path = PROMPT_DIR / "prompt_template.toml"
    category_dir = PROMPT_DIR / "category"

    model_type = "gpt-4"
    temperature = 0.0
    stream = False
    to_json = True
    max_output_tokens = 2000

    with prompt_templates_path.open("rb") as f:
        prompt_templates = tomli.load(f)["prompt"]

    def __init__(self) -> None:
        pass

    @staticmethod
    def postprocessor(text: str) -> str:
        return text

    def construct_prompt(
        self,
        category: Category,
        input_text: str,
        **kwargs,
    ) -> list[dict]:
        # By category, construct criteria str and output_format str
        criteria_dict = st.session_state["prompt_per_category_dict"][category]

        criteria_list_with_num = []
        output_format_dict = {}
        for main_idx, crit_dict in enumerate(criteria_dict["criteria"], start=1):
            criteria_list_with_num.append(f"{main_idx}. {crit_dict['title_ko']}({crit_dict['title_en'].capitalize()})")
            criteria_list_with_num.extend(
                [
                    f"  {main_idx}_{sub_idx}. "
                    + f"{sub_crit_dict['description']} ({sub_crit_dict['scale_min']}~{sub_crit_dict['scale_max']}점)"
                    for sub_idx, sub_crit_dict in enumerate(crit_dict["sub_criteria"], start=1)
                ]
            )

            output_format_dict[crit_dict["title_en"]] = {
                "score": [f"score_{main_idx}_{sub_idx+1}" for sub_idx in range(len(crit_dict["sub_criteria"]))],
                # "score": [
                #     f"{main_idx}_{sub_idx+1}_score"
                #     for sub_idx, sub_crit_dict in enumerate(crit_dict["sub_criteria"], start=1)
                # ],
                "description": "",
            }
        criteria_str = "\n".join(criteria_list_with_num)
        output_format_str = json.dumps(output_format_dict)  # indent=4

        # Construct prompt
        # example 값이 있는 경우에만 example 및 해당 타이틀이 들어갈 수 있도록 수정
        example = f"Scoring examples:\n{criteria_dict['example']}" if criteria_dict.get("example") else ""

        kwargs.update(
            category=criteria_dict["category_name_ko"],
            criteria=criteria_str,
            example=example,
            input_text=input_text,
            output_format=output_format_str,
        )
        prompts = []
        for p in self.prompt_templates:
            content = Environment().from_string(p["content"]).render(**kwargs)
            if content:
                prompts.append({"role": p["role"], "content": content.strip()})

        return prompts

    async def agenerate(self, category: Category, input_text: str):
        def serialize_score_info(score_info: dict[str, dict]) -> dict[str, int | str]:
            """
            Input:
                data = {
                    'content': {'score': [1, 2, 3, 4, 5, 6], 'description': ''},
                    'structure': {'score': [7, 8, 9, 10], 'description': ''},
                    'grammar': {'score': [11, 12, 13], 'description': ''}
                }
            """
            result = {}
            total = 0
            for key, value in score_info.items():
                prefix = key.lower()
                scores = value["score"]
                description = value["description"]
                sub_total = sum(scores)
                for i, score in enumerate(scores, start=1):
                    result[f"{prefix}_{i}"] = score
                result[f"{prefix}_total"] = sub_total
                result[f"{prefix}_descript"] = description
                total += sub_total

            result["Total"] = total
            return result

        def response_metainfo_str(usage_response: dict, start_datetime: datetime):
            entry = {
                "datetime": datetime.now().isoformat(),
                "prompt": usage_response["prompt_tokens"],
                "completion": usage_response["completion_tokens"],
                "total": usage_response["total_tokens"],
                "response_time(s)": (datetime.now() - start_datetime).total_seconds(),
            }
            return json.dumps(entry)

        prompts = self.construct_prompt(category=category, input_text=input_text)
        logger.debug(prompts)
        model_name, _ = get_model_name_adapt_to_prompt_len(prompts=prompts)
        t = datetime.now()
        resp = await achat_completion(
            model=model_name,
            messages=prompts,
            to_json=TO_JSON,
            temperature=LLM_TEMPERATURE,
            max_tokens=MAX_OUTPUT_TOKENS,
        )
        try:
            score_info = load_json(resp["choices"][0]["message"]["content"])
            score_info_serialized = serialize_score_info(score_info)
        except Exception as e:
            logger.exception(f"LLM response is not as expected form: {e.__class__.__name__}: {e}\n{resp}")

        token_usage = resp["usage"]

        logger.info(f"LLM Response Metainfo: {response_metainfo_str(token_usage, t)}")
        prompts_str = "\n\n".join([f"{p['role']}: {p['content']}" for p in prompts])
        return {
            "score_info": score_info_serialized,
            "model_name": model_name,
            "token_usage": token_usage,
            "prompts_str": prompts_str,
        }


@retry(
    exceptions=(APIError, Timeout, TryAgain, RateLimitError),
    tries=OPENAI_RETRIES,
    delay=2,
    backoff=2,
    jitter=(1, 3),
    logger=logger,
)
async def achat_completion(model, messages: list[str], to_json=False, temperature=0.0, max_tokens=None, stream=False):
    response_format = {"type": "json_object" if to_json else "text"}
    try:
        return await openai.ChatCompletion.acreate(
            model=model,
            messages=messages,
            response_format=response_format,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=stream,
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
