#!/usr/bin/env python3

import gc
from typing import Iterable, AnyStr, Literal
from importlib.metadata import version
import traceback
import ast
import json
from pathlib import Path
from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Vertical, Horizontal
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import DirectoryTree, Static, Button, Footer, Header, Label, Input, TextArea, DataTable, Select, Rule, Pretty
from textual import on
from textual import events

from krest.krest_backend import KrestBackend, METHODS, CredentialType, FILE_EXTENSION, developer_log, empty_endpoint, empty_credential
from krest.translations import t

ASCII_LOGO = r"""[blue]
  _  __              _
 | |/ /_ __ ___  ___| |_
 | ' /| '__/ _ \/ __| __|
 | . \| | |  __/\__ \ |_
 |_|\_\_|  \___||___/\__|
[/blue]"""

ERROR_NOTE_TIMEOUT = 15



def format_data_table(
        json_data,
        column_ordering_function=None,
        row_ordering_function=lambda x: x.get("id", ""),
        key="id",
        ignore_columns=[]
    ):
    # returns Columns and Records
    # expected input: list of dicts

    columns = []
    records = []
    keys = []

    for record in json_data:
        for column in record.keys():
            if column not in columns and column not in ignore_columns:
                columns.append(column)

    if column_ordering_function:
        columns = column_ordering_function(columns)

    if row_ordering_function:
        json_data.sort(key=row_ordering_function)

    for record in json_data:
        row = []
        for column in columns:
            row.append(str(record.get(column, "")))
        records.append(row)
        keys.append(record.get(key))

    return (columns, records, keys)


class LineDisplay(Widget):
    def __init__(self, label, value):
        super().__init__()
        self.label = label
        self.value = value

    def compose(self):
        with Horizontal(classes="input-row"):
            yield Label(str(self.label), classes="input-row-left")
            yield Label(str(self.value), classes="input-row-right")


class LineInput(Widget):
    def __init__(self, label, value, id, type: Literal["text", "integer", "number"]="text"):
        super().__init__()
        self.label = label
        self.value = value
        self.input_id = id
        self.type = type

    def compose(self):
        with Horizontal(classes="input-row"):
            yield Label(str(self.label) + ": ", classes="input-row-left")
            yield Input(value=str(self.value), id=self.input_id, classes="input-row-right", compact=True, type=self.type, placeholder=str(self.label))


class KrestDirectoryTree(DirectoryTree):
    def filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]:
        return [path for path in paths if path.is_dir() or path.suffix.lower() == "." + FILE_EXTENSION]


class FoldersDirectoryTree(DirectoryTree):
    def filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]:
        return [path for path in paths if path.is_dir()]


class About(ModalScreen):

    BINDINGS = [
        ("escape", "cancel_dialog", t(t.CLOSE))
    ]

    def compose(self) -> ComposeResult:
        dialog_content = Vertical(classes="dialog-container")
        dialog_content.styles.width = "50%"

        with dialog_content:
            yield Label(t(t.ABOUT), classes="title")
            yield Static(ASCII_LOGO, classes="ascii-logo")
            #yield Label("Krest TUI", classes="about-app-name")
            yield Label(f"v{version('krest-utils')}", classes="version-tag")
            yield Label(t(t.MOTTO), classes="tagline")

            yield Static("", classes="separator")
            yield Label("[b]" + t(t.AUTHOR) + ":[/b] András Tóth")
            yield Label("[b]" + t(t.EMAIL) + ":[/b] tothaa@hotmail.com")
            yield Label("[b]" + t(t.LICENSE) + ":[/b] GNU GPL v2.0")
            yield Label("[b]GitHub:[/b] [blue] https://github.com/tothaa/krest [/blue]")
            yield Label("[b]Donate:[/b]")
            yield Label("[b]Donate via 4Fund:[/b] [blue] https://4fund.com/hu/vhynh2 [/blue]")
            yield Label("Alternatives:")
            yield Label("[b]Donate via GitHub:[/b] [blue] https://github.com/sponsors/tothaa [/blue]")
            yield Label("[b]Donate via Librepay:[/b] [blue] https://liberapay.com/tothaa [/blue]")
            yield Label("[b]Donate via ko-fi:[/b] [blue] https://ko-fi.com/tothaa [/blue]")
            yield Label("[b]Donate via PayPal:[/b] [blue] https://paypal.me/tothaaprojects [/blue]")
            yield Static("", classes="separator")
            yield Label("Powered by [bold magenta]Textual[/bold magenta] and [bold blue]httpx[/bold blue]", classes="credits")

            with Horizontal(classes="button-container"):
                yield Button(t(t.OK), variant="primary", id="about-cancel-btn")

    @on(Button.Pressed, "#about-cancel-btn")
    def action_cancel_dialog(self) -> None:
        self.dismiss()


