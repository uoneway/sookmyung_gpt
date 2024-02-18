import logging
import logging.config
import os
from datetime import datetime

import openai
import streamlit as st
import yaml
from dotenv import load_dotenv

from src.common.consts import (
    ENV_DEV_PATH,
    ENV_PATH,
    LOG_CONFIG_PATH,
    LOG_DIR,
    SERVER_START_DATETIME_FILE,
    SERVICE_TITLE,
)

# 로깅 설정 로드
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)
with open(LOG_CONFIG_PATH, "r") as f:
    config = yaml.safe_load(f.read())
    logging.config.dictConfig(config)

logger = logging.getLogger(SERVICE_TITLE)

load_dotenv(dotenv_path=ENV_PATH)
if ENV_DEV_PATH.exists():
    load_dotenv(dotenv_path=ENV_DEV_PATH, override=True)

assert os.getenv("PHASE") is not None, "Set PHASE enviroment value"
PHASE = os.getenv("PHASE")
logger.info(f"PHASE: {PHASE}")
if PHASE == "dev":
    logger.setLevel(logging.DEBUG)

assert os.getenv("OPENAI_API_KEY") is not None, "Set OPENAI_API_KEY enviroment value"
openai.api_key = os.getenv("OPENAI_API_KEY")

GOOGLE_DRIVE_SERVICE_SECRETS = st.secrets["google_drive_service_secrets"]

date_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
if not os.path.exists(SERVER_START_DATETIME_FILE):
    with open(SERVER_START_DATETIME_FILE, "w") as file:
        file.write(date_str)
        logger.info(f"Server start datetime: {date_str}")
