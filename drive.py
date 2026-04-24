import io
import streamlit as st
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload


def _get_service(creds):
    return build("drive", "v3", credentials=creds)


def upload_image(creds, file_bytes: bytes, filename: str) -> str:
    folder_id = st.secrets["google"]["drive_folder_id"]
    service = _get_service(creds)

    metadata = {"name": filename, "parents": [folder_id]}
    media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype="image/jpeg")

    file = service.files().create(
        body=metadata,
        media_body=media,
        fields="id",
    ).execute()

    file_id = file["id"]

    service.permissions().create(
        fileId=file_id,
        body={"type": "anyone", "role": "reader"},
    ).execute()

    return f"https://drive.google.com/uc?id={file_id}"