class CallHistoryDetailsViewer(ModalScreen):

    BINDINGS = [
        ("escape", "cancel_dialog", t(t.CLOSE))
    ]

    def __init__(self, history_record:dict|None=None):
        super().__init__()
        self.history_record = {}
        if history_record:
            self.history_record = history_record


    def compose(self) -> ComposeResult:
        dialog_content = Vertical(classes="dialog-container")
        dialog_content.styles.width = "95%"
        #dialog_content.styles.height = "100%"

        with dialog_content:
            yield Label(t(t.CALL_HISTORY_DETAILS), classes="title")

            # json.dumps(history_record, indent=4)
            # yield TextArea(self.history_record_text, show_line_numbers=True, classes="height20")
            # yield Label("endpoint")
            # endpoint = json.dumps(self.history_record["endpoint"], indent=4)
            # yield TextArea(endpoint, show_line_numbers=True, classes="height20", language="json")
            # yield Pretty(self.history_record)

            yield LineDisplay(label=t(t.ID), value=self.history_record.get("id", ""))
            yield LineDisplay(label=t(t.CALL_TYPE), value=self.history_record.get("call_type", ""))
            yield LineDisplay(label=t(t.ENDPOINT_ID), value=self.history_record.get("endpoint_id", ""))
            yield LineDisplay(label=t(t.RUN_DATE), value=self.history_record.get("run_date", ""))
            yield LineDisplay(label=t(t.RESPONSE_HAS_REDIRECT_LOCATION), value=self.history_record.get("response_has_redirect_location", ""))
            yield LineDisplay(label=t(t.RESPONSE_STATUS_CODE), value=self.history_record.get("response_status_code", ""))
            yield LineDisplay(label=t(t.RESPONSE_REASON_PHRASE), value=self.history_record.get("response_reason_phrase", ""))
            yield LineDisplay(label=t(t.RESPONSE_HTTP_VERSION), value=self.history_record.get("response_http_version", ""))
            yield LineDisplay(label=t(t.RESPONSE_ENCODING), value=self.history_record.get("response_encoding", ""))
            yield LineDisplay(label=t(t.RESPONSE_CHARSET_ENCODING), value=self.history_record.get("response_charset_encoding", ""))
            yield LineDisplay(label=t(t.ELAPSED_TIME), value=self.history_record.get("elapsed_time", ""))
            yield LineDisplay(label=t(t.RESPONSE_CONTENT_LENGTH), value=self.history_record.get("response_content_length", ""))
            yield LineDisplay(label=t(t.RESPONSE_LINKS), value=self.history_record.get("response_links", ""))

            yield Label(t(t.HEADERS))
            headers = json.dumps(self.history_record["response_headers"], indent=4)
            yield TextArea(headers, show_line_numbers=True, classes="height20", language="json")

            yield Label(t(t.RESPONSE_BODY))
            ### TODO: support for binary content: response_content_base64 ###
            response_body = self.history_record["response_body"] or ""
            yield TextArea(str(response_body), show_line_numbers=True, classes="height20")

            yield Label(t(t.COOKIES))
            cookies = json.dumps(self.history_record["cookies"], indent=4)
            yield TextArea(cookies, show_line_numbers=True, classes="height10", language="json")

            yield Rule(line_style="heavy")
            yield Label(t(t.ENDPOINT_DETAILS))
            yield Rule(line_style="heavy")
            yield Pretty(self.history_record["endpoint"])

            yield Rule(line_style="heavy")
            yield Label(t(t.CREDENTIAL_DETAILS))
            yield Rule(line_style="heavy")
            yield Pretty(self.history_record["credential"])


            with Horizontal(classes="button-container"):
                yield Button(t(t.CLOSE), variant="default", id="history-detail-cancel-btn")

    @on(Button.Pressed, "#history-detail-cancel-btn")
    def action_cancel_dialog(self) -> None:
        self.dismiss()


class CallHistoryViewer(ModalScreen):

    BINDINGS = [
        ("escape", "cancel_dialog", t(t.CLOSE)),
        ("r", "refresh_content", t(t.REFRESH_HISTORY)),
        ("l", "histories_data_table_view_log_selected", t(t.CALL_HISTORY_DETAILS)),
    ]

    def __init__(self, history_records:dict|None=None, ignore_columns:list=["url", "request_url", "endpoint", "credential", "response_headers", "cookies", "response_encoding", "response_body", "response_content_base64"]):
        super().__init__()
        self.histories_data_table_selected_row = None
        self.history_records = []
        if history_records:
            self.history_records = history_records

        self.ignore_columns = []
        if ignore_columns:
            self.ignore_columns = ignore_columns

    def compose(self) -> ComposeResult:
        dialog_content = Vertical(classes="dialog-container")
        dialog_content.styles.width = "85%"
        with dialog_content:
            yield Label(t(t.CALL_HISTORY), classes="title")
            yield DataTable(id="histories_data_table")
            yield Static("")
            yield Button(t(t.CALL_HISTORY_DETAILS), variant="primary", id="history-open-btn")

            with Horizontal(classes="button-container"):
                yield Button(t(t.CLOSE), variant="default", id="history-cancel-btn")

            yield Footer()

    @on(DataTable.RowSelected, "#histories_data_table")
    def update_selected_row(self, event: DataTable.RowSelected):
        self.histories_data_table_selected_row = event.row_key

    @on(events.Mount)
    def loading_dialog(self, event: events.Mount):
        self.action_refresh_content()

    @on(Button.Pressed, "#history-cancel-btn")
    def action_cancel_dialog(self) -> None:
        self.dismiss()

    @on(Button.Pressed, "#history-open-btn")
    def action_histories_data_table_view_log_selected(self):
        if self.histories_data_table_selected_row is None:
            self.notify(message=t(t.ERR_NO_ROW_SELECTED), title=t(t.INFORMATION), severity="information", markup=True)
        else:
            # developer_log("self.histories_data_table_selected_row=" + str(self.histories_data_table_selected_row.value))
            history_record_list = [history for history in self.history_records if history["id"] == self.histories_data_table_selected_row.value]
            # developer_log("history_record_list=" + str(history_record_list))
            history_record = history_record_list[0] if history_record_list else {}
            # developer_log("history_record=" + str(history_record))
            self.app.push_screen(CallHistoryDetailsViewer(history_record))

    def action_refresh_content(self, row_ordering_function=None, column_ordering_function=None):
        ### TODO ### add more types of sorts and unify, store sort settings, add Search Filter

        histories_data_table = self.query_one("#histories_data_table", DataTable)
        histories_data_table.show_cursor = True
        histories_data_table.cursor_type = "row"
        histories_data_table.zebra_stripes = True
        histories_data_table.show_row_labels = True

        histories_data_table.clear(columns=True)

        if len(self.history_records) > 0:

            columns, rows, keys = format_data_table(
                self.history_records,
                column_ordering_function=column_ordering_function,
                row_ordering_function=row_ordering_function,
                ignore_columns=self.ignore_columns
            )

            for column in columns:
                histories_data_table.add_column(column, key=column)

            cnt = 1
            for row in rows:
                label = Text(str(cnt), style="#38B0FC italic")
                histories_data_table.add_row(*row, label=label, key=keys[cnt-1])
                cnt += 1

        self.histories_data_table_selected_row = None
        histories_data_table.focus()


