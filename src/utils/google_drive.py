import io
from io import BytesIO
from pathlib import Path

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

from src import GOOGLE_DRIVE_SERVICE_SECRETS, logger
from src.common.consts import GD_BASE_FOLDER_ID, PROMPT_PER_CATEGORY_DIR


class GoogleDriveHelper:
    def __init__(self, base_folder_id) -> None:
        self.credentials = service_account.Credentials.from_service_account_info(
            GOOGLE_DRIVE_SERVICE_SECRETS, scopes=["https://www.googleapis.com/auth/drive"]
        )
        self.service = build("drive", "v3", credentials=self.credentials)
        self.base_folder_id = base_folder_id

    def create_folder(self, folder_name, parent_folder_id=None):
        parent_folder_id = parent_folder_id or self.base_folder_id
        file_metadata = {
            "name": folder_name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [parent_folder_id],
        }
        folder = self.service.files().create(body=file_metadata, fields="id").execute()
        return folder.get("id")

    def upload(self, filename, content, encoding="utf-8", folder_id=None):
        folder_id = folder_id or self.base_folder_id
        file_metadata = {"name": filename, "parents": [folder_id]}

        if isinstance(content, str):
            media = MediaIoBaseUpload(BytesIO(content.encode(encoding)), mimetype="text/plain", resumable=True)
        else:
            media = MediaIoBaseUpload(BytesIO(content), mimetype="application/octet-stream", resumable=True)

        file = self.service.files().create(body=file_metadata, media_body=media, fields="id, webViewLink").execute()
        return file

    def get_file_list(self, folder_id=None):
        folder_id = folder_id or self.base_folder_id
        query = f"'{folder_id}' in parents and trashed = false"
        results = self.service.files().list(q=query, fields="files(id, name, mimeType, webViewLink)").execute()
        return results.get("files", [])

    def set_permission(self, file_id, email, role="reader"):
        permission = {"type": "user", "role": role, "emailAddress": email}
        return self.service.permissions().create(fileId=file_id, body=permission, sendNotificationEmail=False).execute()

    def get_file_id(self, filename, folder_id=None):
        folder_id = folder_id or self.base_folder_id
        query = f"name = '{filename}' and '{folder_id}' in parents and trashed = false"
        results = self.service.files().list(q=query, fields="files(id, name)").execute()
        files = results.get("files", [])

        if not files:
            raise ValueError(f"File '{filename}' not found in folder {folder_id}")
        if len(files) > 1:
            raise ValueError(f"Multiple files named '{filename}' found in folder {folder_id}")

        return files[0]["id"]

    def get_file_url(self, filename, folder_id=None):
        file_id = self.get_file_id(filename, folder_id)
        return f"https://drive.google.com/file/d/{file_id}/view?usp=sharing"

    def get_file_name_ids(self, folder_id=None):
        folder_id = folder_id or self.base_folder_id
        query = f"'{folder_id}' in parents and trashed = false"
        results = self.service.files().list(q=query, fields="files(id, name)").execute()
        files = results.get("files", [])
        return [{"name": file["name"], "id": file["id"]} for file in files]

    def download(self, file_id, target_path):
        """
        Google Drive의 파일을 로컬에 다운로드합니다.

        Args:
            file_id (str): 다운로드할 파일의 Google Drive ID
            target_path (str|Path): 파일을 저장할 로컬 경로

        Returns:
            Path: 다운로드된 파일의 경로
        """
        target_path = Path(target_path)

        try:
            # 파일 메타데이터 가져오기
            request = self.service.files().get_media(fileId=file_id)

            # 파일 다운로드를 위한 BytesIO 객체 생성
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)

            # 파일 다운로드 실행
            done = False
            while done is False:
                status, done = downloader.next_chunk()

            # 파일 저장
            fh.seek(0)
            target_path.parent.mkdir(parents=True, exist_ok=True)
            with open(target_path, "wb") as f:
                f.write(fh.read())

            return target_path

        except Exception as e:
            raise Exception(f"Error downloading file {file_id}: {str(e)}")

    def move(self, file_id, new_folder_id):
        """
        파일을 다른 폴더로 이동합니다.

        Args:
            file_id (str): 이동할 파일의 ID
            new_folder_id (str): 대상 폴더의 ID
        """
        try:
            # 현재 파일의 부모 폴더들을 가져옵니다
            file = self.service.files().get(fileId=file_id, fields="parents").execute()

            # 이전 부모 폴더들을 제거하고 새 폴더를 추가합니다
            previous_parents = ",".join(file.get("parents", []))
            file = (
                self.service.files()
                .update(fileId=file_id, addParents=new_folder_id, removeParents=previous_parents, fields="id, parents")
                .execute()
            )

            return file

        except Exception as e:
            raise Exception(f"Error moving file {file_id} to folder {new_folder_id}: {str(e)}")

    def upload_byte_obj(self, filename, byte_obj, folder_id=None):
        """
        바이트 객체를 Google Drive에 업로드합니다.

        Args:
            filename (str): 업로드될 파일의 이름
            byte_obj (bytes): 업로드할 바이트 객체
            folder_id (str, optional): 업로드할 폴더 ID. None이면 base_folder_id 사용

        Returns:
            dict: 업로드된 파일의 정보
            {'id': '1Mig6UxKFaL8YVmP-07nCTMOBMouVVs1x',
            'name': 'report_241123_234249.xlsx',
            'webViewLink': 'https://docs.google.com/spreadsheets/~~'}
        """
        folder_id = folder_id or self.base_folder_id

        try:
            # 파일 메타데이터 설정
            file_metadata = {"name": filename, "parents": [folder_id]}

            # 바이트 객체를 MediaIoBaseUpload로 변환
            media = MediaIoBaseUpload(BytesIO(byte_obj), mimetype="application/octet-stream", resumable=True)

            # 파일 업로드 실행
            file = (
                self.service.files()
                .create(body=file_metadata, media_body=media, fields="id, name, webViewLink")
                .execute()
            )

            return file

        except Exception as e:
            raise Exception(f"Error uploading file {filename}: {str(e)}")


