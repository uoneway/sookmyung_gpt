import openai

from src import logger
from src.common.consts import LLM_TEMPERATURE, PROMPT_DIR
from src.utils.io import load_obj
from src.utils.llm import num_tokens_from_messages

system_prompt = load_obj(PROMPT_DIR / "system_prompt.txt")
user_prompt = load_obj(PROMPT_DIR / "user_prompt.txt")
base_messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]


async def reqeust_llm(input_text: str, base_messages: list[dict[str, str]] = base_messages):
    messages = base_messages
    messages.append({"role": "user", "content": f"## REPORT:\n{input_text}"})

    num_tokens = num_tokens_from_messages(messages)
    # model_name = "gpt-4" if num_tokens < 8100 else "gpt-4-32k"  # 8,192
    model_name = "gpt-3.5-turbo" if num_tokens < 4000 else "gpt-3.5-turbo-16k"
    resp = await openai.ChatCompletion.acreate(
        model=model_name,
        messages=messages,
        temperature=LLM_TEMPERATURE,
    )
    logger.debug(f"LLM Response: {resp}")
    content = resp["choices"][0]["message"]["content"]
    usage = resp["usage"]

    return {"content": content, "usage": usage}