class EndpointEditor(ModalScreen):

    BINDINGS = [
        ("escape", "cancel_dialog", t(t.CANCEL))
    ]

    def __init__(self, endpoint:dict|None=None, available_credentials:list[tuple[str, int]]=[]):
        super().__init__()
        self.endpoint = {}
        self.available_credentials = available_credentials

        if endpoint:
            self.endpoint = endpoint
        else:
            self.endpoint = empty_endpoint()


    def compose(self) -> ComposeResult:
        dialog_content = Vertical(classes="dialog-container")
        dialog_content.styles.width = "95%"
        with dialog_content:
            yield Label(t(t.ENDPOINT_EDITOR), classes="title")

            # for key in self.endpoint:
            #     with Horizontal(classes="input-row"):
            #         yield Label(key, id=key+"_label")
            #         yield Input(value=str(self.endpoint.get(key, "")), id=key+"_input", compact=True)

            yield LineInput(label=t(t.NAME), value=self.endpoint.get("name", ""), id="name")

            yield LineInput(label=t(t.DESC), value=self.endpoint.get("desc", ""), id="desc")

            with Horizontal(classes="input-row"):
                yield Label(t(t.CREDENTIAL) + ": ", classes="input-row-left")
                selected_credential_option = Select.BLANK
                if self.endpoint.get("credential_id", None):
                    #selected_credential_option = [credential for credential in self.available_credentials if credential[1] == self.endpoint.get("credential_id")][0]
                    selected_credential_option = self.endpoint.get("credential_id")

                # developer_log("available_credentials:")
                # developer_log(str(self.available_credentials))
                # developer_log("selected_credential_option:")
                # developer_log(str(selected_credential_option))

                yield Select(
                    value=selected_credential_option,
                    id="credential_id",
                    classes="input-row-right",
                    compact=True,
                    allow_blank=True,
                    type_to_search=True,
                    options=self.available_credentials
                )

            with Horizontal(classes="input-row"):
                yield Label(t(t.METHOD) + ": ", classes="input-row-left")
                available_methods = [(method, method) for method in METHODS]
                selected_method_option = Select.BLANK
                if self.endpoint.get("method", None):
                    #selected_method_option = [method for method in available_methods if method[1] == self.endpoint.get("method")][0]
                    selected_method_option = self.endpoint.get("method")

                # developer_log("available_methods:")
                # developer_log(str(available_methods))
                # developer_log("selected_method_option:")
                # developer_log(str(selected_method_option))

                yield Select(
                    value=selected_method_option,
                    id="method",
                    classes="input-row-right",
                    compact=True,
                    allow_blank=False,
                    type_to_search=True,
                    options=available_methods
                )

            yield LineInput(label=t(t.URL), value=self.endpoint.get("url", ""), id="url")

            yield Label(t(t.PARAMS) + ": ", classes="input-row-left")
            params = "{}"
            if self.endpoint.get("params", "{}"):
                params = json.dumps(self.endpoint.get("params", "{}"), indent=4)
            yield TextArea.code_editor(
                    name=t(t.PARAMS),
                    text=params,
                    id="params",
                    language="json",
                    show_line_numbers=True,
                    classes="height10"
            )

            yield LineInput(label=t(t.TIMEOUT), value=self.endpoint.get("timeout", ""), id="timeout", type="integer")

            with Horizontal(classes="input-row"):
                 yield Label(t(t.ALLOW_REDIRECTS) + ": ", classes="input-row-left")

                 available_redirect_options = [("True", True), ("False", False)]
                 selected_redirect_option = True
                 if self.endpoint.get("follow_redirects", None):
                     selected_redirect_option = self.endpoint.get("follow_redirects")

                 yield Select(
                     value=selected_redirect_option,
                     id="follow_redirects",
                     classes="input-row-right",
                     compact=True,
                     allow_blank=False,
                     type_to_search=True,
                     options=available_redirect_options
                 )

            yield LineInput(label=t(t.LABELS), value=self.endpoint.get("labels", ""), id="labels")

            yield Label(t(t.HEADERS) + ": ", classes="input-row-left")
            headers = "{}"
            if self.endpoint.get("headers", "{}"):
                headers = json.dumps(self.endpoint.get("headers"), indent=4)

            yield TextArea.code_editor(
                    name=t(t.HEADERS),
                    text=headers,
                    id="headers",
                    language="json",
                    show_line_numbers=True,
                    classes="height10"
            )

            yield Label(t(t.BODY) + ": ")
            yield TextArea.code_editor(
                    name=t(t.BODY),
                    text=str(self.endpoint.get("body", None) or ""),
                    id="body",
                    language="json",
                    show_line_numbers=True,
                    classes="height10"
            )

            with Horizontal(classes="button-container"):
                yield Button(t(t.CANCEL), variant="default", id="endpoint-cancel-btn")
                yield Button(t(t.APPLY), variant="success", id="endpoint-apply-btn")

    @on(Button.Pressed, "#endpoint-cancel-btn")
    def action_cancel_dialog(self) -> None:
        self.dismiss()

    @on(Button.Pressed, "#endpoint-apply-btn")
    def action_apply(self, event: Button.Pressed) -> None:
        endpoint_params = self.query_one("#params", TextArea)
        endpoint_labels = self.query_one("#labels", Input)
        endpoint_headers = self.query_one("#headers", TextArea)
        endpoint_params_dict = {}
        endpoint_labels_list = []
        endpoint_headers_dict = {}

        try:
            endpoint_params_dict = ast.literal_eval(endpoint_params.text)

            if not isinstance(endpoint_params_dict, dict):
                raise ValueError(t(t.ERR_PARAM_FORMAT))

            if not all(isinstance(k, str) and isinstance(v, str) for k, v in endpoint_params_dict.items()):
                raise ValueError(t(t.ERR_PARAM_STR))

        except Exception as e:
            self.notify(t(t.PARAMS) + ': ' + str(e), title=t(t.ERROR), severity="error", timeout=ERROR_NOTE_TIMEOUT)
            event.stop()
            return

        try:
            endpoint_labels_list = ast.literal_eval(endpoint_labels.value)

            if not isinstance(endpoint_labels_list, list):
                raise ValueError(t(t.ERR_LABELS_FORMAT))

            if not all(isinstance(item, str) for item in endpoint_labels_list):
                raise ValueError(t(t.ERR_LABELS_STR))

        except Exception as e:
            self.notify(t(t.LABELS) + ': ' + str(e), title=t(t.ERROR), severity="error", timeout=ERROR_NOTE_TIMEOUT)
            event.stop()
            return

        try:
            endpoint_headers_dict = ast.literal_eval(endpoint_headers.text)

            if not isinstance(endpoint_headers_dict, dict):
                raise ValueError(t(t.ERR_HEADERS_FORMAT))

            if not all(isinstance(k, str) and isinstance(v, str) for k, v in endpoint_headers_dict.items()):
                raise ValueError(t(t.ERR_HEADERS_STR))

        except Exception as e:
            self.notify(t(t.HEADERS) + ': ' + str(e), title=t(t.ERROR), severity="error", timeout=ERROR_NOTE_TIMEOUT)
            event.stop()
            return

        credential_id = self.query_one("#credential_id", Select).value
        if self.query_one("#credential_id", Select).is_blank():
            credential_id = None

        body = self.query_one("#body", TextArea).text
        if body == "":
            body = None

        self.endpoint["name"] = self.query_one("#name", Input).value
        self.endpoint["desc"] = self.query_one("#desc", Input).value
        self.endpoint["credential_id"] = credential_id
        self.endpoint["method"] = self.query_one("#method", Select).value
        self.endpoint["url"] = self.query_one("#url", Input).value
        self.endpoint["params"] = endpoint_params_dict
        self.endpoint["timeout"] = int(self.query_one("#timeout", Input).value)
        self.endpoint["follow_redirects"] = bool(self.query_one("#follow_redirects", Select).value)
        self.endpoint["labels"] = endpoint_labels_list
        self.endpoint["headers"] = endpoint_headers_dict
        self.endpoint["body"] = body

        self.dismiss(self.endpoint)


