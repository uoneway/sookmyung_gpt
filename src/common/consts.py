from pathlib import Path

SERVICE_TITLE = "myproject"

# Path
PROJECT_DIR = Path(__file__).parent.parent.parent
ENV_PATH = PROJECT_DIR / ".env"
ENV_DEV_PATH = PROJECT_DIR / ".env.dev"
RESULT_DIR = PROJECT_DIR / "db/result"
PROMPT_DIR = PROJECT_DIR / "src/prompt"

# Model
LLM_MODEL1: str = "gpt-3.5-turbo"  # -16k
LLM_MODEL1_MAX_NUM_TOKEN: int = 4000  # 4,097
LLM_MODEL2: str = "gpt-3.5-turbo-16k"
LLM_MODEL2_MAX_NUM_TOKEN: int = 16000  # 16,385
LLM_TEMPERATURE: int = 0
