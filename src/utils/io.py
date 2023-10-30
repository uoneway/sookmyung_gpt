import asyncio
import io
import json
import os
import pickle
import re
import sys
import uuid
import zipfile
from datetime import datetime, time
from pathlib import Path
from typing import Collection, Optional, Union

import aiofiles
import aiohttp
import orjson
import requests

from src import logger

# FILE IO #


def load_obj(
    file_path: Union[str, Path],
    file_type: str = None,
    encoding: str = "utf-8",
    as_list: bool = False,
    verbose: bool = False,
):
    """file_type과 encoding이 주어지지 않아도 해당 file_path에 맞는 적절한 값을 찾아 파일을 불러와주는 함수
    - 주어진 encoding 값으로 load 시 encoding 관련 오류가 발생했다면, 적절한 encoding을 찾아 재시도함
    """

    def _load_obj(file_path, encoding):
        # encoding = detect_encoding(file_path) if use_encoding_detector else "utf-8"

        if file_type in [".pickle", ".pkl", ".p"]:
            mode = "rb"
            with open(file_path, mode) as f:
                result = pickle.load(f)

        else:
            mode = "r"
            with open(file_path, mode, encoding=encoding) as f:
                match file_type:
                    case ".json":
                        result = json.load(f)
                    case ".jsonl":
                        json_list = list(f)
                        jsons = []
                        for json_str in json_list:
                            line = json.loads(json_str)  # 문자열을 읽을때는 loads
                            jsons.append(line)
                        result = jsons
                    case _:  # ".txt"
                        if as_list:
                            result = f.read().splitlines()
                        else:
                            result = f.read()

        return result

    if os.path.getsize(file_path) == 0:
        raise EmptyFileError(f"The file {file_path} is empty")

    if file_type is None:
        file_type = get_suffix(file_path)

    try:
        result = _load_obj(file_path, encoding)
    except UnicodeDecodeError as e:  # may encoding problem
        try:
            encoding_fix = detect_encoding(file_path)
            result = _load_obj(file_path, encoding_fix)
        except Exception as e:
            logger.error(f"Fail to load '{file_path}")
            raise e
        else:
            logger.info(
                f"The appropriate file encoding value is {encoding_fix} not {encoding}. If you designate 'encoding={encoding_fix}', you'll be able to read the file faster"
            )
            encoding = encoding_fix

    if verbose:
        logger.debug(f"Success to load '{file_path}', with encoding='{encoding}'")
    return result


def save_obj(collection: Collection, path: Union[str, Path], verbose: bool = True):
    def default_serializer(obj):
        if isinstance(obj, set):
            return list(obj)

    _, file_extension = os.path.splitext(os.path.basename(path))

    # Make dirs
    dir_path = os.path.dirname(os.path.abspath(path))
    os.makedirs(dir_path, exist_ok=True)

    if file_extension in [".pickle", ".pkl", ".p"]:
        with open(path, "wb") as f:
            pickle.dump(collection, f)

    else:
        with open(path, "wb") as f:
            f.write(
                orjson.dumps(
                    collection,
                    option=orjson.OPT_APPEND_NEWLINE | orjson.OPT_INDENT_2 | orjson.OPT_SERIALIZE_NUMPY,
                    default=default_serializer,
                )
            )
    if verbose:
        logger.info(f"Save to {path}")


def unzip_as_dict(file: Union[str, io.BytesIO], return_as_file=True) -> Optional[dict]:
    # 파일 경로 또는 BytesIO 객체를 처리
    if isinstance(file, str):
        is_zip = zipfile.is_zipfile(file)
        zip_ref = zipfile.ZipFile(file, "r")
    elif isinstance(file, io.BytesIO):
        file.seek(0)  # Seek to the beginning of the file
        is_zip = zipfile.is_zipfile(file)
        zip_ref = zipfile.ZipFile(file, "r")
    else:
        logger.debug("Invalid file type")
        return None

    # 파일이 ZIP 파일인지 확인합니다.
    if not is_zip:
        logger.debug("The file is not a zip file")
        return None

    # ZIP 파일의 내용을 압축 해제합니다.
    files_dict = {}
    with zip_ref:
        for zip_info in zip_ref.infolist():
            if not zip_info.is_dir():
                with zip_ref.open(zip_info.filename) as f:
                    file_data = io.BytesIO(f.read()) if return_as_file else f.read()
                    if return_as_file:
                        file_data.seek(0)
                    recursive_filename = zip_info.filename.replace(os.path.sep, "_")
                    files_dict[recursive_filename] = file_data

    return files_dict


async def load_async(file_path):
    file_path = Path(file_path)

    if file_path.suffix in [".pickle", ".pkl", ".p"]:
        async with aiofiles.open(file_path, "rb") as f:
            data = await f.read()
        return pickle.loads(data)

    elif file_path.suffix == ".json":
        async with aiofiles.open(file_path, "r") as f:
            data = await f.read()
        return json.loads(data)

    elif file_path.suffix == ".txt":
        async with aiofiles.open(file_path, "r") as f:
            data = await f.read()
        return data
    else:
        raise NotImplementedError(f"No load func implemented for {file_path.suffix}")