class PlainEditor(ModalScreen):

    BINDINGS = [
        ("escape", "cancel_dialog", t(t.CANCEL))
    ]

    def __init__(self, file_data_json: AnyStr=""):
        super().__init__()
        self.file_data_json = file_data_json
        self.dirty_bit = False

    def compose(self) -> ComposeResult:
        dialog_content = Vertical(classes="dialog-container")
        dialog_content.styles.width = "90%"

        with dialog_content:
            yield Label(t(t.PFE), classes="title")
            yield TextArea.code_editor(text=self.file_data_json, language="json", id="code-editor", show_line_numbers=True, name=t(t.EDITOR))
            with Horizontal(classes="button-container"):
                yield Button(t(t.CANCEL), variant="default", id="editor-cancel-btn")
                yield Button(t(t.APPLY), variant="success", id="editor-apply-btn")

    @on(TextArea.Changed, "#code-editor")
    def update_file_data_json(self) -> None:
        code_editor = self.query_one("#code-editor", TextArea)
        self.file_data_json = code_editor.text
        self.dirty_bit = True

    @on(Button.Pressed, "#editor-apply-btn")
    def action_apply(self) -> None:
        if self.dirty_bit:
            try:
                file_data = json.loads(self.file_data_json)
                self.notify(t(t.DATA_UPD), title=t(t.INFORMATION), severity="information")
                self.dismiss(self.file_data_json)
            except Exception as e:
                self.notify(str(e), title=t(t.ERROR), severity="error", timeout=ERROR_NOTE_TIMEOUT)
        else:
            self.dismiss()

    @on(Button.Pressed, "#editor-cancel-btn")
    def action_cancel_dialog(self) -> None:
        self.dismiss()


class YesNoQuestion(ModalScreen):

    BINDINGS = [
        ("y", "answer_yes", t(t.YES)),
        ("n", "answer_no", t(t.NO)),
        ("escape", "cancel_dialog", t(t.CANCEL))
    ]

    def __init__(self, question=None):
        super().__init__()
        self.question = question or t(t.CONFIRM)

    def compose(self) -> ComposeResult:
        dialog_content = Vertical(classes="dialog-container")
        dialog_content.styles.width = 55

        with dialog_content:
            yield Label(t(t.CONFIRMATION), classes="title")
            yield Label(self.question)

            with Horizontal(classes="button-container"):
                yield Button(t(t.CANCEL), variant="default", id="cancel-btn")
                yield Button(t(t.NO) + " (" + "n" + ")", variant="error", id="no-btn")
                yield Button(t(t.YES) + " (" + "y" + ")", variant="success", id="yes-btn")

    @on(Button.Pressed, "#no-btn")
    def action_answer_no(self) -> None:
        self.dismiss(False)

    @on(Button.Pressed, "#yes-btn")
    def action_answer_yes(self) -> None:
        self.dismiss(True)

    @on(Button.Pressed, "#cancel-btn")
    def action_cancel_dialog(self) -> None:
        self.dismiss()

    @on(events.Mount)
    def setfocus(self) -> None:
        cancel_button = self.query_one("#cancel-btn", Button)
        cancel_button.focus()


class SelectFileDialog(ModalScreen):
    BINDINGS = [
        ("escape", "cancel_dialog", t(t.CANCEL))
    ]

    def __init__(self, directories_only: bool=False):
        super().__init__()
        self.selected_path = None
        self.directories_only = directories_only

    def compose(self) -> ComposeResult:

        dialog_content = Vertical(classes="dialog-container")
        dialog_content.styles.width = "70%"

        with dialog_content:
            if self.directories_only:
                yield Label(t(t.SEL_DIR), classes="title")
            else:
                yield Label(t(t.SEL_FILE), classes="title")

            if self.directories_only:
                yield FoldersDirectoryTree(Path.home(), id="krest-dir-tree")
            else:
                yield KrestDirectoryTree(Path.home(), id="krest-dir-tree")

            with Horizontal(classes="button-container"):
                yield Button(t(t.CANCEL), variant="default", id="cancel-btn")
                yield Button(t(t.SEL), variant="primary", id="select-btn")

    @on(DirectoryTree.FileSelected, "#krest-dir-tree")
    def update_selected_file_path(self, event: DirectoryTree.FileSelected) -> None:
        self.selected_path = event.path

    @on(DirectoryTree.DirectorySelected, "#krest-dir-tree")
    def update_selected_dir_path(self, event: DirectoryTree.DirectorySelected) -> None:
        self.selected_path = event.path

    @on(Button.Pressed, "#select-btn")
    def action_close_dialog(self) -> None:
        if self.selected_path:
            if self.directories_only and self.selected_path.is_dir() \
               or not self.directories_only and self.selected_path.is_file():
                    self.dismiss(self.selected_path)

    @on(Button.Pressed, "#cancel-btn")
    def action_cancel_dialog(self) -> None:
        self.dismiss()


