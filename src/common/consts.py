from pathlib import Path

SERVICE_TITLE = "myproject"

# Path
PROJECT_DIR = Path(__file__).parent.parent.parent
ENV_PATH = PROJECT_DIR / ".env"
ENV_DEV_PATH = PROJECT_DIR / ".env.dev"
RESULT_DIR = PROJECT_DIR / "db/result"
PROMPT_DIR = PROJECT_DIR / "src/prompt"
