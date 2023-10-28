import re
import struct
import zlib
from pathlib import Path
from typing import IO, Optional

import olefile
from unstructured.partition.auto import partition


class RegPat:
    TO_REMOVE_CHAR = re.compile(r"\xa0|[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")  # ASCII_CONTROL 문자 등
    DUPLICATED_EXP = re.compile(r"([^a-zA-Z가-힣0-9_\n\-\.\*\\])\1+")
    STRIP_SPACE_with_OTHER_WS = re.compile(r" *([\t\n\r\f\v]) *")
    LINE_BREAK_TRIPLE = re.compile(r"\n{3,}")
    NUMBER_SEQUENCE_3_MORE = re.compile(r"(?:\(?[-+]?\d*,?\d*[.]?\d+\)?\s+){2,}\(?[-+]?\d*,?\d*[.]?\d+\)?")


def clean_text(text, verbose=False):
    """Clean the extracted text."""
    if verbose:
        text_orig = text
    text = RegPat.TO_REMOVE_CHAR.sub(" ", text)  # ASCII 제어 문자 제거
    text = RegPat.DUPLICATED_EXP.sub(r"\1", text)  # 여기서 동일 유형의 white space 중복 제거도 시행
    text = RegPat.STRIP_SPACE_with_OTHER_WS.sub(r"\1", text)  # " "와 다른 유형의 white space가 붙어 있으면 " "를 제거
    text = RegPat.LINE_BREAK_TRIPLE.sub(r"\n\n", text)  # " "와 다른 유형의 white space가 붙어 있으면 " "를 제거
    text = text.rstrip()  # 왼쪽 공백은 삭제하지 않음. 들여쓰기 의미가 있을 수 있어서

    if verbose and (text != text_orig):
        print(f"#Original: {text_orig}")
        print(f"#Cleaned : {text}")
        print()
    return text


class FileReader(object):
    def __init__(
        self,
        filepath: Optional[Path] = None,
        file: Optional[IO[bytes]] = None,
        filetype: str = None,
        clean=False,
        verbose=False,
    ):
        self.filepath = None
        assert (filepath or file) and not (filepath and file), "Either filepath or file should be given, not both."
        if filepath is not None:
            self.filepath = Path(filepath)
            self.file = open(filepath, "rb")
            self.filetype = get_suffix(filepath)
        if file is not None:
            assert filetype is not None, "filetype should be given when file is given."
            self.file = file
            self.filetype = filetype

        self.clean = clean
        self.verbose = verbose

        self.text = self.extract_text()
        self.word_count = self.calculate_word_count() if self.text else 0
        self.char_count = self.calculate_char_count() if self.text else 0

    def extract_text(self):
        try:
            match self.filetype:
                case ".txt":
                    text_list = [line.decode("utf-8").strip() for line in self.file]

                case ".hwp":
                    text_list = HWPReader(self.file).text_list
                case ".docx" | ".pdf":
                    """
                    Plaintext: .eml, .html, .json, .md, .msg, .rst, .rtf, .txt, .xml
                    Images: .jpeg, .png
                    Documents: .csv, .doc, .docx, .epub, .odt, .pdf, .ppt, .pptx, .tsv, .xlsx

                    Text: FigureCaption, NarrativeText, ListItem, Title, Address, Table,
                        PageBreak, Header, Footer, EmailAddress
                    CheckBox
                    Image

                    """
                    # try:
                    # elements = partition(filename=str(self.filepath))
                    elements = partition(file=self.file)

                    text_list = []
                    for elem in elements:
                        if elem.category in ["Image", "PageBreak"]:
                            continue
                        if elem.category in ["Table", "Header", "Footer"]:
                            if self.verbose:
                                print("Deleted:", elem.category, elem.text)
                            continue

                        text_list.append(elem.text)

                case _:  # ".doc"
                    raise Exception(f"{self.filetype} is not supported")

            self.file.close()

        except Exception as e:
            print(f"Cannot extract text from file: {self.filepath if self.filepath else self.file}. {e}")
            return None

        if self.clean:
            text_list_cleaned = []
            for text in text_list:
                text = clean_text(text, self.verbose)
                if text:
                    text_list_cleaned.append(text)
        else:
            text_list_cleaned = text_list

        text = "\n".join(text_list_cleaned)
        # 표 숫자는 줄바꿈도
        if self.clean:
            text = RegPat.NUMBER_SEQUENCE_3_MORE.sub(" ", text)

        if not text:
            if "\n".join(text_list):
                print(f"All str in the doc is cleaned:\n{text_list}")
            else:
                print(f"Empty text: {self.filepath}")
        return text

    def calculate_word_count(self):
        """Calculate word count from the extracted text."""

        return len(self.text.split())

    def calculate_char_count(self):
        """Calculate character count from the extracted text."""
        return len(self.text)

    def summary(self):
        """Return a summary with the first 1000 characters of the extracted text and the counts."""
        return {"text": self.text[:1000], "char_count": self.char_count, "word_count": self.word_count}