class OpenFileDialog(ModalScreen):
    BINDINGS = [
        ("escape", "cancel_dialog", t(t.CANCEL))
    ]

    def __init__(self, new_file: bool=False):
        super().__init__()
        self.new_file = new_file

    def compose(self):
        with Vertical(classes="dialog-container"):
            if self.new_file:
                yield Label(t(t.NEW), classes="title")
            else:
                yield Label(t(t.OPEN), classes="title")

            yield Label(t(t.FILE_PRMT))

            with Horizontal(classes="input-row"):
                yield Input(placeholder=t(t.FILE_NAME), id="open-file-name", classes="input-row-left")
                yield Button(t(t.BROWSE), variant="primary", id="open-browse-btn", classes="input-row-right-btn")

            yield Input(placeholder=t(t.PASSWORD), id="open-file-password", password=True,)

            with Horizontal(classes="button-container"):
                yield Button(t(t.CANCEL), variant="default", id="open-cancel-btn")
                if self.new_file:
                    yield Button(t(t.NEW), variant="success", id="open-open-btn")
                else:
                    yield Button(t(t.OPEN), variant="success", id="open-open-btn")

    @on(Button.Pressed, "#open-browse-btn")
    def open_browse_dialog(self, event) -> None:
        def update_file_name(result) -> None:
            if result:
                if self.new_file:
                    self.query_one("#open-file-name", Input).value = str(result) + "/" + t(t.NEW) + "." + FILE_EXTENSION
                else:
                    self.query_one("#open-file-name", Input).value = str(result)

        self.app.push_screen(SelectFileDialog(directories_only=self.new_file), callback=update_file_name)
        event.stop()

    @on(Button.Pressed, "#open-open-btn")
    def action_close_dialog(self) -> None:
        filename = self.query_one("#open-file-name", Input).value
        password = self.query_one("#open-file-password", Input).value
        self.dismiss((filename, password))

    @on(Button.Pressed, "#open-cancel-btn")
    def action_cancel_dialog(self) -> None:
        self.dismiss()


class CredentialEditor(ModalScreen):

    BINDINGS = [
        ("escape", "cancel_dialog", t(t.CLOSE)),
    ]

    def __init__(self, credential:dict|None=None):
        super().__init__()
        self.credential = {}

        if credential:
            self.credential = credential

    @on(events.Mount)
    def draw_form_on_mount(self, event: events.Mount)-> None:
        credential_type = self.credential.get("credential_type", None)
        self.draw_form(credential_type=credential_type)

    def draw_form(self, credential_type):
        # developer_log(f"draw_form({credential_type})")
        dialog_content = self.query_one("#credential_editor_dialog_content", Vertical)
        if credential_type in (CredentialType.BASIC.value, CredentialType.DIGEST.value):
            dialog_content.mount(LineInput(label=t(t.NAME), value=self.credential.get("name", ""), id="name"))
            dialog_content.mount(LineInput(label=t(t.DESC), value=self.credential.get("desc", ""), id="desc"))
            dialog_content.mount(LineInput(label=t(t.LABELS), value=self.credential.get("labels", ""), id="labels"))
            dialog_content.mount(LineInput(label=t(t.USERNAME), value=self.credential.get("username", ""), id="username"))
            dialog_content.mount(LineInput(label=t(t.PASSWORD), value=self.credential.get("password", ""), id="password"))
        elif credential_type == CredentialType.OAUTH2.value:
            dialog_content.mount(LineInput(label=t(t.NAME), value=self.credential.get("name", ""), id="name"))
            dialog_content.mount(LineInput(label=t(t.DESC), value=self.credential.get("desc", ""), id="desc"))
            dialog_content.mount(LineInput(label=t(t.LABELS), value=self.credential.get("labels", ""), id="labels"))
            dialog_content.mount(LineInput(label=t(t.TOKEN_URL), value=self.credential.get("token_url", ""), id="token_url"))
            dialog_content.mount(LineInput(label=t(t.SCOPE), value=str(self.credential.get("scope", "") or ""), id="scope"))
            dialog_content.mount(LineInput(label=t(t.CLIENT_ID), value=self.credential.get("client_id", ""), id="client_id"))
            dialog_content.mount(LineInput(label=t(t.CLIENT_SECRET), value=self.credential.get("client_secret", ""), id="client_secret"))

    def compose(self) -> ComposeResult:

        dialog_content = Vertical(classes="dialog-container", id="credential_editor_dialog_content")
        dialog_content.styles.width = "65%"
        
        with dialog_content:
            yield Label(t(t.CREDENTIAL_EDITOR), classes="title")

            if self.credential.get("credential_type", None):
                # developer_log("existing credential...")
                yield LineDisplay(label=t(t.CREDENTIAL_TYPE), value=self.credential.get("credential_type", None))
            else:
                # developer_log("new credential...")
                with Horizontal(classes="input-row"):
                    yield Label(t(t.CREDENTIAL_TYPE) + ": ", classes="input-row-left")

                    available_credential_types = [(item.display, item.value) for item in CredentialType]

                    yield Select(
                        value=Select.BLANK,
                        id="credential_type_selector",
                        classes="input-row-right",
                        compact=True,
                        allow_blank=True,
                        type_to_search=True,
                        options=available_credential_types
                    )
            
            with Horizontal(classes="button-container"):
                yield Button(t(t.CANCEL), variant="default", id="credential-cancel-btn")
                yield Button(t(t.APPLY), variant="success", id="credential-apply-btn")

    @on(Select.Changed, "#credential_type_selector")
    def handle_credential_type_selection(self, event: Select.Changed) -> None:
        selected_credential_type = event.value

        if selected_credential_type:
            # developer_log("selected_credential_type: " + str(selected_credential_type))
            self.credential = empty_credential(selected_credential_type)
            self.draw_form(self.credential["credential_type"])
            self.query_one("#credential_type_selector", Select).disabled = True

    @on(Button.Pressed, "#credential-cancel-btn")
    def action_cancel_dialog(self) -> None:
        self.dismiss()

    @on(Button.Pressed, "#credential-apply-btn")
    def action_apply(self, event: Button.Pressed) -> None:
        credential_type = self.credential.get("credential_type", None)

        if credential_type in (CredentialType.BASIC.value, CredentialType.DIGEST.value):
            try:
                credentials_labels_list = ast.literal_eval(self.query_one("#labels", Input).value)

                if not isinstance(credentials_labels_list, list):
                    raise ValueError(t(t.ERR_LABELS_FORMAT))

                if not all(isinstance(item, str) for item in credentials_labels_list):
                    raise ValueError(t(t.ERR_LABELS_STR))

            except Exception as e:
                self.notify(t(t.LABELS) + ': ' + str(e), title=t(t.ERROR), severity="error", timeout=ERROR_NOTE_TIMEOUT)
                event.stop()
                return

            self.credential["name"] = self.query_one("#name", Input).value
            self.credential["desc"] = self.query_one("#desc", Input).value
            self.credential["labels"] = credentials_labels_list
            self.credential["username"] = self.query_one("#username", Input).value
            self.credential["password"] = self.query_one("#password", Input).value

        elif credential_type == CredentialType.OAUTH2.value:
            try:
                credentials_labels_list = ast.literal_eval(self.query_one("#labels", Input).value)

                if not isinstance(credentials_labels_list, list):
                    raise ValueError(t(t.ERR_LABELS_FORMAT))

                if not all(isinstance(item, str) for item in credentials_labels_list):
                    raise ValueError(t(t.ERR_LABELS_STR))

            except Exception as e:
                self.notify(t(t.LABELS) + ': ' + str(e), title=t(t.ERROR), severity="error", timeout=ERROR_NOTE_TIMEOUT)
                event.stop()
                return
            
            scope = self.query_one("#scope", Input).value
            if scope == "":
                scope = None
            
            self.credential["name"] = self.query_one("#name", Input).value
            self.credential["desc"] = self.query_one("#desc", Input).value
            self.credential["labels"] = credentials_labels_list
            self.credential["token_url"] = self.query_one("#token_url", Input).value
            self.credential["scope"] = scope
            self.credential["client_id"] = self.query_one("#client_id", Input).value
            self.credential["client_secret"] = self.query_one("#client_secret", Input).value

        else:
            self.notify(t(t.ERR_CREDENTIAL_TYPE, credential_type=credential_type), title=t(t.ERROR), severity="error", timeout=ERROR_NOTE_TIMEOUT)
            event.stop()
            return
        
        self.dismiss(self.credential)

