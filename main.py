import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO
from pathlib import Path

import pandas as pd
import streamlit as st

from src import logger
from src.common.consts import ALLOWED_EXTENSIONS, ALLOWED_EXTENSIONS_WITH_ZIP, MAX_CHAR_LEN_PER_FILE, OUTPUT_DTYPE_DICT
from src.common.models import ReportFile, ReportFileList, reset_all_category_info
from src.processor.generator import Generator
from src.processor.reader import FileReader
from src.utils.google_drive import GD_DOCS_FILE_URL, GD_RESULT_FOLDER_ID, GoogleDriveHelper
from src.utils.io import excel_col_index_to_name, get_current_datetime, get_suffix, unzip_as_dict

gd_helper = GoogleDriveHelper(GD_RESULT_FOLDER_ID)


if "category_id_to_name_ko_dict" not in st.session_state:
    reset_all_category_info()


def read_report_file(file, name=None) -> ReportFile | str:
    try:
        name = file.name if name is None else name
        extension = get_suffix(name)
        file_reader = FileReader(file=file, filetype=extension, clean=True)
        return ReportFile(name=name, content=file_reader.text)
    except Exception as e:
        return f"{e.__class__.__name__}: {str(e)}"


def read_report_files_concurrently(files, names) -> dict[str, ReportFile | str]:
    report_files_dict = {}
    with ThreadPoolExecutor() as executor:
        future_to_name = {executor.submit(read_report_file, file, name): name for file, name in zip(files, names)}
        for future in as_completed(future_to_name):
            name = future_to_name[future]
            result = future.result()  # 여기서 발생하는 예외는 read_report_file 함수 내에서 이미 처리됨
            report_files_dict[name] = result
    return report_files_dict


async def run_llm_concurrently(report_file_list, category_id):
    generator = Generator()

    tasks = []
    for report_file in report_file_list:
        tasks.append(generator.agenerate(category=category_id, input_text=report_file.content))
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return results


def raise_error(msg="Error", e=Exception):
    msg = f"{msg}: {e.__class__.__name__}: {e}"
    st.error(msg)
    logger.error(msg)


# https://docs.streamlit.io/library/api-reference/utilities/st.set_page_config
st.set_page_config(
    page_title="AI 기반 미래역량 평가 도구", page_icon="🧊", layout="centered", initial_sidebar_state="auto"  # "wide",
)

# #  Hide sidebar menu
# st.markdown(
#     # [data-testid="collapsedControl"] {
#     """
#     <style>
#         section[data-testid="stSidebar"][aria-expanded="true"]{
#             display: none;
#         }
#     </style>
#     """,
#     unsafe_allow_html=True,
# )

# Configure Streamlit page and state
st.title("AI 기반 미래역량 평가 도구")
st.markdown("#### 숙명여대 SSK 연구사업 AI-CALI팀 개발")
st.write(
    "이 점수는 연구진이 개발한 채점기준을 활용하여 GPT-4가 채점을 시행한 결과로, "
    + "향후 채점의 신뢰도와 타당도를 평가하고 개선하기 위한 연구자료로 활용됩니다. "
    + "현재 단계에서 GPT-4의 채점결과는 실제 해당 역량의 특성을 충분히 반영하고 있지 않을 수 있으므로, 해석과 사용 시 주의가 필요합니다"
)

