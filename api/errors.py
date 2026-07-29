"""結構化 API 錯誤。"""

from __future__ import annotations


class ApiError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def file_not_found(file_id: str) -> ApiError:
    return ApiError(404, "FILE_NOT_FOUND", f"找不到檔案或已過期: {file_id}")


def unauthorized_file(file_id: str) -> ApiError:
    return ApiError(403, "UNAUTHORIZED_FILE", f"無權使用此檔案: {file_id}")


def job_not_found(job_id: str) -> ApiError:
    return ApiError(404, "JOB_NOT_FOUND", f"找不到任務: {job_id}")


def invalid_url(message: str) -> ApiError:
    return ApiError(400, "INVALID_URL", message)