class Credentials(ModalScreen):

    BINDINGS = [
        ("escape", "cancel_dialog", t(t.CLOSE)),
        ("r", "refresh_content", t(t.REFRESH_CREDENTIALS)),
        ("m", "credentials_data_table_modify_selected", t(t.MODIFY_CREDENTIAL)),
        ("a", "credentials_data_table_add", t(t.NEW_CREDENTIAL)),
    ]

    def __init__(self, backend, ignore_columns:list=["headers", "method", "body", "password", "client_secret"]):
        super().__init__()
        self.backend = backend
        self.credentials_data_table_selected_row = None

        self.ignore_columns = []
        if ignore_columns:
            self.ignore_columns = ignore_columns

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Header(show_clock=True)
            yield Label(t(t.MANAGE_CREDENTIALS))
            yield DataTable(id="credentials_data_table")
            yield Static("")
            yield Button(t(t.MODIFY), variant="primary", id="credentials-edit-btn")
            yield Button(t(t.NEW), variant="success", id="credentials-add-btn")
            with Horizontal(classes="button-container"):
                yield Button(t(t.CLOSE), variant="default", id="credentials-cancel-btn")
            yield Footer()

    @on(DataTable.RowSelected, "#credentials_data_table")
    def update_selected_row(self, event: DataTable.RowSelected):
        self.credentials_data_table_selected_row = event.row_key

    def handle_save_credential(self, credential):
        if credential:
            try:
                self.backend.save_credential(credential)
                self.notify(message=t(t.DATA_UPD), title=t(t.INFORMATION), severity="information", markup=True)
                self.action_refresh_content()
            except Exception as e:
                error_stack = traceback.format_exc()
                self.notify(str(error_stack), title=t(t.ERROR), severity="error", timeout=ERROR_NOTE_TIMEOUT)
        else:
            self.notify(t(t.NO_UPD), title=t(t.INFORMATION), severity="information")

    @on(Button.Pressed, "#credentials-add-btn")
    def action_credentials_data_table_add(self) -> None:
        if self.backend.file_path:
            self.app.push_screen(CredentialEditor(credential=None), callback=self.handle_save_credential)
        else:
            self.notify(message=t(t.ERR_NO_FILE_SELECTED), title=t(t.INFORMATION), severity="information", markup=True)

    @on(Button.Pressed, "#credentials-edit-btn")
    def action_credentials_data_table_modify_selected(self) -> None:
        if self.credentials_data_table_selected_row is None:
            self.notify(message=t(t.ERR_NO_ROW_SELECTED), title=t(t.INFORMATION), severity="information", markup=True)
        else:
            if self.backend.file_path:
                credential_id = self.credentials_data_table_selected_row.value
                credential = self.backend.get_credential(credential_id)
                self.app.push_screen(CredentialEditor(credential=credential), callback=self.handle_save_credential)
            else:
                self.notify(message=t(t.ERR_NO_FILE_SELECTED), title=t(t.INFORMATION), severity="information", markup=True)
            
    @on(events.Mount)
    def loading_dialog(self, event: events.Mount):
        self.action_refresh_content()

    @on(Button.Pressed, "#credentials-cancel-btn")
    def action_cancel_dialog(self) -> None:
        self.dismiss()

    def action_refresh_content(self, row_ordering_function=None, column_ordering_function=None):
        ### TODO ### add more types of sorts and unify, store sort settings, add Search Filter

        credentials_data_table = self.query_one("#credentials_data_table", DataTable)
        credentials_data_table.show_cursor = True
        credentials_data_table.cursor_type = "row"
        credentials_data_table.zebra_stripes = True
        credentials_data_table.show_row_labels = True

        credentials_data_table.clear(columns=True)

        if len(self.backend.file_data["credentials"]) > 0:

            columns, rows, keys = format_data_table(
                self.backend.file_data["credentials"],
                column_ordering_function=column_ordering_function,
                row_ordering_function=row_ordering_function,
                ignore_columns=self.ignore_columns
            )

            for column in columns:
                credentials_data_table.add_column(column, key=column)

            cnt = 1
            for row in rows:
                label = Text(str(cnt), style="#38B0FC italic")
                credentials_data_table.add_row(*row, label=label, key=keys[cnt-1])
                cnt += 1

        self.credentials_data_table_selected_row = None
        credentials_data_table.focus()

