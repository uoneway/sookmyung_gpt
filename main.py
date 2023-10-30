# import sys
# from pathlib import Path
import asyncio
import os
from concurrent.futures import ThreadPoolExecutor

# import pandas as pd
import streamlit as st

from src import logger
from src.common.consts import ALLOWED_EXTENSIONS, ALLOWED_EXTENSIONS_WITH_ZIP, RESULT_DIR
from src.common.models import ReportFile, ReportFileList
from src.processor.generator import request_llm
from src.processor.reader import FileReader, get_suffix
from src.utils.io import get_current_timestamp, get_suffix, load_json, unzip_as_dict


def read_report_file(file, name=None) -> ReportFile:
    name = file.name if name is None else name
    extension = get_suffix(name)
    file_reader = FileReader(file=file, filetype=extension, clean=True)
    return ReportFile(name=name, content=file_reader.text)


def read_report_files_concurrently(files, names) -> ReportFileList:
    with ThreadPoolExecutor() as executor:
        return ReportFileList(executor.map(read_report_file, files, names))


async def run_llm_concurrently(report_file_list):
    tasks = []
    for report_file in report_file_list:
        tasks.append(request_llm(input_text=report_file.content))
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return results


# Configure Streamlit page and state
st.title("AI 기반 미래역량 평가 도구")
st.markdown("#### 숙명여대 SSK 연구사업 AI-CALI팀 개발")

with st.form("input"):
    type_option = st.selectbox("역량", ["의사소통"])
    upload_files = st.file_uploader(
        f"과제 파일 업로드({' '.join(ALLOWED_EXTENSIONS_WITH_ZIP)})",
        accept_multiple_files=True,
        type=[ext[1:] for ext in ALLOWED_EXTENSIONS_WITH_ZIP],
    )
    # for filename, content in file_info.items():
    #     src_path = tgt_dir / filename
    #     async with aiofiles.open(src_path, "wb") as f:
    #         await f.write(content)
    #         logger.info(f"File uploaded to {src_path}")

    submitted = st.form_submit_button("Submit")


result_dict = {}
if submitted:
    if not upload_files:
        st.error("1개 이상의 파일을 첨부해주세요.")

    # Output
    with st.spinner("파일을 읽고 있습니다... ⏳"):
        files_dict = dict()
        for upload_file in upload_files:
            suffix = get_suffix(upload_file.name)
            if suffix == ".zip":
                _files_dict = unzip_as_dict(upload_file, return_as_file=True)

                for filename, file in _files_dict.items():
                    if (ext := get_suffix(filename)) not in ALLOWED_EXTENSIONS:
                        st.error(f"Unsupported file type: {ext}")
                        st.stop()

                files_dict.update(_files_dict)

            else:
                files_dict[upload_file.name] = upload_file

        try:
            input_file_list = read_report_files_concurrently(files_dict.values(), files_dict.keys())
        except Exception as e:
            st.error("Error reading file. Make sure certain files are not corrupted or encrypted")
            logger.error(f"Cannot read certarin files:{e.__class__.__name__}: {e}")
            st.stop()

    with st.spinner("결과를 생성중입니다... 약 1분 내외가 소요됩니다. ⏳"):
        current_timestamp = get_current_timestamp(unit="µs")
        tgt_dir = RESULT_DIR / str(int(current_timestamp))
        os.makedirs(tgt_dir, exist_ok=True)

        # Run LLM
        results = asyncio.run(run_llm_concurrently(input_file_list))
        assert len(results) == len(input_file_list)
        # total_results = []
        # for report_file, result in zip(input_file_list, results):
        #     total_results.append([result[0], result[1], result[2], report_file.name])
        # result = pd.DataFrame(input_file_list.to_list_of_dict())

        # result.to_csv(tgt_dir / "report.csv", index=False)
        print(results)

        result_dict = load_json(results[0][0])
        print(result_dict)

        # df = pd.DataFrame(results, columns=["결과", "모델", "토큰 사용량", "프롬프트"])
for category, result in result_dict.items():
    st.write(category)
    st.write(result["score"])
    st.write(result["description"])

# if submitted and upload_files:
#     for upload_file in upload_files:
#         st.write(upload_file.type)
#         st.write("filename:", upload_file.name)
#         bytes_data = upload_file.read()


# with st.form("output") as f:
#     output = st.empty()
#     result = ""

#     if submitted:
#         resp = get_response_oai(upload_topic)
#     hiddent_submit = st.form_submit_button("Generation Finished", disabled=True)

# st.write(f"길이: {len(content)} 자")
# st.write(f"비용: {cost:.3f} usd($)")
# st.download_button("Download", content)
