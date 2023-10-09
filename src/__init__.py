import logging
import os

import openai
from dotenv import load_dotenv

from src.common.consts import ENV_DEV_PATH, ENV_PATH, SERVICE_TITLE

logger = logging.getLogger(SERVICE_TITLE)

load_dotenv(dotenv_path=ENV_PATH)
if ENV_DEV_PATH.exists():
    load_dotenv(dotenv_path=ENV_DEV_PATH, override=True)

assert os.getenv("PHASE") is not None, "Set PHASE enviroment value"
PHASE = os.getenv("PHASE")
logger.info(f"PHASE: {PHASE}")
print(f"PHASE: {PHASE}")
if PHASE == "dev":
    logger.setLevel(logging.DEBUG)

assert os.getenv("OPENAI_API_KEY") is not None, "Set OPENAI_API_KEY enviroment value"
openai.api_key = os.getenv("OPENAI_API_KEY")
