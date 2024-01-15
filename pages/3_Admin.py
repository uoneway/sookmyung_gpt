import streamlit as st
import toml
from streamlit_extras.stylable_container import stylable_container

from src.common.consts import PROMPT_ARCHIVE_DIR, PROMPT_PER_CATEGORY_DIR
from src.common.models import (
    reset_all_category_info,
    reset_category_id_to_name_ko_dict,
    reset_category_strenum,
    reset_prompt_per_category_dict,
)
from src.utils.io import get_current_datetime, make_unique_id

cate_dict_template = {
    "category_name_ko": "",
    "category_name_en": "",
    "criteria": [
        {
            "title_ko": "",
            "title_en": "",
            "elements": [""],
        }
    ],
}

# Read .toml files and build the category_option_dict
if "prompt_per_category_dict" not in st.session_state:
    reset_prompt_per_category_dict()

if "category_id_to_name_ko_dict" not in st.session_state:
    reset_category_id_to_name_ko_dict()

if "Category" not in st.session_state:
    reset_category_strenum()

if "select_category_idx" not in st.session_state:
    st.session_state["select_category_idx"] = 0

if "edit_mode" not in st.session_state:
    st.session_state["edit_mode"] = False


col1, col2 = st.columns([1, 1])
with col1:
    on = st.toggle("Edit mode", False, key="edit_mode")

with col2:
    if st.session_state["edit_mode"]:
        with stylable_container(
            key="stylable_container_add_category",
            css_styles=[
                """
                div[data-testid="stButton"]:nth-of-type(1) {
                    text-align: right;
                }
                """
            ],
        ):
            if st.button("역량 추가하기"):
                new_category_id = f"{get_current_datetime()}_{make_unique_id()}"
                if f"{new_category_id}_category" not in st.session_state:
                    st.session_state[f"{new_category_id}_category"] = cate_dict_template.copy()
                cate_dict_session = st.session_state[f"{new_category_id}_category"]

                new_prompt_path = PROMPT_PER_CATEGORY_DIR / f"{new_category_id}.toml"
                with open(new_prompt_path, "w") as file:
                    toml.dump(cate_dict_session, file)

                reset_all_category_info()
                st.session_state["select_category_idx"] = (
                    len(st.session_state["category_id_to_name_ko_dict"].keys()) - 1
                )
                st.rerun()

st.markdown("## 역량별 평가기준 관리")
category_id_selected = st.selectbox(
    "역량",
    options=list(st.session_state["category_id_to_name_ko_dict"].keys()),
    format_func=lambda x: st.session_state["category_id_to_name_ko_dict"][x],
    # options=list(st.session_state["category_id_to_name_ko_dict"].keys()) + ["Add New Category..."],
    # format_func=lambda x: st.session_state["category_id_to_name_ko_dict"][x] if x != "Add New Category..." else x,
    index=st.session_state["select_category_idx"],
    # placeholder="Select contact method...",
    label_visibility="collapsed",
)