class HWPReader(object):
    FILE_HEADER_SECTION = "FileHeader"
    HWP_SUMMARY_SECTION = "\x05HwpSummaryInformation"
    SECTION_NAME_LENGTH = len("Section")
    BODYTEXT_SECTION = "BodyText"
    HWP_TEXT_TAGS = [67]

    def __init__(self, filepath_or_fileio):
        self._ole = self.load(filepath_or_fileio)
        self._dirs = self._ole.listdir()

        self._valid = self.is_valid(self._dirs)
        if self._valid == False:
            raise Exception("Not Valid HwpFile")

        self._compressed = self.is_compressed(self._ole)
        self.text_list = self._get_text_list()
        self.text = self._get_text()

    # 파일 불러오기
    def load(self, filepath_or_fileio):
        return olefile.OleFileIO(filepath_or_fileio)

    # hwp 파일인지 확인 header가 없으면 hwp가 아닌 것으로 판단하여 진행 안함
    def is_valid(self, dirs):
        if [self.FILE_HEADER_SECTION] not in dirs:
            return False

        return [self.HWP_SUMMARY_SECTION] in dirs

    # 문서 포맷 압축 여부를 확인
    def is_compressed(self, ole):
        header = self._ole.openstream("FileHeader")
        header_data = header.read()
        return (header_data[36] & 1) == 1

    # bodytext의 section들 목록을 저장
    def get_body_sections(self, dirs):
        m = []
        for d in dirs:
            if d[0] == self.BODYTEXT_SECTION:
                m.append(int(d[1][self.SECTION_NAME_LENGTH :]))

        return ["BodyText/Section" + str(x) for x in sorted(m)]

    def get_text_list(self):
        return self.text_list

    def _get_text_list(self):
        sections = self.get_body_sections(self._dirs)
        text_list = [self.get_text_from_section(section) for section in sections]
        return text_list

    # text를 뽑아내는 함수
    def get_text(self):
        return self.text

    # 전체 text 추출
    def _get_text(self):
        text = "\n".join(self.text_list)
        self.text = text
        return self.text

    # section 내 text 추출
    def get_text_from_section(self, section):
        bodytext = self._ole.openstream(section)
        data = bodytext.read()
        unpacked_data = zlib.decompress(data, -15) if self.is_compressed else data
        size = len(unpacked_data)

        i = 0

        text = ""
        while i < size:
            header = struct.unpack_from("<I", unpacked_data, i)[0]
            rec_type = header & 0x3FF
            level = (header >> 10) & 0x3FF
            rec_len = (header >> 20) & 0xFFF

            if rec_type in self.HWP_TEXT_TAGS:
                rec_data = unpacked_data[i + 4 : i + 4 + rec_len]
                decoded_text = rec_data.decode("utf-16")

                cleaned_text = re.sub(r"[\x00-\x1F\x7F-\x9F]", "", decoded_text)
                # if decoded_text != cleaned_text:
                #     print(decoded_text)
                #     print(cleaned_text)
                # print(cleaned_text)
                text += cleaned_text + "\n"

            i += 4 + rec_len

        return text


def get_suffix(path: str | Path):
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