with st.form("input"):
    st.markdown(f"역량 [ℹ️]({GD_DOCS_FILE_URL})", unsafe_allow_html=True)
    category_id_selected = st.selectbox(
        "역량",
        options=tuple(st.session_state["category_id_to_name_ko_dict"].keys()),
        format_func=lambda x: st.session_state["category_id_to_name_ko_dict"][x],
        label_visibility="collapsed",
        # index=None,
        # placeholder="Select contact method...",
    )
    st.markdown(f"과제 파일 업로드({' '.join(ALLOWED_EXTENSIONS_WITH_ZIP)})")
    upload_files = st.file_uploader(
        "과제 파일 업로드",
        accept_multiple_files=True,
        type=[ext[1:] for ext in ALLOWED_EXTENSIONS_WITH_ZIP],
        label_visibility="collapsed",
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

        input_file_dict = read_report_files_concurrently(files_dict.values(), files_dict.keys())
        error_dict = {filename: v for filename, v in input_file_dict.items() if isinstance(v, str)}
        if error_dict:
            for filename, error_msg in error_dict.items():
                error_msg = f"'{filename}'을 읽는 도중 오류({error_msg})가 발생했습니다."
                if Path(filename).suffix == ".hwp":
                    error_msg += " pdf나 word 파일로 변환하여 사용하십시오"
                st.error(error_msg)
            st.stop()

        input_file_list = ReportFileList([v for v in input_file_dict.values()])
        for file in input_file_list:
            if len(file.content) > MAX_CHAR_LEN_PER_FILE:
                st.warning(
                    f"Since the '{file.name}' file is too long"
                    + f"({len(file.content)} chars), "
                    + f"only the content up to {MAX_CHAR_LEN_PER_FILE} will be used for processing."
                )
                file.content = file.content[:MAX_CHAR_LEN_PER_FILE]
        st.write(f"총 {len(input_file_list)}개 파일을 읽었습니다.")
        logger.info(f"File loaded: {[file.name for file in input_file_list]}")

    with st.spinner("평가중입니다... 약 1~2분 소요됩니다."):
        # Run LLM
        logger.info("Start to run LLM...")
        results = asyncio.run(run_llm_concurrently(report_file_list=input_file_list, category_id=category_id_selected))
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
        # Should sync with serialize_score_info in agenerate
        criteria_dict = st.session_state["prompt_per_category_dict"][category_id_selected]
        output_dtype_dict = OUTPUT_DTYPE_DICT[0].copy()
        for crit_dict in criteria_dict["criteria"]:
            prefix = crit_dict["title_en"].lower()
            output_dtype_dict.update(
                {f"{prefix}_{sub_idx+1}": "Int64" for sub_idx in range(len(crit_dict["sub_criteria"]))}
            )
            output_dtype_dict[f"{prefix}_total"] = "Int64"
        output_dtype_dict.update({"Total": "Int64"})
        output_dtype_dict.update(
            {f"{crit_dict['title_en'].lower()}_descript": "str" for crit_dict in criteria_dict["criteria"]}
        )
        output_dtype_dict.update(OUTPUT_DTYPE_DICT[1].copy())

        result_df = pd.DataFrame(columns=output_dtype_dict.keys())
        new_df = pd.DataFrame(total_results)
        result_df = pd.concat([result_df, new_df], ignore_index=True)
        output_str_columns = [colname for colname, t in output_dtype_dict.items() if t == "str"]
        result_df.loc[:, output_str_columns] = result_df[output_str_columns].fillna("")
        result_df = result_df.astype(output_dtype_dict)

    with st.spinner("결과를 구글드라이브에 업로드하고 있습니다..."):
        # encoding = "utf-8-sig"
        # filename = f"report_{stu_id_base}.csv"
        # result_csv_bytes = result_df.to_csv(index=False).encode(encoding)
        filename = f"report_{stu_id_base}.xlsx"
        output = BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            result_df.to_excel(writer, index=False)

            workbook = writer.book
            worksheet = writer.sheets["Sheet1"]

            # 칼럼 너비 설정
            cell_format = {}  # workbook.add_format({"text_wrap": True})
            col_span_name = f"{excel_col_index_to_name(0)}:{excel_col_index_to_name(0)}"
            worksheet.set_column(col_span_name, 15, cell_format)
            long_width_col_idxs = [
                idx
                for idx, key_name in enumerate(output_dtype_dict.keys())
                if "_descript" in key_name or key_name == "원문 내용"
            ]
            for idx in long_width_col_idxs:
                col_span_name = f"{excel_col_index_to_name(idx)}:{excel_col_index_to_name(idx)}"
                worksheet.set_column(col_span_name, 40, cell_format)

            # 모든 행의 높이 설정
            row_height = 100  # 원하는 행 높이
            cell_format = workbook.add_format({"text_wrap": True, "valign": "top"})  # 상단 정렬
            for row in range(len(result_df)):
                worksheet.set_row(row + 1, row_height, cell_format)  # 헤더 행 제외 나머지

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
