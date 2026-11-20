"""The photo formats the app accepts, and the file extension each one gets.

To support a new format, change it here: uploads and export filenames both use this.
"""

from typing import Literal

ContentType = Literal["image/jpeg", "image/png"]

EXTENSIONS: dict[ContentType, str] = {"image/jpeg": "jpg", "image/png": "png"}