"""
GD_BASE_FOLDER: admin에게 edit 권한
├── prompt
│   └── archive
└── ssk_gpt_manager: manager에게 view 권한
    ├── result
    └── docs: manager에게 edit 권한 
        └── manual (file)
"""

gd_helper_base = GoogleDriveHelper(GD_BASE_FOLDER_ID)
GD_PROMPT_FOLDER_ID = gd_helper_base.get_file_id("prompt")
GD_PROMPT_ARCHIVE_FOLDER_ID = gd_helper_base.get_file_id("archive", folder_id=GD_PROMPT_FOLDER_ID)
GD_MANAGER_FOLDER_ID = gd_helper_base.get_file_id("ssk_gpt_manager")
GD_RESULT_FOLDER_ID = gd_helper_base.get_file_id("result", folder_id=GD_MANAGER_FOLDER_ID)
GD_DOCS_FOLDER_ID = gd_helper_base.get_file_id("docs", folder_id=GD_MANAGER_FOLDER_ID)
GD_DOCS_FILE_URL = gd_helper_base.get_file_url("manual", folder_id=GD_DOCS_FOLDER_ID)

logger.info(f"Start to download prompt files from Google Drive: {GD_PROMPT_FOLDER_ID}")
for name_id in gd_helper_base.get_file_name_ids(GD_PROMPT_FOLDER_ID):
    name, id = name_id["name"], name_id["id"]
    if Path(name).suffix == ".toml":
        gd_helper_base.download(id, PROMPT_PER_CATEGORY_DIR / name)
        logger.info(f"Complete to download prompt file: {name}")

# gd_helper_prompt = GoogleDriveHelper(GD_PROMPT_FOLDER_ID)


def get_prompt_folder_id_in_gd():
    return GD_PROMPT_FOLDER_ID
    # date_str = gd_helper_prompt.get_server_start_datetime_str()
    # try:
    #     return gd_helper_prompt.get_file_id(filename=date_str)

    # except ValueError:
    #     prompt_folder_in_gd = gd_helper_prompt.create_folder(date_str)
    #     logger.info(f"Create new prompt folder in Google Drive: {date_str}")
    #     return prompt_folder_in_gd["id"]
