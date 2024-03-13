from dataclasses import dataclass, field
from enum import StrEnum
from typing import Optional

import streamlit as st
import toml

from src.common.consts import PROMPT_PER_CATEGORY_DIR
from src.utils.io import get_suffix


def load_prompt(file_path):
    prompt_dict = toml.load(file_path)
    # Temporary add the new element(example) for exist file
    if prompt_dict.get("example") is None:
        prompt_dict["example"] = ""
    return prompt_dict


def reset_prompt_per_category_dict():
    prompt_per_category_dict = {}
    prompt_per_category_file_paths = sorted(PROMPT_PER_CATEGORY_DIR.glob("*.toml"), key=lambda file: file.name)
    for file_path in prompt_per_category_file_paths:
        prompt_dict = load_prompt(file_path)
        category_id = file_path.stem  # Gets the file name without extension
        prompt_per_category_dict[category_id] = prompt_dict
    st.session_state["prompt_per_category_dict"] = prompt_per_category_dict


reset_prompt_per_category_dict()


def reset_category_id_to_name_ko_dict():
    st.session_state["category_id_to_name_ko_dict"] = {
        k: v["category_name_ko"] for k, v in st.session_state["prompt_per_category_dict"].items()
    }


def reset_category_strenum():
    st.session_state["Category"] = StrEnum("Category", {k: k for k in st.session_state["prompt_per_category_dict"]})
    # class Category(StrEnum):
    #     communication: str = auto()


def reset_all_category_info():
    reset_prompt_per_category_dict()
    reset_category_id_to_name_ko_dict()
    reset_category_strenum()


@dataclass
class SubScoreResult:
    subscores: list[int]
    descrpition: str
    num_score: int = field(init=False, default=10)

    def __post_init__(self):
        assert len(self.subscores) == self.num_score, "Subscores should have {self.num_score} elements"

    @property
    def total_score(self):
        return sum(self.subscores)


@dataclass
class SubScoreResult1(SubScoreResult):
    num_score = 6


@dataclass
class SubScoreResult2(SubScoreResult):
    num_score = 4


@dataclass
class SubScoreResult3(SubScoreResult):
    num_score = 3


@dataclass
class ScoreResult:
    subscore_results: tuple[SubScoreResult1, SubScoreResult2, SubScoreResult3]
    content: str
    created_at: Optional[str] = None

    @property
    def total_score(self):
        return sum([subscore_result.total_score for subscore_result in self.subscore_results])


@dataclass
class ReportFile:
    name: str
    content: str

    def __post_init__(self):
        self.name = self.name.strip()
        self.content = self.content.strip()
        self.extension = get_suffix(self.name)


class ReportFileList(list):
    creted_at: Optional[int] = None

    def append(self, new_file: ReportFile):
        if any(existing_file.name == new_file.name for existing_file in self):
            raise ValueError(f"Filename '{new_file.name}' already exists.")
        super().append(new_file)

    def to_list_of_dict(self):
        return [report_file.__dict__ for report_file in self]


@dataclass
class Result:
    content: str
    name: Optional[str] = None
    created_at: Optional[str] = None
