import copy

import streamlit as st
import streamlit_authenticator as stauth
import toml
import yaml
from streamlit_extras.stylable_container import stylable_container
from yaml.loader import SafeLoader

from src import logger
from src.common.consts import PROMPT_ARCHIVE_DIR, PROMPT_PER_CATEGORY_DIR
from src.common.models import (
    reset_all_category_info,
    reset_category_id_to_name_ko_dict,
    reset_category_strenum,
    reset_prompt_per_category_dict,
)
from src.utils.google_drive import (
    GD_PROMPT_ARCHIVE_FOLDER_ID,
    GD_PROMPT_FOLDER_ID,
    GoogleDriveHelper,
    get_prompt_folder_id_in_gd,
)
from src.utils.io import get_current_datetime, make_unique_id

gd_helper = GoogleDriveHelper(GD_PROMPT_FOLDER_ID)
# Authentication
with open(".streamlit/config.yaml") as file:
    config = yaml.load(file, Loader=SafeLoader)

authenticator = stauth.Authenticate(
    config["credentials"],
    config["cookie"]["name"],
    config["cookie"]["key"],
    config["cookie"]["expiry_days"],
    config["preauthorized"],
)

# Login
authenticator.login("Login", "main")  # sidebar

if st.session_state["authentication_status"] is False:
    st.error("Username/password is incorrect")
    st.stop()
elif st.session_state["authentication_status"] is None:
    st.warning("Please enter your username and password")
    st.stop()
elif st.session_state["authentication_status"]:
    authenticator.logout("Logout", "main", key="unique_key")
    st.write(f'Welcome *{st.session_state["name"]}*')
    st.title("Cretia Management")


# Admin page
sub_crit_dict_template = {
    "description": "",
    "scale_min": 1,
    "scale_max": 5,
}
crit_dict_template = {
    "title_ko": "",
    "title_en": "",
    "sub_criteria": [sub_crit_dict_template],
}

