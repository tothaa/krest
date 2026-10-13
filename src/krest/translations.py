#!/usr/bin/env python3

import json
import locale
from importlib.resources import files


def new_text_id():
    """Generates unique text IDs like #TEXT1#, #TEXT2#, etc."""
    if not hasattr(new_text_id, "count"):
        new_text_id.count = 0
    new_text_id.count += 1
    return f"#TEXT_{new_text_id.count}#"


class T:
    """
    Translator

    Fetch translation for given key in selected language.
    Falls back to English if the language is missing or unsupported.
    Returns unknown keys unchanged.
    Catalogs are UTF-8 JSON objects in locales/<language>.json, with
    translation constant names (such as REPLY_NAME) as their keys.

    Usage:
    '''python
        from krest.translations import t
        t.set_lang("en")
        print(t(t.REPLY_NAME, name="User"))
    '''

    Note: you can pass the substitution strings as named arguments.

    """

    ###   Translation Keys   ###
    REPLY_NAME = new_text_id()
    K_USER = new_text_id()
    BASICAUTH_DESC = new_text_id()
    DIGESTAUTH_DESC = new_text_id()
    OAUTH_DESC = new_text_id()
    ERR_MISSING_FILEPATH = new_text_id()
    ERR_NODATA = new_text_id()
    ERR_MAGICBYTES = new_text_id()
    ERR_INVALID_PASSWD = new_text_id()
    ERR_INVALID_ENDPOINT_ID = new_text_id()
    TOKEN_REQUEST = new_text_id()
    ERR_ACCESS_TOKEN = new_text_id()
    SERVICE_REQUEST = new_text_id()
    CLOSE = new_text_id()
    ABOUT = new_text_id()
    MOTTO = new_text_id()
    AUTHOR = new_text_id()
    EMAIL = new_text_id()
    LICENSE = new_text_id()
    OK = new_text_id()
    CALL_HISTORY_DETAILS = new_text_id()
    ERROR = new_text_id()
    INFORMATION = new_text_id()
    ID = new_text_id()
    CALL_TYPE = new_text_id()
    ENDPOINT_ID = new_text_id()
    RUN_DATE = new_text_id()
    RESPONSE_HAS_REDIRECT_LOCATION = new_text_id()
    RESPONSE_STATUS_CODE = new_text_id()
    RESPONSE_REASON_PHRASE = new_text_id()
    RESPONSE_HTTP_VERSION = new_text_id()
    RESPONSE_ENCODING = new_text_id()
    RESPONSE_CHARSET_ENCODING = new_text_id()
    ELAPSED_TIME = new_text_id()
    RESPONSE_CONTENT_LENGTH = new_text_id()
    RESPONSE_LINKS = new_text_id()
    HEADERS = new_text_id()
    RESPONSE_BODY = new_text_id()
    COOKIES = new_text_id()
    ENDPOINT_DETAILS = new_text_id()
    CREDENTIAL_DETAILS = new_text_id()
    REFRESH_HISTORY = new_text_id()
    CALL_HISTORY = new_text_id()
    ERR_NO_ROW_SELECTED = new_text_id()
    CANCEL = new_text_id()
    ENDPOINT_EDITOR = new_text_id()
    NAME = new_text_id()
    DESC = new_text_id()
    CREDENTIAL = new_text_id()
    METHOD = new_text_id()
    URL = new_text_id()
    PARAMS = new_text_id()
    TIMEOUT = new_text_id()
    ALLOW_REDIRECTS = new_text_id()
    LABELS = new_text_id()
    BODY = new_text_id()
    APPLY = new_text_id()
    ERR_PARAM_FORMAT = new_text_id()
    ERR_PARAM_STR = new_text_id()
    ERR_LABELS_FORMAT = new_text_id()
    ERR_LABELS_STR = new_text_id()
    ERR_HEADERS_FORMAT = new_text_id()
    ERR_HEADERS_STR = new_text_id()
    PFE = new_text_id()
    EDITOR = new_text_id()
    DATA_UPD = new_text_id()
    YES = new_text_id()
    NO = new_text_id()
    CONFIRM = new_text_id()
    CONFIRMATION = new_text_id()
    SEL_DIR = new_text_id()
    SEL_FILE = new_text_id()
    SEL = new_text_id()
    NEW = new_text_id()
    OPEN = new_text_id()
    FILE_PRMT = new_text_id()
    FILE_NAME = new_text_id()
    BROWSE = new_text_id()
    PASSWORD = new_text_id()
    TOKEN_URL = new_text_id()
    CLIENT_ID = new_text_id()
    CLIENT_SECRET = new_text_id()
    CREDENTIAL_EDITOR = new_text_id()
    CREDENTIAL_TYPE = new_text_id()
    ERR_CREDENTIAL_TYPE = new_text_id()
    REFRESH_CREDENTIALS = new_text_id()
    MODIFY_CREDENTIAL = new_text_id()
    NEW_CREDENTIAL = new_text_id()
    MODIFY = new_text_id()
    NO_UPD = new_text_id()
    ERR_NO_FILE_SELECTED = new_text_id()
    SAVE = new_text_id()
    QUIT = new_text_id()
    NEW_ENDPOINT = new_text_id()
    EXECUTE = new_text_id()
    DELETE = new_text_id()
    ALL_CALL_HISTORIES = new_text_id()
    DATA_DLTD = new_text_id()
    CONFIRM_DELETE = new_text_id()
    RUN_SUCCESS = new_text_id()
    NOTE_UNSAVED_CHANGES = new_text_id()
    FILE_SAVED = new_text_id()
    FILE_CREATED = new_text_id()
    FILE_NOSAVE = new_text_id()
    FILE_EXISTS = new_text_id()
    FILE_LOADED = new_text_id()
    MANAGE_CREDENTIALS = new_text_id()
    USERNAME = new_text_id()
    FILE = new_text_id()
    ############################

    @staticmethod
    def system_lang() -> str | None:
        lang, _ = locale.getlocale()
        print(f"System Language is {lang}.")
        return lang

    def __init__(self):
        self._current_lang = "en"
        self._data: dict[str, str] | None = None

    def _load_language(self, lang: str) -> dict[str, str] | None:
        # Keep locale names within the package's resource directory.
        if not lang.isidentifier():
            return None
        resource = files(__package__).joinpath("locales", f"{lang}.json")
        if not resource.is_file():
            return None
        messages = json.loads(resource.read_text(encoding="utf-8"))
        return {getattr(self, name): text for name, text in messages.items()}

    def set_lang(self, lang: str | None):
        print(f"set_lang: Requested Language: {lang}.")
        requested = lang.replace("-", "_") if lang else "en"
        candidates = dict.fromkeys((requested, requested.split("_")[0], "en"))
        for candidate in candidates:
            if candidate == self._current_lang and self._data is not None:
                return
            data = self._load_language(candidate)
            if data is not None:
                self._current_lang = candidate
                self._data = data
                print(f"set_lang: Language set to {candidate}.")
                return
        raise FileNotFoundError("English translation file locales/en.json is missing.")

    def __call__(self, key: str | None, **kwargs) -> str:
        if self._data is None:
            self.set_lang(self._current_lang)
        text = self._data.get(key, key)
        return text.format(**kwargs) if kwargs else text


t = T()
t.set_lang(t.system_lang())
