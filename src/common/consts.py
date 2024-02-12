from pathlib import Path

SERVICE_TITLE = "sookmyung-ai-cali"

# Path
PROJECT_DIR = Path(__file__).parent.parent.parent
ENV_PATH = PROJECT_DIR / ".env"
ENV_DEV_PATH = PROJECT_DIR / ".env.dev"
LOG_DIR = "./logs"
LOG_CONFIG_PATH = PROJECT_DIR / "log_config.yml"
RESULT_DIR = PROJECT_DIR / "db/result"
PROMPT_DIR = PROJECT_DIR / "src/prompt"
PROMPT_PER_CATEGORY_DIR = PROMPT_DIR / "category"
PROMPT_ARCHIVE_DIR = PROMPT_PER_CATEGORY_DIR / "archive"

# Model
TO_JSON = True
LLM_TEMPERATURE: int = 0
# {"name": "gpt-4-32k", "max_tokens": 32768}, {"name": "gpt-3.5-turbo-16k", "max_tokens": 16385}]
MODEL_TYPE_INFOS = [{"name": "gpt-4-1106-preview", "max_tokens": 128000}]
MAX_OUTPUT_TOKENS = 1000
OPENAI_RETRIES = 3

# Input
ALLOWED_EXTENSIONS = [".hwp", ".docx", ".pdf"]
ALLOWED_EXTENSIONS_WITH_ZIP = ALLOWED_EXTENSIONS + [".zip"]
MAX_CHAR_LEN_PER_FILE = 40000

# Output
OUTPUT_DTYPE_DICT = [
    {
        "STU ID": "str",
    },
    {
        "원문파일명": "str",
        "원문 내용": "str",
        "사용 모델명": "str",
        "비고": "str",
    },
]

# google drive
base_folder_id = "1EHaZ9kIAL2k64l40-7sya8yIrvgvxhNj"
