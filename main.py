import asyncio
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO

import pandas as pd
import streamlit as st

from src import logger
from src.common.consts import ALLOWED_EXTENSIONS, ALLOWED_EXTENSIONS_WITH_ZIP, OUTPUT_DTYPE_DICT, OUTPUT_STR_COLUMNS
from src.common.models import ReportFile, ReportFileList
from src.processor.generator import request_llm
from src.processor.reader import FileReader
from src.utils.google_drive import GoogleDriveHelper
from src.utils.io import get_current_datetime, get_suffix, unzip_as_dict

gd_helper = GoogleDriveHelper()


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


def raise_error(msg="Error", e=Exception):
    msg = f"{msg}: {e.__class__.__name__}: {e}"
    st.error(msg)
    logger.error(msg)


# Configure Streamlit page and state
st.title("AI 기반 미래역량 평가 도구")
st.markdown("#### 숙명여대 SSK 연구사업 AI-CALI팀 개발")
st.write(
    "이 점수는 연구진이 개발한 채점기준을 활용하여 GPT-4가 채점을 시행한 결과로, "
    + "향후 채점의 신뢰도와 타당도를 평가하고 개선하기 위한 연구자료로 활용됩니다. "
    + "현재 단계에서 GPT-4의 채점결과는 실제 해당 역량의 특성을 충분히 반영하고 있지 않을 수 있으므로, 해석과 사용 시 주의가 필요합니다"
)

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

    submitted = st.form_submit_button("평가하기")


if submitted:
    if not upload_files:
        st.error("1개 이상의 파일을 첨부해주세요.")
        st.stop()
    logger.info(f"File uploaded: {[file.name for file in upload_files]}")

    with st.spinner("파일을 읽고 있습니다..."):
        files_dict = dict()
        for upload_file in upload_files:
            suffix = get_suffix(upload_file.name)
            if suffix == ".zip":
                _files_dict = unzip_as_dict(upload_file, return_as_file=True)
                for filename, file in _files_dict.items():
                    if (ext := get_suffix(filename)) not in ALLOWED_EXTENSIONS:
                        raise_error(f"The {upload_file.name} file include unsupported file type: {ext}")

                files_dict.update(_files_dict)

            else:
                files_dict[upload_file.name] = upload_file

        try:
            input_file_list = read_report_files_concurrently(files_dict.values(), files_dict.keys())
            st.write(f"총 {len(input_file_list)}개 파일을 읽었습니다.")
            logger.info(f"File loaded: {[file.name for file in input_file_list]}")
        except Exception as e:
            raise_error("Cannot read certain file. Make sure certain files are not corrupted or encrypted", e)
            st.stop()

    with st.spinner("평가중입니다... 약 1~2분 소요됩니다."):
        # Run LLM
        logger.info("Start to run LLM...")
        results = asyncio.run(run_llm_concurrently(input_file_list))
        assert len(results) == len(input_file_list)

        stu_id_base = get_current_datetime(format="%y%m%d_%H%M%S")
        total_results = []
        for idx, (report_file, result) in enumerate(zip(input_file_list, results), start=1):
            _result = {"STU ID": f"{stu_id_base}_{idx}", "비고": ""}
            if isinstance(result, Exception):
                if len(input_file_list) == 1:
                    raise_error("Error raise", result)
                    st.stop()
                else:
                    _result["비고"] = result
            else:
                _result.update(result["score_info"])
                _result.update({"사용 모델명": result["model_name"]})
            _result.update({"원문파일명": report_file.name, "원문 내용": report_file.content})

            total_results.append(_result)

            # 모든 결과에 일부 키값이 없는 경우가 있을 수 있기에, 구조 맞춰주기 위해 빈 데이터프레임을 먼저 생성
            result_df = pd.DataFrame(columns=OUTPUT_DTYPE_DICT.keys())
            new_df = pd.DataFrame(total_results)
            result_df = pd.concat([result_df, new_df], ignore_index=True)
            result_df.loc[:, OUTPUT_STR_COLUMNS] = result_df[OUTPUT_STR_COLUMNS].fillna("")
            result_df = result_df.astype(OUTPUT_DTYPE_DICT)

    with st.spinner("결과를 구글드라이브에 업로드하고 있습니다..."):
        # encoding = "utf-8-sig"
        # filename = f"report_{stu_id_base}.csv"
        # result_csv_bytes = result_df.to_csv(index=False).encode(encoding)
        filename = f"report_{stu_id_base}.xlsx"
        output = BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            result_df.to_excel(writer, index=False)
        result_xlsx_bytes = output.getvalue()

        # Save to google drive
        try:
            # folder = gd_helper.create_folder(stu_id_base)
            file = gd_helper.upload_byte_obj(filename, result_xlsx_bytes)  # , folder_id=folder["id"])

        except Exception as e:
            raise_error("Cannot upload result to google drive", e)
        else:
            st.link_button("결과 Google drive에서 확인하기", url=file["alternateLink"])  # folder["alternateLink"])
            # embedLink: preview, webContentLink: downlaod
            # st.link_button("Google drive에서 확인하기", url=file["alternateLink"])

        # 다운로드 버튼 추가
        # st.download_button("결과 다운받기", result_csv_bytes, filename, "text/csv", key="download-csv")
        st.download_button(
            "결과 파일로 다운받기",
            result_xlsx_bytes,
            filename,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="download-xlsx",
        )

        st.success("평가가 완료되었습니다. 결과를 확인해주세요.")

# st.write(f"길이: {len(content)} 자")
# st.write(f"비용: {cost:.3f} usd($)")
