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

# Model
LLM_TEMPERATURE: int = 0
# {"name": "gpt-4-32k", "max_tokens": 32768}, {"name": "gpt-3.5-turbo-16k", "max_tokens": 16385}]
MODEL_TYPE_INFOS = [{"name": "gpt-4", "max_tokens": 8192}]
MAX_OUTPUT_TOKENS = 800
OPENAI_RETRIES = 3

# Input
ALLOWED_EXTENSIONS = [".hwp", ".docx", ".pdf"]
ALLOWED_EXTENSIONS_WITH_ZIP = ALLOWED_EXTENSIONS + [".zip"]