cate_dict_template = {
    "category_name_ko": "(신규 역량)",
    "category_name_en": "",
    "criteria": [crit_dict_template],
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
                    st.session_state[f"{new_category_id}_category"] = copy.deepcopy(cate_dict_template)
                cate_dict_session = st.session_state[f"{new_category_id}_category"]

                # Save
                new_prompt_path = PROMPT_PER_CATEGORY_DIR / f"{new_category_id}.toml"
                with open(new_prompt_path, "w") as file:
                    toml.dump(cate_dict_session, file)
                gd_helper.upload(
                    filename=new_prompt_path.name,
                    content=toml.dumps(cate_dict_session),
                    folder_id=get_prompt_folder_id_in_gd(),
                )

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
                for sub_idx, sub_crit_dict in enumerate(main_crit["sub_criteria"]):
                    col1, col2, col3, col4 = st.columns([7, 1, 1, 1])
                    with col1:
                        cate_dict_session["criteria"][main_idx]["sub_criteria"][sub_idx]["description"] = st.text_input(
                            "세부 평가기준 description",
                            value=sub_crit_dict["description"],
                            key=f"sub_{main_crit}_{sub_idx}",
                            placeholder="설명",
                            label_visibility="collapsed",
                        )
                    with col2:
                        cate_dict_session["criteria"][main_idx]["sub_criteria"][sub_idx]["scale_min"] = st.number_input(
                            "세부 평가기준 scale_min",
                            value=sub_crit_dict["scale_min"],
                            step=1,
                            key=f"sub_{main_crit}_{sub_idx}_scale_min",
                            placeholder="최소",
                            label_visibility="collapsed",
                        )
                    with col3:
                        cate_dict_session["criteria"][main_idx]["sub_criteria"][sub_idx]["scale_max"] = st.number_input(
                            "세부 평가기준 scale_max",
                            value=sub_crit_dict["scale_max"],
                            step=1,
                            key=f"sub_{main_crit}_{sub_idx}_scale_max",
                            placeholder="최대",
                            label_visibility="collapsed",
                        )
                    with col4:
                        with stylable_container(
                            key="stylable_container_delete_sub_crit",
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
                            if st.button("❎", key=f"delete_sub_crit_{main_idx}_{sub_idx}"):
                                cate_dict_session["criteria"][main_idx]["sub_criteria"].pop(sub_idx)
                                st.rerun()

                if st.button("➕ 세부 평가기준 추가", key=f"add_sub_{main_idx}", help="세부 평가기준을 추가합니다."):
                    cate_dict_session["criteria"][main_idx]["sub_criteria"].append(
                        copy.deepcopy(sub_crit_dict_template)
                    )
                    st.rerun()

        # Add New Main Criteria Section
        st.divider()
        if st.button("➕ 평가기준 추가", help="평가기준을 추가합니다."):
            i = len(cate_dict_session["criteria"]) + 1
            cate_dict_session["criteria"].append(copy.deepcopy(crit_dict_template))
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
        # 평가기준별로 세부 평가기준을 안넣은 경우는 제거하기
        for main_crit in cate_dict_session["criteria"]:
            main_crit["sub_criteria"] = [
                {
                    "description": sub_crit["description"].strip(),
                    "scale_min": sub_crit["scale_min"],
                    "scale_max": sub_crit["scale_max"],
                }
                for sub_crit in main_crit["sub_criteria"]
                if sub_crit["description"]
            ]

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

        for main_crit in cate_dict_session["criteria"]:
            if not main_crit["sub_criteria"]:
                st.error("평가기준별 세부 평가기준은 최소 1개 이상 입력되어야 합니다")
                is_valid = False
            for sub_crit in main_crit["sub_criteria"]:
                if not all(
                    [
                        sub_crit["description"],
                        isinstance(sub_crit["scale_min"], int),
                        isinstance(sub_crit["scale_max"], int),
                    ]
                ):
                    st.error("세부 평가기준의 설명, 최소, 최대 값은 모두 입력되어야 합니다")
                    is_valid = False

                    if sub_crit["scale_min"] >= sub_crit["scale_max"]:
                        st.error("세부 평가기준의 최소값은 최대값보다 작아야 합니다")
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

        # 파일 로컬에 저장: 기존 파일 백업 & 변경사항 저장
        archive_prompt_path = PROMPT_ARCHIVE_DIR / f"{prompt_path.stem}_{get_current_datetime()}{prompt_path.suffix}"
        prompt_path.rename(archive_prompt_path)
        with open(prompt_path, "w") as file:
            toml.dump(cate_dict_session, file)

        # 파일 구글드라이브에 업로드
        try:
            archive_file_id = gd_helper.get_file_id(prompt_path.name, folder_id=get_prompt_folder_id_in_gd())
            gd_helper.move(archive_file_id, GD_PROMPT_ARCHIVE_FOLDER_ID)
        except ValueError as e:
            logger.error(e)

        gd_helper.upload(
            filename=prompt_path.name,
            content=toml.dumps(cate_dict_session),
            folder_id=get_prompt_folder_id_in_gd(),
        )
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
            try:
                # Check
                for k, v in main_crit.items():
                    if not v:
                        raise KeyError(k)
                st.markdown(f"#### {main_crit['title_ko']} ({main_crit['title_en']})")
                for sub_crit_dict in main_crit["sub_criteria"]:
                    for k, v in sub_crit_dict.items():
                        if not v:
                            raise KeyError(k)
                    st.markdown(
                        f"- {sub_crit_dict['description']} "
                        + f"({sub_crit_dict['scale_min']}~{sub_crit_dict['scale_max']}점)"
                    )

            except KeyError as e:
                st.error(f"해당 역량 파일에 필수 값이 빠져 있습니다. 수정 모드에서 수정해주세요: {e}")
