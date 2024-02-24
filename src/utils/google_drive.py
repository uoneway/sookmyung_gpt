from io import BytesIO
from pathlib import Path

from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive

from src import GOOGLE_DRIVE_SERVICE_SECRETS, logger
from src.common.consts import GD_BASE_FOLDER_ID, PROMPT_PER_CATEGORY_DIR


class GoogleDriveHelper:
    client_json_dict = GOOGLE_DRIVE_SERVICE_SECRETS

    def __init__(self, base_folder_id) -> None:
        self.gauth = self.login_with_service_account()
        self.drive = GoogleDrive(self.gauth)
        self.base_folder_id = base_folder_id
        self.base_folder = self.get_file(self.base_folder_id)

    @staticmethod
    def login_with_service_account():
        """
        https://docs.iterative.ai/PyDrive2/oauth/#authentication-with-a-service-account
        https://rclone.org/drive/#making-your-own-client-id

        웹브라우저를 통해서가 아닌 자동 인증을 받기 위해서는 서비스 계정을 사용해야 한다.
        그런데 이렇게 하면 해당 서비스 계정에 해당되는 구글드라이브에 업로드 되어 모든 제어를 API를 통해 해야함
        -> 해당 폴더를 다른 계정과 공유하여 이용하는 방식으로 해결

        Google Drive service with a service account.
        note: for the service account to work, you need to share the folder or
        files with the service account email.

        :return: google auth
        """
        # Define the settings dict to use a service account
        # We also can use all options available for the settings dict like
        # oauth_scope,save_credentials,etc.
        settings = {
            "client_config_backend": "service",
            "service_config": {
                "client_json_dict": GoogleDriveHelper.client_json_dict,
            },
        }
        # Create instance of GoogleAuth
        gauth = GoogleAuth(settings=settings)
        # Authenticate
        gauth.ServiceAuth()
        return gauth

    def decide_folder_id(self, folder_id=None):
        if folder_id is None:
            folder_id = self.base_folder_id
        return folder_id

    def create_folder(self, subfolder_name, parent_folder_id=None):
        parent_folder_id = self.decide_folder_id(parent_folder_id)

        metadata = {
            "title": subfolder_name,
            "parents": [{"kind": "drive#fileLink", "id": parent_folder_id}],
            "mimeType": "application/vnd.google-apps.folder",
        }
        folder = self.drive.CreateFile(metadata=metadata)
        folder.Upload()
        return folder

    def move(self, id, tgt_folder_id):
        file = self.get_file(id)
        file["parents"] = [{"kind": "drive#fileLink", "id": tgt_folder_id}]
        file.Upload()

    def upload(self, filename, content, encoding="utf-8", folder_id=None):
        folder_id = self.decide_folder_id(folder_id)

        file = self.drive.CreateFile({"title": filename, "parents": [{"kind": "drive#fileLink", "id": folder_id}]})
        file.SetContentString(content, encoding=encoding)
        file.Upload()

        return file

    def upload_byte_obj(self, filename, byte_obj, folder_id=None):
        folder_id = self.decide_folder_id(folder_id)

        # 이미 바이트 객체인 경우, 직접 사용
        file_stream = BytesIO(byte_obj)
        file = self.drive.CreateFile({"title": filename, "parents": [{"kind": "drive#fileLink", "id": folder_id}]})

        # 바이트 스트림으로 내용 설정
        file.content = file_stream
        file.Upload()

        return file

    # def upload(self, filename, content, folder_id=None):
    #     folder_id = self.decide_folder_id(folder_id)

    #     metadata = {
    #         "parents": [{"kind": "drive#fileLink", "id": folder_id}],
    #         "title": filename,
    #         # 'mimeType': 'image/jpeg'
    #     }
    #     file = self.drive.CreateFile(metadata=metadata)
    #     # if Path(content_or_path).exists():
    #         file.SetContentFile(content_or_path)
    #     # else:
    #     file.SetContentString(content)
    #     file.Upload()

    def update_file_with_id(self, file_id, content):
        file = self.get_file(file_id)
        file.SetContentString(content)
        file.Upload()

    def update_file_with_name(self, filename, content, folder_id=None):
        folder_id = self.decide_folder_id(folder_id)
        file_id = self.get_file_id(filename, folder_id)

        self.update_file_with_id(file_id, content)

    def download(self, file_id, filename):
        file = self.drive.CreateFile({"id": file_id})
        file.GetContentFile(filename)
        return file

    def get_file(self, file_id):
        return self.drive.CreateFile({"id": file_id})

    def get_file_list(self, folder_id=None):
        folder_id = self.decide_folder_id(folder_id)

        query = f"'{folder_id}' in parents and trashed = false"
        return self.drive.ListFile({"q": query}).GetList()

    def get_file_name_ids(self, folder_id=None):
        folder_id = self.decide_folder_id(folder_id)

        return [{"name": file["title"], "id": file["id"]} for file in self.get_file_list(folder_id)]

    def get_folder_list(self, folder_id=None):
        folder_id = self.decide_folder_id(folder_id)

        query = f"'{folder_id}' in parents and trashed = false and mimeType = 'application/vnd.google-apps.folder'"
        return self.drive.ListFile({"q": query}).GetList()

    def delete(self, file_id):
        file = self.get_file(file_id)
        file.Delete()

    def delete_all(self, folder_id=None):
        folder_id = self.decide_folder_id(folder_id)

        file_list = self.get_file_list(folder_id)
        for file in file_list:
            self.delete(file["id"])

    def set_permission(self, id, permission_type="anyone", permission_role="reader", permission_value="anyone"):
        file = self.get_file(id)
        permission = file.InsertPermission(
            {"type": permission_type, "role": permission_role, "value": permission_value}
        )
        return permission

    def allow_access(self, email):
        # 폴더 등록 & 초대 이메일 전송
        self.set_permission(
            self.base_folder_id, permission_type="user", permission_role="writer", permission_value=email
        )

    def get_file_id(self, filename, folder_id=None):
        folder_id = self.decide_folder_id(folder_id)

        query = f"title = '{filename}' and '{folder_id}' in parents and trashed = false"
        file_list = self.drive.ListFile({"q": query}).GetList()
        if len(file_list) != 1:
            raise ValueError(f"File '{filename}' does not exist in the {folder_id} folder of google drive.")

        return file_list[0]["id"]

    def get_file_url_from_id(self, file_id):
        return f"https://drive.google.com/file/d/{file_id}/view?usp=sharing"

    def get_file_url(self, filename, folder_id=None):
        folder_id = self.decide_folder_id(folder_id)

        file_id = self.get_file_id(filename, folder_id)
        return self.get_file_url_from_id(file_id)

    def get_folder_url(self, folder_id=None):
        folder_id = self.decide_folder_id(folder_id)

        return f"https://drive.google.com/drive/folders/{folder_id}?usp=sharing"

    def get_folder_url_from_filename(self, filename, folder_id=None):
        folder_id = self.decide_folder_id(folder_id)

        file_id = self.get_file_id(filename, folder_id)
        return self.get_folder_url(file_id)

    # @staticmethod
    # def get_server_start_datetime_str():
    #     """SERVER_START_DATE_FILE 존재하면 읽고, 없으면 현재 날짜를 기록하고 읽음"""
    #     if os.path.exists(SERVER_START_DATETIME_FILE):
    #         with open(SERVER_START_DATETIME_FILE, "r") as file:
    #             date_str = file.read().strip()
    #     else:
    #         logger.warning(f"{SERVER_START_DATETIME_FILE} does not exist. Create new file and write current date.")
    #         date_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    #         with open(SERVER_START_DATETIME_FILE, "w") as file:
    #             file.write(date_str)
    #     return date_str


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