# 데이터 표시 및 편집
if st.session_state["edit_mode"]:
    prompt_path = PROMPT_PER_CATEGORY_DIR / f"{category_id_selected}.toml"
    if prompt_path.is_file():  # 기존 카테고리 편집
        cate_dict_orig = toml.load(prompt_path)
        if f"{category_id_selected}_category" not in st.session_state:
            st.session_state[f"{category_id_selected}_category"] = cate_dict_orig.copy()
        cate_dict_session = st.session_state[f"{category_id_selected}_category"]

        # st.divider()
        st.markdown("### 역량명")
        col1, col2 = st.columns([1, 1])
        with col1:
            cate_dict_session["category_name_ko"] = st.text_input(
                "ko", value=cate_dict_session["category_name_ko"], key="categoty_name_ko"
            )
        with col2:
            cate_dict_session["category_name_en"] = st.text_input(
                "en", value=cate_dict_session["category_name_en"], key="category_name_en"
            )

        for main_idx, main_crit in enumerate(cate_dict_session["criteria"]):
            st.divider()

            col1, col2 = st.columns([1, 1])
            with col1:
                st.markdown(f"#### 평가기준 {main_idx+1}")
            with col2:
                with stylable_container(
                    key=f"stylable_container_{main_idx}",
                    css_styles=[
                        """
                        div[data-testid="stButton"]:nth-of-type(1) {
                            text-align: right;
                        }
                        """,
                        """
                        button {
                            border: none;
                        }
                        """,
                    ],
                ):
                    if st.button("❎", key=f"delete_main_crit_{main_idx}"):
                        # st.warning(f"정말로 {main_crit['title_ko']} 삭제하시겠습니까?")
                        cate_dict_session["criteria"].pop(main_idx)
                        st.rerun()

                # if first_click:
                #     print("1111")
                #     if st.button("네 정말 삭제하겠습니다", key=f"delete_main_crit_{main_idx}_confirm"):
                #         print("aaaaaa")
                #         cate_dict_session["criteria"].pop(main_idx)
                #         st.rerun()

            with st.container():
                col1, col2 = st.columns([1, 1])
                with col1:
                    cate_dict_session["criteria"][main_idx]["title_ko"] = st.text_input(
                        "평가기준명(ko)", value=main_crit["title_ko"], key=f"main_crit_{main_idx}_title_ko"
                    )
                with col2:
                    cate_dict_session["criteria"][main_idx]["title_en"] = st.text_input(
                        "평가기준명(en)", value=main_crit["title_en"], key=f"main_crit_{main_idx}_title_en"
                    )

                st.write("세부 평가기준")
                for sub_idx, sub_crit in enumerate(main_crit["elements"]):
                    cate_dict_session["criteria"][main_idx]["elements"][sub_idx] = st.text_input(
                        f"세부 평가기준 {sub_idx}",
                        value=sub_crit,
                        key=f"sub_{main_crit}_{sub_idx}",
                        label_visibility="collapsed",
                    )

                if st.button("➕ 세부 평가기준 추가", key=f"add_sub_{main_idx}", help="세부 평가기준을 추가합니다."):
                    cate_dict_session["criteria"][main_idx]["elements"].append("")
                    st.rerun()

        # Add New Main Criteria Section
        st.divider()
        if st.button("➕ 평가기준 추가", help="평가기준을 추가합니다."):
            i = len(cate_dict_session["criteria"]) + 1
            cate_dict_session["criteria"].append({"title_ko": "", "title_en": "", "elements": [""]})
            st.rerun()

    else:
        st.error("해당 역량에 대한 평가기준 파일을 찾을 수 없습니다. 관리자에게 문의해주세요.")

    # 변경사항 저장
    st.divider()
    to_be_saved = True if cate_dict_orig != cate_dict_session else False
    if st.button(
        "저장하기",
        disabled=not to_be_saved,
        use_container_width=True,
        help="변경사항을 저장합니다. 변경사항이 있을 떄 활성화되며, 저장하지 않은 변경사항은 사라집니다.",
    ):
        # Check
        # 평가기준별로 세부 평가기준에서 공백이 있는 경우 제거하기
        for main_crit in cate_dict_session["criteria"]:
            main_crit["elements"] = [sub_crit for sub_crit in main_crit["elements"] if sub_crit]

        is_valid = True
        if not cate_dict_session["category_name_ko"]:
            st.error("역량명(ko)를 입력해주세요")
            is_valid = False
        if not cate_dict_session["category_name_en"]:
            st.error("역량명(en)를 입력해주세요")
            is_valid = False
        if not cate_dict_session["criteria"]:
            st.error("평가기준이 최소 1개 이상 입력되어야 합니다")
            is_valid = False
        if not all([main_crit["title_ko"] and main_crit["title_en"] for main_crit in cate_dict_session["criteria"]]):
            st.error("평가기준명(ko), 평가기준명(en)은 모두 입력되어야 합니다")
            is_valid = False
        if not all([main_crit["elements"] for main_crit in cate_dict_session["criteria"]]):
            st.error("평가기준별 세부 평가기준은 최소 1개 이상 입력되어야 합니다")
            is_valid = False

        # title_en, title_ko 중복 체크
        title_en_list = [main_crit["title_en"] for main_crit in cate_dict_session["criteria"]]
        if len(title_en_list) != len(set(title_en_list)):
            st.error("평가기준명(en)은 중복되어서는 안됩니다")
            is_valid = False
        title_ko_list = [main_crit["title_ko"] for main_crit in cate_dict_session["criteria"]]
        if len(title_ko_list) != len(set(title_ko_list)):
            st.error("평가기준명(ko)은 중복되어서는 안됩니다")
            is_valid = False

        # TODO: category_name_en, category_name_ko 중복 체크

        if not is_valid:
            st.stop()

        # 기존 파일 백업
        archive_prompt_path = PROMPT_ARCHIVE_DIR / f"{prompt_path.stem}_{get_current_datetime()}{prompt_path.suffix}"
        prompt_path.rename(archive_prompt_path)

        # 변경사항 저장
        with open(prompt_path, "w") as file:
            toml.dump(cate_dict_session, file)
        reset_all_category_info()

        st.info("저장되었습니다")
        st.rerun()

    st.divider()
    # 카테고리 삭제 기능 (편집 모드에서만 가능)
    with stylable_container(
        key="stylable_container_delete_category",
        css_styles=[
            """
            div[data-testid="baseButton-secondary"]:nth-of-type(1) {
                text-align: right;
            }
            """,
            """
            button {
                background-color: #ef7777;
                color: white;
            }
            """,
        ],
    ):
        if st.button("역량 삭제하기", help="현재 보이는 역량 자체를 삭제합니다."):
            # 기존 파일 백업
            archive_prompt_path = (
                PROMPT_ARCHIVE_DIR / f"{prompt_path.stem}_{get_current_datetime()}{prompt_path.suffix}"
            )
            prompt_path.rename(archive_prompt_path)

            reset_all_category_info()
            st.rerun()

else:
    # 편집 불가능한 상태로 정보 표시
    if category_id_selected in st.session_state["prompt_per_category_dict"]:  # 기존 카테고리 표시
        criteria_list = st.session_state["prompt_per_category_dict"][category_id_selected]["criteria"]
        for main_crit in criteria_list:
            main_crit, sub_crit_list = main_crit["title_en"], main_crit["elements"]
            st.markdown(f"#### {main_crit}")
            for sub_crit in sub_crit_list:
                st.markdown(f"- {sub_crit}")
