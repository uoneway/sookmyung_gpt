import os
from pathlib import Path

import aiofiles
from fastapi import APIRouter, BackgroundTasks, Request, UploadFile

from src import logger
from src.common.consts import RESULT_DIR
from src.utils.io import get_current_timestamp, unzip_as_dict

router = APIRouter()


@router.post("/upload")
async def upload_dialogue(
    file: UploadFile,
    request: Request,
    background_tasks: BackgroundTasks,
):
    content = await file.read()
    if not content:
        return False
    filename = Path(file.filename)

    if filename.suffix == ".zip":
        file_info = unzip_as_dict(content)
    else:
        file_info = {str(filename): content}

    current_timestamp = get_current_timestamp(unit="µs")
    tgt_dir = RESULT_DIR / str(int(current_timestamp))
    os.makedirs(tgt_dir, exist_ok=True)

    results = []
    for filename, content in file_info.items():
        src_path = tgt_dir / filename
        async with aiofiles.open(src_path, "wb") as f:
            await f.write(content)
            logger.info(f"File uploaded to {src_path}")

        background_tasks.add_task(run, src_path=src_path)

    return True


async def run(src_path):
    return "Success"
