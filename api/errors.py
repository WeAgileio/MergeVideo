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


def script_required() -> ApiError:
    return ApiError(400, "SCRIPT_REQUIRED", "請提供文字稿 script")


def script_empty() -> ApiError:
    return ApiError(400, "SCRIPT_EMPTY", "文字稿不可為空白")


def script_too_long(max_chars: int) -> ApiError:
    return ApiError(400, "SCRIPT_TOO_LONG", f"文字稿超過上限 {max_chars} 字")


def wrong_file_type(message: str) -> ApiError:
    return ApiError(400, "WRONG_FILE_TYPE", message)


def invalid_margin(message: str) -> ApiError:
    return ApiError(400, "INVALID_MARGIN", message)


def invalid_font_size(message: str) -> ApiError:
    return ApiError(400, "INVALID_FONT_SIZE", message)