async def save_async(data, file_path: Path):
    file_path = Path(file_path)

    if file_path.suffix in [".pickle", ".pkl", ".p"]:
        async with aiofiles.open(file_path, "wb") as f:
            pickle_data = pickle.dumps(data)
            await f.write(pickle_data)

    elif file_path.suffix == ".json":
        async with aiofiles.open(file_path, "w") as f:
            json_data = json.dumps(data, ensure_ascii=False, indent=2)
            await f.write(json_data)

    elif file_path.suffix == ".txt":
        async with aiofiles.open(file_path, "w") as f:
            await f.write(data)
    else:
        raise NotImplementedError(f"No save func implemented for {file_path.suffix}")


def load_json(response: str):
    try:
        return json.loads(response)  # TODO: refactor postprocesing
    except json.JSONDecodeError as e:
        logger.error(f"Undefined json parsing error raised: {e}\n\n{response}")
        raise


def get_suffix(path: Union[str, Path]):
    """Path에서 suffix 부분을 리턴히는 함수
    그냥 .with_suffix("")를 쓰면 SDRW2000000001.1 와 같은 형태가 들어왔을 때, '.1'가 삭제됨에 따라
    이를 유지시켜주기 위한 처리를 포함하고 있음
    """
    path = Path(path)
    suffix = path.suffix[1:]

    if len(suffix) >= 2 and re.search("[a-zA-Z]", path.suffix):
        return path.suffix
    else:
        return ""


def detect_encoding(file_path: Union[str, Path]):
    from chardet.universaldetector import UniversalDetector

    encoding_detector = UniversalDetector()

    encoding_detector.reset()
    for line in open(file_path, "rb"):
        encoding_detector.feed(line)
        if encoding_detector.done:
            break
    encoding_detector.close()

    result = encoding_detector.result  # {'encoding': 'EUC-KR', 'confidence': 0.99, 'language': 'Korean'}
    encoding = result["encoding"]

    # Use cp949(extension version of EUC-KR) instead of EUC-KR
    if encoding == "EUC-KR":
        encoding = "cp949"

    return encoding


def get_size(data, as_str=False):
    size_mb = round(sys.getsizeof(data) / (1024), 4)
    return f"{size_mb} KB" if as_str else size_mb


def remove_all_files_in_dir(dir_path):
    dir_path = Path(dir_path)
    files = dir_path.glob("*")
    for f in files:
        os.remove(f)


def get_relative_path(path: Path, num_from_end: int):
    return Path(*Path(path).parts[-num_from_end:])


class EmptyFileError(Exception):
    def __init__(self, msg: str = None):
        error_msg = "The file is empty" if msg is None else msg
        super().__init__(error_msg)


# WEB IO #


async def fetch(
    url: str,
    method: str = "GET",
    headers: Optional[dict] = None,
    params: Optional[dict] = None,
    data: Optional[dict] = None,
) -> tuple[dict, int]:
    async with aiohttp.ClientSession() as session:
        async with session.request(method, url, headers=headers, params=params, json=data) as response:
            return await response.json(), response.status


def is_valid_url(url):
    try:
        response = requests.get(url)
        # 200-299 사이의 상태 코드는 성공을 의미합니다.
        return 200 <= response.status_code < 300
    except requests.RequestException:
        return False


async def try_run(
    runner: callable,
    *args,
    is_async: bool = False,
    max_retries: int = 3,
    wait_time: int = 3,
    error_msg="Failed after maximum retries",
    **kwargs,
):
    for i in range(max_retries):
        try:
            return await runner(*args, **kwargs)
        except Exception as e:
            logger.error(f"Attempt {i+1} - Error raised: {e}, {args=}, {kwargs=}")
            if i < max_retries - 1:
                if is_async:
                    await asyncio.sleep(wait_time)
                else:
                    time.sleep(wait_time)
            else:
                raise SystemError(error_msg)


# Others #


def make_unique_id(seed: str = None) -> str:
    if seed is None:
        return str(uuid.uuid4())

    else:
        return str(uuid.uuid3(uuid.NAMESPACE_URL, seed))


def get_current_datetime(format="%Y-%m-%d_%H-%M-%S"):
    return datetime.now().strftime(format)


def get_current_timestamp(unit="µs") -> float:
    match unit:
        case "µs":
            mutiplier = 1000000
        case "ms":
            mutiplier = 1000
        case "s":
            mutiplier = 1
        case _:
            raise ValueError(f"Invalid unit: {unit}")

    return datetime.now().timestamp() * mutiplier


def get_datetime_from_timestamp_ms(timestamp: int):
    return datetime.fromtimestamp(timestamp / 1000.0)


def check_if_timestamp_ms_in_hour_from_now(timestamp_ms: int, hours: int):
    current_timestamp_ms = int(get_current_timestamp("ms"))

    # 주어진 timestamp와 현재 시간의 차이를 계산
    difference_ms = current_timestamp_ms - timestamp_ms
    # 1일은 24시간 x 60분 x 60초 x 1000ms = 86,400,000ms
    standard_ms = hours * 60 * 60 * 1000

    return difference_ms <= standard_ms