class KrestTui(App):

    CSS_PATH = "krest_tui.tcss"

    BINDINGS = [
        ("ctrl+o", "open_file", t(t.OPEN)),
        ("ctrl+n", "new_file", t(t.NEW)),
        ("ctrl+s", "save_file", t(t.SAVE)),
        ("ctrl+q", "quit_krest", t(t.QUIT)),
        # ("e", "edit_file", "Advanced Editor"),  ### can kill memory if file too big ###
        # ("|", "none", "║"),
        ("a", "endpoints_data_table_add", t(t.NEW_ENDPOINT)),
        ("x", "endpoints_data_table_execute_selected", t(t.EXECUTE)),
        ("l", "endpoints_data_table_view_logs_selected", t(t.CALL_HISTORY)),
        ("m", "endpoints_data_table_modify_selected", t(t.MODIFY)),
        ("d", "endpoints_data_table_delete_selected", t(t.DELETE)),
        # ("S", "endpoints_data_table_sort_by_name", "Sort by Name"),
        # ("|", "none", "║"),
        ("c", "edit_credentials", t(t.MANAGE_CREDENTIALS)),
        ("h", "view_all_logs", t(t.ALL_CALL_HISTORIES)),
        ("f1", "about", t(t.ABOUT)),
    ]

    current_sorts: set = set()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.backend = KrestBackend()
        self.endpoints_data_table_selected_row = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Footer()
        yield Static("File" + ": -", id="opened_file_name")
        yield DataTable(id="endpoints_data_table")

    @on(events.Mount)
    def update_screen_title(self) -> None:
        self.title = "Krest TUI"
        self.sub_title = t(t.MOTTO) + f"  (v{version('krest-utils')}) "

    @on(DataTable.RowSelected, "#endpoints_data_table")
    def update_selected_row(self, event: DataTable.RowSelected):
        self.endpoints_data_table_selected_row = event.row_key

    def handle_save_endpoint(self, endpoint):
        if endpoint:
            try:
                self.backend.save_endpoint(endpoint)
                self.notify(message=t(t.DATA_UPD), title=t(t.INFORMATION), severity="information", markup=True)
                self.action_refresh_content()
            except Exception as e:
                error_stack = traceback.format_exc()
                self.notify(str(error_stack), title=t(t.ERROR), severity="error", timeout=ERROR_NOTE_TIMEOUT)
        else:
            self.notify(t(t.NO_UPD), title=t(t.INFORMATION), severity="information")

    def action_none(self) -> None:
        pass

    def action_about(self) -> None:
        self.push_screen(About())

    def action_endpoints_data_table_view_logs_selected(self) -> None:
        if self.endpoints_data_table_selected_row is None:
            self.notify(message=t(t.ERR_NO_ROW_SELECTED), title=t(t.INFORMATION), severity="information", markup=True)
        else:
            if self.backend.file_path:
                endpoint_id = self.endpoints_data_table_selected_row.value
                history_records = [history_record for history_record in self.backend.file_data["call_history"] if history_record["endpoint_id"] == endpoint_id]
                self.push_screen(CallHistoryViewer(history_records))
            else:
                self.notify(message=t(t.ERR_NO_FILE_SELECTED), title=t(t.INFORMATION), severity="information", markup=True)

    def action_view_all_logs(self) -> None:
        if self.backend.file_path:
            self.push_screen(CallHistoryViewer(self.backend.file_data["call_history"]))
        else:
            self.notify(message=t(t.ERR_NO_FILE_SELECTED), title=t(t.INFORMATION), severity="information", markup=True)

    def action_edit_credentials(self) -> None:
        if self.backend.file_path:
            self.push_screen(Credentials(self.backend))
        else:
            self.notify(message=t(t.ERR_NO_FILE_SELECTED), title=t(t.INFORMATION), severity="information", markup=True)

    def action_endpoints_data_table_add(self) -> None:
        if self.backend.file_path:
            available_credentials = [(str(credential["name"]), credential["id"]) for credential in self.backend.file_data.get("credentials")]
            self.push_screen(EndpointEditor(available_credentials=available_credentials), callback=self.handle_save_endpoint)
        else:
            self.notify(message=t(t.ERR_NO_FILE_SELECTED), title=t(t.INFORMATION), severity="information", markup=True)

    def action_endpoints_data_table_delete_selected(self) -> None:
        def perform_delete(endpoint_id):
            if endpoint_id:
                try:
                    self.backend.delete_endpoint(endpoint_id)
                    self.notify(message=t(t.DATA_DLTD), title=t(t.INFORMATION), severity="warning", markup=True)
                    self.action_refresh_content()
                except Exception as e:
                    self.notify(str(e), title=t(t.ERROR), severity="error", timeout=ERROR_NOTE_TIMEOUT)
            else:
                self.notify(t(t.NO_UPD), title=t(t.INFORMATION), severity="information")

        if self.endpoints_data_table_selected_row is None:
            self.notify(message=t(t.ERR_NO_ROW_SELECTED), title=t(t.INFORMATION), severity="information", markup=True)
        else:
            if self.backend.file_path:
                endpoint_id = self.endpoints_data_table_selected_row.value
                self.push_screen(
                    YesNoQuestion(t(t.CONFIRM_DELETE)),
                    callback=lambda confirmed: perform_delete(endpoint_id) if confirmed else self.notify(t(t.NO_UPD), title=t(t.INFORMATION), severity="information")
                )
            else:
                self.notify(message=t(t.ERR_NO_FILE_SELECTED), title=t(t.INFORMATION), severity="information", markup=True)

    def action_endpoints_data_table_modify_selected(self) -> None:
        if self.endpoints_data_table_selected_row is None:
            self.notify(message=t(t.ERR_NO_ROW_SELECTED), title=t(t.INFORMATION), severity="information", markup=True)
        else:
            if self.backend.file_path:
                endpoint_id = self.endpoints_data_table_selected_row.value
                endpoint = self.backend.get_endpoint(endpoint_id)

                available_credentials = [(str(credential["name"]), credential["id"]) for credential in self.backend.file_data.get("credentials")]
                self.push_screen(EndpointEditor(available_credentials=available_credentials, endpoint=endpoint), callback=self.handle_save_endpoint)
            else:
                self.notify(message=t(t.ERR_NO_FILE_SELECTED), title=t(t.INFORMATION), severity="information", markup=True)


    def action_endpoints_data_table_execute_selected(self) -> None:
        if self.endpoints_data_table_selected_row is None:
            self.notify(message=t(t.ERR_NO_ROW_SELECTED), title=t(t.INFORMATION), severity="information", markup=True)
        else:
            try:
                id = self.endpoints_data_table_selected_row.value
                self.backend.run_endpoint(id)
                self.notify(message=t(t.RUN_SUCCESS), title=t(t.INFORMATION), severity="information", markup=True)
            except Exception as e:
                error_stack = traceback.format_exc()
                self.notify(str(error_stack), title=t(t.ERROR), severity="error", timeout=ERROR_NOTE_TIMEOUT)

    def sort_reverse(self, sort_type: str):
        reverse = sort_type in self.current_sorts
        if reverse:
            self.current_sorts.remove(sort_type)
        else:
            self.current_sorts.add(sort_type)
        return reverse

    def action_endpoints_data_table_sort_by_name(self) -> None:
        self.action_refresh_content(row_ordering_function=lambda x: x.get("name", ""), column_ordering_function=None)

    def action_refresh_content(self, row_ordering_function=None, column_ordering_function=None) -> None:
        ### TODO ### add more types of sorts and unify, store sort settings, add Search Filter

        self.query_one("#opened_file_name", Static).content = t(t.FILE_NAME) + ": " + str(self.backend.file_path)

        endpoints_data_table = self.query_one("#endpoints_data_table", DataTable)
        endpoints_data_table.show_cursor = True
        endpoints_data_table.cursor_type = "row"
        endpoints_data_table.zebra_stripes = True
        endpoints_data_table.show_row_labels = True

        endpoints_data_table.clear(columns=True)

        endpoints_list = self.backend.file_data.get("endpoints")

        if len(endpoints_list) > 0:

            columns, rows, keys = format_data_table(
                endpoints_list,
                column_ordering_function=column_ordering_function,
                row_ordering_function=row_ordering_function,
                ignore_columns=["headers", "body", "params"]
            )

            for column in columns:
                endpoints_data_table.add_column(column, key=column)

            cnt = 1
            for row in rows:
                label = Text(str(cnt), style="#38B0FC italic")
                endpoints_data_table.add_row(*row, label=label, key=keys[cnt-1])
                cnt += 1

        self.endpoints_data_table_selected_row = None
        endpoints_data_table.focus()

    def action_quit_krest(self) -> None:
        def perform_quit():
            self.exit()

        if self.backend.dirty_bit:
            self.push_screen(
                YesNoQuestion(t(t.NOTE_UNSAVED_CHANGES)),
                callback=lambda confirmed: perform_quit() if confirmed else None
            )
        else:
            perform_quit()

    def action_edit_file(self) -> None:

        def handle_update_file_data(result) -> None:
            if result:
                try:
                    self.backend.file_data = json.loads(result)
                    self.backend.dirty_bit = True
                    self.action_refresh_content()
                except Exception as e:
                    error_stack = traceback.format_exc()
                    self.notify(str(error_stack), title=t(t.ERROR), severity="error", timeout=ERROR_NOTE_TIMEOUT)
            else:
                self.notify(t(t.NO_UPD), title=t(t.INFORMATION), severity="information")

        if self.backend.file_path:
            file_data_json = json.dumps(self.backend.file_data, indent=4)
            self.push_screen(PlainEditor(file_data_json), callback=handle_update_file_data)
        else:
            self.notify(message=t(t.ERR_NO_FILE_SELECTED), title=t(t.INFORMATION), severity="information", markup=True)

    def action_save_file(self) -> None:
        if self.backend.file_path is None or self.backend.file_path=="":
            self.notify(message=t(t.ERR_NO_FILE_SELECTED), title=t(t.INFORMATION), severity="information", markup=True)
        else:
            if self.backend.dirty_bit:
                try:
                    self.backend.save_file()
                    self.notify(message=t(t.FILE_SAVED), title=t(t.INFORMATION), severity="information", markup=True)
                except Exception as e:
                    error_stack = traceback.format_exc()
                    self.notify(str(error_stack), title=t(t.ERROR), severity="error", timeout=ERROR_NOTE_TIMEOUT)
            else:
                self.notify(message=t(t.FILE_NOSAVE), title=t(t.INFORMATION), severity="information", markup=True)

    def action_new_file(self) -> None:

        def perform_create_file(path, password):
            try:
                self.backend.create_file(path, password)
                self.action_refresh_content()
                self.notify(message=t(t.FILE_CREATED), title=t(t.INFORMATION), severity="information", markup=True)
            except Exception as e:
                error_stack = traceback.format_exc()
                self.notify(str(error_stack), title=t(t.ERROR), severity="error", timeout=ERROR_NOTE_TIMEOUT)

        def perform_new_file():

            def handle_selection_dialog(result):

                if result:
                    path, password = result
                    if path is None or path == "":
                        self.notify(message=t(t.ERR_NO_FILE_SELECTED), title=t(t.INFORMATION), severity="information", markup=True)
                        return
                else:
                    #selecting cancelled
                    return

                if Path(path).is_file():
                    self.push_screen(
                        YesNoQuestion(t(t.FILE_EXISTS)),
                        callback=lambda confirmed: perform_create_file(path, password) if confirmed else None
                    )
                else:
                    perform_create_file(path, password)

            self.push_screen(OpenFileDialog(new_file=True), callback=handle_selection_dialog)

        if self.backend.dirty_bit:
            self.push_screen(
                YesNoQuestion(t(t.NOTE_UNSAVED_CHANGES)),
                callback=lambda confirmed: perform_new_file() if confirmed else None
            )
        else:
            perform_new_file()

    def action_open_file(self) -> None:

        def perform_load(file_path, file_password):
            try:
                self.backend.file_path, self.backend.file_password = file_path, file_password
                self.backend.load_file()
                self.action_refresh_content()
                self.notify(message=t(t.FILE_LOADED, file_path=file_path), title=t(t.INFORMATION), severity="information", markup=True)

            except Exception as e:
                error_stack = traceback.format_exc()
                self.notify(str(error_stack), title=t(t.ERROR), severity="error", timeout=ERROR_NOTE_TIMEOUT)

        def handle_file_open_dialog(result):
            if result:
                path, password = result
                if path is None or path == "":
                    self.notify(message=t(t.ERR_NO_FILE_SELECTED), title=t(t.INFORMATION), severity="information", markup=True)
                    return
            else:
                #opening cancelled
                return

            if self.backend.dirty_bit:
                self.push_screen(
                    YesNoQuestion(t(t.NOTE_UNSAVED_CHANGES)),
                    callback=lambda confirmed: perform_load(path, password) if confirmed else None
                )
            else:
                perform_load(path, password)

        self.push_screen(OpenFileDialog(), callback=handle_file_open_dialog)

def tui():
    # setup_logging()
    # logging.info('TUI: Start...')
    krest_main_page = None
    try:
        krest_main_page = KrestTui()
        krest_main_page.run()
    finally:
        krest_main_page = None
        gc.collect()
    # logging.info('TUI: End.')

def main():
    tui()

if __name__ == "__main__":
    tui()


