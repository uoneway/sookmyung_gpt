from dataclasses import dataclass, field
from typing import Optional

from src.processor.reader import get_suffix


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
