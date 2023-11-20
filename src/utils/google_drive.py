from io import BytesIO

from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive

from src import GOOGLE_DRIVE_SERVICE_SECRETS
from src.common.consts import base_folder_id


class GoogleDriveHelper:
    client_json_dict = GOOGLE_DRIVE_SERVICE_SECRETS
    base_folder_id = base_folder_id

    def __init__(self) -> None:
        self.gauth = self.login_with_service_account()
        self.drive = GoogleDrive(self.gauth)
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

    def create_folder(self, subfolder_name, folder_id=None):
        folder_id = self.decide_folder_id(folder_id)

        metadata = {
            "title": subfolder_name,
            "parents": [{"kind": "drive#fileLink", "id": folder_id}],
            "mimeType": "application/vnd.google-apps.folder",
        }
        folder = self.drive.CreateFile(metadata=metadata)
        folder.Upload()
        return folder

    def upload_str_obj(self, filename, str_obj, encoding, folder_id=None):
        folder_id = self.decide_folder_id(folder_id)

        file = self.drive.CreateFile({"title": filename, "parents": [{"kind": "drive#fileLink", "id": folder_id}]})

        # 이미 바이트 객체인 경우, 직접 사용
        file.SetContentString(str_obj, encoding=encoding)
        file.Upload()

        return file

    def upload_byte_obj(self, filename, byte_obj, folder_id=None):
        folder_id = self.decide_folder_id(folder_id)

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
        assert len(file_list) == 1, f"len(file_list) == 1, but {len(file_list)}"
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
