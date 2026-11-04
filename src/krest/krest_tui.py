#!/usr/bin/env python3

import argparse
import gc
import getpass
import sys
from typing import Callable, Iterable, AnyStr, Literal
from importlib.metadata import version
from functools import partial
from copy import deepcopy
import traceback
import ast
import json
import re
from pathlib import Path
import logging
from rich.text import Text
from textual.app import App, ComposeResult, SystemCommand
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll, Horizontal
from textual.screen import ModalScreen, Screen
from textual.widget import Widget
from textual.widgets import LoadingIndicator, Checkbox, DirectoryTree, Static, Button, Footer, Header, Label, Input, TextArea, DataTable, Select, Rule, Pretty
from textual import on
from textual import events

from krest.krest_backend import KrestBackend, METHODS, BodyType, ValueType, MultipartBody, CredentialType, FILE_EXTENSION, developer_log, empty_endpoint, empty_credential, empty_workflow, setup_logging, LOG_LEVELS
from krest.translations import t

ASCII_LOGO = r"""[blue]
  _  __              _
 | |/ /_ __ ___  ___| |_
 | ' /| '__/ _ \/ __| __|
 | . \| | |  __/\__ \ |_
 |_|\_\_|  \___||___/\__|
[/blue]"""

APP_TITLE = "Krest TUI"
ERROR_NOTE_TIMEOUT = 15
ROW_NUMBER_COLUMN = "__krest_row_number__"


def format_data_table(
        json_data,
        column_ordering_function=None,
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

    # if row_ordering_function:
    #     json_data.sort(key=lambda x: x.get("id", ""))

    for record in json_data:
        row = []
        for column in columns:
            row.append(str(record.get(column, "")))
        records.append(row)
        keys.append(record.get(key))

    return (columns, records, keys)


def row_sort(value):
    try:
        return (0, float(str(value).strip()))
    except ValueError:
        return (1, str(value).strip().casefold())


def sort_data_table(table, sort_column, sort_reverse=False):
    for column in table.ordered_columns:
        if column.key.value == ROW_NUMBER_COLUMN:
            continue
        label = Text.from_markup(column.key.value)
        if column.key.value == sort_column:
            label.append(" \u25bc" if sort_reverse else " \u25b2")
        column.label = label
    table.sort(sort_column, key=row_sort, reverse=sort_reverse)


def refresh_data_table(table, columns, rows, keys, filter_text="", sort_column=None, sort_reverse=False):
    table.show_cursor = True
    table.cursor_type = "row"
    table.zebra_stripes = True
    table.show_row_labels = False
    table.clear()

    column_keys = [ROW_NUMBER_COLUMN, *columns]
    existing_columns = [column.key.value for column in table.ordered_columns]
    if existing_columns != column_keys:
        table.clear(columns=True)
        table.add_column("#", key=ROW_NUMBER_COLUMN, width=1)
        for column in columns:
            table.add_column(column, key=column, width=1)

    # Reserve room for a sort marker so sorting never clips or resizes headers.
    widths = [max(1, len(str(len(rows))))]
    for index, column in enumerate(columns):
        values = [column, *(row[index] for row in rows)]
        widths.append(max(
            line.cell_len
            for value in values
            for line in Text.from_markup(value).split("\n", allow_blank=True)
        ) + 2)
    for column, width in zip(table.ordered_columns, widths):
        column.width = width

    count = 1
    for row, key in zip(rows, keys):
        if filter_text and not any(filter_text in value.casefold() for value in row):
            continue
        label = Text(str(count), style="#38B0FC italic")
        table.add_row(label, *row, key=key)
        count += 1

    if sort_column in columns:
        sort_data_table(table, sort_column, sort_reverse)


class LineDisplay(Widget):
    def __init__(self, label, value):
        super().__init__()
        self.label = label
        self.value = value

    def compose(self):
        with Horizontal(classes="input-row"):
            yield Label(str(self.label), classes="input-row-left")
            yield Label(str(self.value), classes="input-row-right", markup=False)


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


class ExecutionProgress(ModalScreen):
    """Keep execution feedback animated while a blocking backend call runs."""

    DEFAULT_CSS = """
    ExecutionProgress { align: center middle; }
    ExecutionProgress > Vertical {
        width: 50;
        height: auto;
        padding: 1 2;
        border: round $accent;
        background: $surface;
    }
    ExecutionProgress LoadingIndicator { height: 3; }
    """

    def __init__(self, operation: Callable[[], object], kind: str, record_id):
        super().__init__()
        self.operation = operation
        self.kind = kind
        self.record_id = record_id

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(t(t.EXECUTE))
            yield LoadingIndicator()

    def on_mount(self) -> None:
        self.run_worker(self.execute, thread=True)

    def execute(self) -> None:
        try:
            self.operation()
        except Exception as error:
            logging.error("TUI: Executing %s failed (%s)", self.kind, type(error).__name__)
            self.app.call_from_thread(self.notify, traceback.format_exc(), title=t(t.ERROR), severity="error", timeout=ERROR_NOTE_TIMEOUT)
        else:
            logging.info("TUI: %s execution succeeded id=%s", self.kind, self.record_id)
            self.app.call_from_thread(self.notify, message=t(t.RUN_SUCCESS), title=t(t.INFORMATION), severity="information", markup=True)
        finally:
            self.app.call_from_thread(self.close_progress)

    def close_progress(self) -> None:
        self.dismiss()


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


class HistoryDownloadButton(Button):
    """Keep encoded history content out of the rendered widgets."""

    def __init__(self, content, id):
        super().__init__(t(t.DOWNLOAD), variant="primary", id=id, classes="history-download")
        self.content = content


class CallHistoryDetailsViewer(ModalScreen):

    DEFAULT_CSS = """
    CallHistoryDetailsViewer .dialog-container { width: 95%; height: 90%; }
    CallHistoryDetailsViewer VerticalScroll { height: 1fr; }
    CallHistoryDetailsViewer TextArea { height: 10; }
    """

    BINDINGS = [
        ("escape", "cancel_dialog", t(t.CLOSE))
    ]

    def __init__(self, history_record:dict|None=None):
        super().__init__()
        self.history_record = deepcopy(history_record or {})


    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog-container"):
            yield Label(t(t.CALL_HISTORY_DETAILS), classes="title")
            with VerticalScroll():
                yield from self.compose_details()
            with Horizontal(classes="button-container"):
                yield Button(t(t.CLOSE), variant="default", id="history-detail-cancel-btn")

    def compose_details(self) -> ComposeResult:
        record = self.history_record
        endpoint = record.get("endpoint") or {}
        for field, label in (
            ("id", t(t.ID)),
            ("call_type", t(t.CALL_TYPE)),
            ("endpoint_id", t(t.ENDPOINT_ID)),
            ("run_date", t(t.RUN_DATE)),
            ("response_status_code", t(t.RESPONSE_STATUS_CODE)),
            ("response_reason_phrase", t(t.RESPONSE_REASON_PHRASE)),
            ("elapsed_time", t(t.ELAPSED_TIME)),
            ("response_content_length", t(t.RESPONSE_CONTENT_LENGTH)),
            ("response_http_version", t(t.RESPONSE_HTTP_VERSION)),
            ("response_encoding", t(t.RESPONSE_ENCODING)),
            ("response_charset_encoding", t(t.RESPONSE_CHARSET_ENCODING)),
            ("response_has_redirect_location", t(t.RESPONSE_HAS_REDIRECT_LOCATION)),
            ("response_links", t(t.RESPONSE_LINKS)),
        ):
            yield LineDisplay(label=label, value=record.get(field, ""))
        for field in ("url", "request_url", "response_url"):
            if field in record:
                yield LineDisplay(label=field, value=record[field])

        yield Label(t(t.HEADERS))
        yield TextArea(json.dumps(record.get("response_headers") or {}, indent=4), show_line_numbers=True, read_only=True, language="json")

        response_type = record.get("response_type", endpoint.get("response_type", ValueType.TEXT.value))
        yield LineDisplay(label=t(t.RESPONSE_TYPE), value=response_type)
        yield Label(t(t.RESPONSE_BODY))
        if response_type == ValueType.BINARY.value:
            yield HistoryDownloadButton(record.get("response_content_base64"), id="history-response-download")
        else:
            yield TextArea(str(record.get("response_body") or ""), show_line_numbers=True, read_only=True, id="history-response-body")

        yield Label(t(t.COOKIES))
        yield TextArea(json.dumps(record.get("cookies") or [], indent=4), show_line_numbers=True, read_only=True, language="json")

        yield Rule(line_style="heavy")
        yield Label(t(t.ENDPOINT_DETAILS))
        yield Rule(line_style="heavy")
        yield Pretty({key: value for key, value in endpoint.items() if key != "body"})
        yield Label(t(t.BODY))
        body = endpoint.get("body")
        body_type = endpoint.get("body_type", BodyType.TEXT.value)
        if body_type == BodyType.BINARY.value:
            yield HistoryDownloadButton(body, id="history-body-download")
        elif body_type == BodyType.MULTIPART.value:
            for index, (name, part) in enumerate((body or {}).items()):
                yield Rule()
                yield LineDisplay(t(t.ATTRIBUTE_NAME), name)
                for field, label in (("filename", t(t.FILE_NAME)), ("value_type", t(t.VALUE_TYPE)), ("mime_type", t(t.MIME))):
                    yield LineDisplay(label, part.get(field) or "")
                if part.get("value_type") == ValueType.BINARY.value:
                    yield HistoryDownloadButton(part.get("value"), id=f"history-part-{index}-download")
                else:
                    yield TextArea(str(part.get("value") or ""), show_line_numbers=True, read_only=True)
        else:
            text = json.dumps(body, indent=4) if isinstance(body, (dict, list)) else str(body or "")
            yield TextArea(text, show_line_numbers=True, read_only=True, id="history-request-body")

        yield Rule(line_style="heavy")
        yield Label(t(t.CREDENTIAL_DETAILS))
        yield Rule(line_style="heavy")
        yield Pretty(record.get("credential") or {})

        yield Rule(line_style="heavy")
        yield Label(t(t.VARIABLES))
        yield Rule(line_style="heavy")
        yield TextArea(json.dumps(record.get("variables_curr") or {}, indent=4, ensure_ascii=False), show_line_numbers=True, read_only=True, language="json", id="history-variables")

        yield Rule(line_style="heavy")
        yield Label(t(t.UPDATED_VARIABLES))
        yield Rule(line_style="heavy")
        yield TextArea(json.dumps(record.get("variables_updated") or {}, indent=4, ensure_ascii=False), show_line_numbers=True, read_only=True, language="json", id="history-variables-updated")

    @on(Button.Pressed, ".history-download")
    def download_content(self, event: Button.Pressed) -> None:
        event.stop()
        content = event.button.content

        def save_file(result) -> None:
            if result is None:
                return
            file_path, overwrite = result
            try:
                KrestBackend.export_file(content, file_path, force=overwrite)
            except Exception as error:
                logging.warning("TUI: Downloading history content failed (%s)", type(error).__name__)
                self.notify(str(error), title=t(t.ERROR), severity="error", timeout=ERROR_NOTE_TIMEOUT)
                return
            self.notify(t(t.FILE_SAVED), title=t(t.INFORMATION), severity="information")

        self.app.push_screen(BodyFileDialog(download=True), callback=save_file)

    @on(Button.Pressed, "#history-detail-cancel-btn")
    def action_cancel_dialog(self) -> None:
        self.dismiss()


class PurgeCallHistoryDialog(ModalScreen):

    BINDINGS = [
        Binding("escape", "cancel_dialog", t(t.CANCEL), priority=True)
    ]

    def __init__(self, backend: KrestBackend):
        super().__init__()
        self.backend = backend

    def compose(self) -> ComposeResult:
        dialog_content = Vertical(classes="dialog-container")
        dialog_content.styles.width = 55
        with dialog_content:
            yield Label(t(t.PURGE_CALL_HISTORY), classes="title")
            yield Label(t(t.OLDER))
            yield Input(type="integer", placeholder="N", id="purge-history-days")
            with Horizontal(classes="button-container"):
                yield Button(t(t.CANCEL), variant="default", id="purge-history-cancel-btn")
                yield Button(t(t.DELETE), variant="error", id="purge-history-delete-btn")

    @on(Button.Pressed, "#purge-history-delete-btn")
    def action_delete(self) -> None:
        days_input = self.query_one("#purge-history-days", Input)
        try:
            days = int(days_input.value)
        except ValueError:
            logging.warning("TUI: Invalid call history retention input")
            self.notify(t(t.ERR_DAYS_FORMAT), title=t(t.ERROR), severity="error")
            days_input.focus()
            return
        try:
            self.backend.purge_call_history_older_than(days)
        except (ValueError, OverflowError) as error:
            logging.error("TUI: Call history purge failed (%s)", type(error).__name__)
            self.notify(str(error), title=t(t.ERROR), severity="error", timeout=ERROR_NOTE_TIMEOUT)
            return
        self.dismiss(True)

    @on(Button.Pressed, "#purge-history-cancel-btn")
    def action_cancel_dialog(self) -> None:
        self.dismiss(False)


class CallHistoryViewer(ModalScreen):

    AUTO_FOCUS = "#histories_data_table"

    BINDINGS = [
        Binding("escape", "cancel_dialog", t(t.CLOSE), priority=True),
        ("r", "refresh_content", t(t.REFRESH_HISTORY)),
        ("l", "histories_data_table_view_log_selected", t(t.CALL_HISTORY_DETAILS)),
        ("D", "purge_call_history", t(t.PURGE_CALL_HISTORY)),
    ]

    def __init__(self, backend: KrestBackend, ignore_columns:list=["url", "request_url", "endpoint", "credential", "response_headers", "cookies", "response_encoding", "response_body", "response_content_base64"], endpoint_id=None):
        super().__init__()
        self.backend = backend
        self.endpoint_id = endpoint_id
        self.histories_data_table_selected_row = None
        self.histories_data_table_sort_column: str | None = None
        self.histories_data_table_sort_reverse = False
        self.history_records = []

        self.ignore_columns = []
        if ignore_columns:
            self.ignore_columns = ignore_columns

    def compose(self) -> ComposeResult:
        dialog_content = Vertical(classes="dialog-container")
        dialog_content.styles.width = "85%"
        with dialog_content:
            yield Label(t(t.CALL_HISTORY), classes="title")
            yield Input(id="histories_filter", compact=True, placeholder=t(t.SEARCH_LABEL))
            yield DataTable(id="histories_data_table")
            yield Static("")
            yield Button(t(t.CALL_HISTORY_DETAILS), variant="primary", id="history-open-btn")
            yield Static("")
            yield Static("")
            yield Button(t(t.PURGE_CALL_HISTORY), variant="error", id="history-purge-btn")


            with Horizontal(classes="button-container"):
                yield Button(t(t.CLOSE), variant="default", id="history-cancel-btn")

            yield Footer()

    @on(Input.Changed, "#histories_filter")
    def filter_histories(self, event: Input.Changed) -> None:
        self.action_refresh_content()

    @on(Input.Submitted, "#histories_filter")
    def filter_submitted(self, event: Input.Submitted) -> None:
        self.query_one("#histories_data_table", DataTable).focus()

    @on(DataTable.RowHighlighted, "#histories_data_table")
    @on(DataTable.RowSelected, "#histories_data_table")
    def update_selected_row(self, event: DataTable.RowHighlighted | DataTable.RowSelected):
        self.histories_data_table_selected_row = event.row_key

    @on(events.Mount)
    def loading_dialog(self, event: events.Mount):
        self.action_refresh_content()

    @on(DataTable.HeaderSelected, "#histories_data_table")
    def sort_histories_by_header(self, event: DataTable.HeaderSelected) -> None:
        if event.column_key.value == ROW_NUMBER_COLUMN:
            return

        if self.histories_data_table_sort_column == event.column_key.value:
            self.histories_data_table_sort_reverse = not self.histories_data_table_sort_reverse
        else:
            self.histories_data_table_sort_column = event.column_key.value
            self.histories_data_table_sort_reverse = False

        sort_data_table(self.query_one("#histories_data_table", DataTable), event.column_key.value, self.histories_data_table_sort_reverse)

        if self.histories_data_table_selected_row is not None:
            table = self.query_one("#histories_data_table", DataTable)
            table.move_cursor(row=table.get_row_index(self.histories_data_table_selected_row), scroll=True)

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

    @on(Button.Pressed, "#history-purge-btn")
    def action_purge_call_history(self) -> None:
        self.app.push_screen(PurgeCallHistoryDialog(self.backend), self.handle_purge_call_history)

    def handle_purge_call_history(self, deleted: bool) -> None:
        if deleted:
            logging.debug("TUI: Refreshing call history after purge")
            self.action_refresh_content()

    def action_refresh_content(self, column_ordering_function=None):

        self.history_records = self.backend.file_data["call_history"]
        if self.endpoint_id is not None:
            self.history_records = [
                history_record for history_record in self.history_records
                if history_record["endpoint_id"] == self.endpoint_id
            ]
        histories_data_table = self.query_one("#histories_data_table", DataTable)
        filter_text = self.query_one("#histories_filter", Input).value.strip().casefold()
        columns, rows, keys = format_data_table(
            self.history_records,
            column_ordering_function=column_ordering_function,
            ignore_columns=self.ignore_columns
        )
        refresh_data_table(
            histories_data_table, columns, rows, keys,
            filter_text=filter_text,
            sort_column=self.histories_data_table_sort_column,
            sort_reverse=self.histories_data_table_sort_reverse,
        )

        self.histories_data_table_selected_row = None
        if histories_data_table.row_count:
            histories_data_table.move_cursor(row=0)
            self.histories_data_table_selected_row = histories_data_table.coordinate_to_cell_key(histories_data_table.cursor_coordinate).row_key


class MultipartRow(Horizontal):
    def __init__(self, attribute_name, part):
        super().__init__(classes="multipart-row")
        self.attribute_name = attribute_name
        self.part = part

    def compose(self) -> ComposeResult:
        binary = self.part.get("value_type") == ValueType.BINARY.value
        value_type = self.part.get("value_type")
        value_type_display = next((item.display for item in ValueType if item.value == value_type), value_type)
        for value in (
            self.attribute_name, self.part.get("filename"),
            value_type_display, "" if binary else self.part.get("value"),
            self.part.get("mime_type"),
        ):
            yield Label(str(value or ""), markup=False)
        with Horizontal(classes="multipart-actions"):
            yield Button(t(t.DELETE), classes="multipart-delete", compact=True)
            if binary:
                yield Button(t(t.DOWNLOAD), classes="multipart-download", compact=True)
                yield Button(t(t.UPLOAD), classes="multipart-upload", compact=True)


class EndpointEditor(ModalScreen):

    DEFAULT_CSS = """
    EndpointEditor #multipart-body { height: auto; overflow-x: auto; }
    EndpointEditor #multipart-rows { height: auto; min-width: 110; }
    EndpointEditor .multipart-row { height: auto; min-width: 110; }
    EndpointEditor .multipart-row > * { width: 1fr; margin-right: 1; }
    EndpointEditor .multipart-row > Vertical { height: auto; }
    EndpointEditor .multipart-row > .multipart-actions { width: 32; height: auto; }
    EndpointEditor .multipart-actions Button { min-width: 0; width: auto; margin-right: 1; }
    """

    BINDINGS = [
        ("escape", "cancel_dialog", t(t.CANCEL))
    ]

    def __init__(self, endpoint:dict|None=None, available_credentials:list[tuple[str, int]]=[], backend:KrestBackend|None=None):
        super().__init__()
        self.backend = backend if backend is not None else KrestBackend()
        self.endpoint_curr = {}
        self.available_credentials = available_credentials

        if endpoint:
            self.endpoint_curr = deepcopy(endpoint)
        else:
            self.endpoint_curr = empty_endpoint()


    def compose(self) -> ComposeResult:
        dialog_content = Vertical(classes="dialog-container")
        dialog_content.styles.width = "95%"
        with dialog_content:
            yield Label(t(t.ENDPOINT_EDITOR), classes="title")

            # for key in self.endpoint_curr:
            #     with Horizontal(classes="input-row"):
            #         yield Label(key, id=key+"_label")
            #         yield Input(value=str(self.endpoint_curr.get(key, "")), id=key+"_input", compact=True)

            yield LineInput(label=t(t.NAME), value=self.endpoint_curr.get("name", ""), id="name")

            yield LineInput(label=t(t.DESC), value=self.endpoint_curr.get("desc", ""), id="desc")

            with Horizontal(classes="input-row"):
                yield Label(t(t.CREDENTIAL) + ": ", classes="input-row-left")
                selected_credential_option = Select.BLANK
                credential_id = self.endpoint_curr.get("credential_id")
                if any(value == credential_id for _, value in self.available_credentials):
                    selected_credential_option = credential_id

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
                if self.endpoint_curr.get("method", None):
                    #selected_method_option = [method for method in available_methods if method[1] == self.endpoint_curr.get("method")][0]
                    selected_method_option = self.endpoint_curr.get("method")

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

            yield LineInput(label=t(t.URL), value=self.endpoint_curr.get("url", ""), id="url")

            yield Label(t(t.PARAMS) + ": ", classes="input-row-left")
            params = "{}"
            if self.endpoint_curr.get("params", "{}"):
                params = json.dumps(self.endpoint_curr.get("params", "{}"), indent=4)
            yield TextArea.code_editor(
                    name=t(t.PARAMS),
                    text=params,
                    id="params",
                    language="json",
                    show_line_numbers=True,
                    classes="height10"
            )

            yield LineInput(label=t(t.TIMEOUT), value=self.endpoint_curr.get("timeout", ""), id="timeout", type="integer")

            with Horizontal(classes="input-row"):
                yield Label(t(t.RESPONSE_TYPE) + ": ", classes="input-row-left")
                yield Select(
                    value=self.endpoint_curr.get("response_type", ValueType.TEXT.value),
                    id="response_type",
                    classes="input-row-right",
                    compact=True,
                    allow_blank=False,
                    type_to_search=True,
                    options=[(item.display, item.value) for item in ValueType],
                )

            for field, label, default in (
                ("follow_redirects", t(t.ALLOW_REDIRECTS), True),
                ("ignore_proxy", t(t.IGNORE_PROXY), False),
            ):
                with Horizontal(classes="input-row"):
                    yield Label(label + ": ", classes="input-row-left")
                    yield Select(
                        value=self.endpoint_curr.get(field, default),
                        id=field,
                        classes="input-row-right",
                        compact=True,
                        allow_blank=False,
                        options=[("True", True), ("False", False)],
                    )

            yield LineInput(label=t(t.LABELS), value=self.endpoint_curr.get("labels", ""), id="labels")

            yield Label(t(t.HEADERS) + ": ", classes="input-row-left")
            headers = "{}"
            if self.endpoint_curr.get("headers", "{}"):
                headers = json.dumps(self.endpoint_curr.get("headers"), indent=4)

            yield TextArea.code_editor(
                    name=t(t.HEADERS),
                    text=headers,
                    id="headers",
                    language="json",
                    show_line_numbers=True,
                    classes="height10"
            )

            yield Label(t(t.SET_VARIABLES) + ": ", classes="input-row-left")
            yield TextArea.code_editor(
                name=t(t.SET_VARIABLES),
                text=json.dumps(self.endpoint_curr.get("set_variables") or {}, indent=4),
                id="set_variables", language="json", show_line_numbers=True, classes="height10",
            )

            with Horizontal(classes="input-row"):
                yield Label(t(t.BODY_TYPE) + ": ", classes="input-row-left")
                yield Select(
                    value=self.endpoint_curr.get("body_type", BodyType.TEXT.value),
                    id="body_type",
                    classes="input-row-right",
                    compact=True,
                    allow_blank=False,
                    type_to_search=True,
                    options=[(item.display, item.value) for item in BodyType],
                )

            yield Label(t(t.BODY) + ": ")
            yield TextArea.code_editor(
                    name=t(t.BODY),
                    text=str(self.endpoint_curr.get("body", None) or ""),
                    id="body",
                    language="json",
                    show_line_numbers=True,
                    classes="height10"
            )

            with Horizontal(classes="input-row", id="binary-body-buttons"):
                yield Button(t(t.DOWNLOAD), variant="primary", id="body-download-btn")
                yield Button(t(t.UPLOAD), variant="primary", id="body-upload-btn")

            with Vertical(id="multipart-body"):
                with Horizontal(classes="multipart-row"):
                    for column in (t(t.ATTRIBUTE_NAME), t(t.FILE_NAME), t(t.VALUE_TYPE), t(t.VALUE), t(t.MIME)):
                        yield Label(column)
                    yield Label(t(t.ACTIONS), classes="multipart-actions")
                yield Vertical(id="multipart-rows")
                with Horizontal(classes="multipart-row"):
                    yield Input(placeholder=t(t.ATTRIBUTE_NAME), id="multipart-name", compact=True)
                    yield Input(placeholder=t(t.FILE_NAME), id="multipart-filename", compact=True)
                    yield Select([(item.display, item.value) for item in ValueType],
                                 value=ValueType.TEXT.value, allow_blank=False,
                                 id="multipart-value-type", compact=True)
                    with Vertical():
                        yield Input(placeholder=t(t.VALUE), id="multipart-value", compact=True)
                    yield Input(placeholder=t(t.MIME), id="multipart-mime-type", compact=True)
                    with Horizontal(classes="multipart-actions"):
                        yield Button(t(t.ADD), id="multipart-add", compact=True)

            with Horizontal(classes="button-container"):
                yield Button(t(t.CANCEL), variant="default", id="endpoint-cancel-btn")
                yield Button(t(t.APPLY), variant="success", id="endpoint-apply-btn")

    def on_mount(self) -> None:
        self.endpoint_curr = deepcopy(self.endpoint_curr)
        self.update_body_controls()

    @on(Select.Changed, "#body_type")
    def update_body_controls(self) -> None:
        body_type = self.query_one("#body_type", Select).value
        previous = self.endpoint_curr.get("body_type", BodyType.TEXT.value)
        binary = body_type == BodyType.BINARY.value
        multipart = body_type == BodyType.MULTIPART.value
        if body_type != previous and (
            body_type in (BodyType.BINARY.value, BodyType.MULTIPART.value)
            or previous in (BodyType.BINARY.value, BodyType.MULTIPART.value)
        ):
            self.endpoint_curr["body"] = {} if multipart else None
            self.query_one("#body", TextArea).load_text("")
        self.endpoint_curr["body_type"] = body_type
        self.query_one("#body", TextArea).display = not (binary or multipart)
        self.query_one("#binary-body-buttons", Horizontal).display = binary
        self.query_one("#multipart-body").display = multipart
        if multipart:
            if not isinstance(self.endpoint_curr.get("body"), dict):
                self.endpoint_curr["body"] = {}
            self.refresh_multipart_rows()

    def refresh_multipart_rows(self) -> None:
        rows = self.query_one("#multipart-rows", Vertical)
        rows.remove_children()
        rows.mount(*(MultipartRow(name, part) for name, part in self.endpoint_curr["body"].items()))

    @on(Select.Changed, "#multipart-value-type")
    def update_multipart_value(self) -> None:
        self.query_one("#multipart-value", Input).display = (
            self.query_one("#multipart-value-type", Select).value != ValueType.BINARY.value
        )

    @on(Button.Pressed, "#multipart-add")
    def add_multipart_part(self) -> None:
        name = self.query_one("#multipart-name", Input).value
        body = MultipartBody(self.endpoint_curr["body"])
        if not name.strip() or name in body:
            self.notify(t(t.ERR_UNIQUE_ATTR_NAME), severity="error")
            return
        value_type = self.query_one("#multipart-value-type", Select).value
        body.set_part(
            name, self.query_one("#multipart-filename", Input).value or None,
            value_type,
            b"" if value_type == ValueType.BINARY.value else self.query_one("#multipart-value", Input).value,
            self.query_one("#multipart-mime-type", Input).value or None,
        )
        self.endpoint_curr["body"] = body
        self.refresh_multipart_rows()
        for field in ("name", "filename", "value", "mime-type"):
            self.query_one(f"#multipart-{field}", Input).value = ""
        self.query_one("#multipart-value-type", Select).value = ValueType.TEXT.value

    @on(Button.Pressed, ".multipart-delete")
    @on(Button.Pressed, ".multipart-download")
    @on(Button.Pressed, ".multipart-upload")
    def multipart_action(self, event: Button.Pressed) -> None:
        row = event.button.parent.parent
        name = row.attribute_name
        event.stop()
        if event.button.has_class("multipart-delete"):
            del self.endpoint_curr["body"][name]
            row.remove()
        elif event.button.has_class("multipart-download"):
            self.download_body_file(name)
        else:
            self.upload_body_file(name)

    @on(Button.Pressed, "#body-download-btn")
    def download_body(self) -> None:
        self.download_body_file()

    def download_body_file(self, part_name=None) -> None:
        def save_file(result) -> None:
            if result is None:
                return
            file_path, overwrite = result
            try:
                body = self.endpoint_curr.get("body")
                content = body[part_name].get("value") if part_name is not None else body
                self.backend.export_file(content, file_path, force=overwrite)
            except Exception as error:
                logging.warning("TUI: Downloading endpoint body failed (%s)", type(error).__name__)
                self.notify(str(error), title=t(t.ERROR), severity="error", timeout=ERROR_NOTE_TIMEOUT)
                return
            self.notify(t(t.FILE_SAVED), title=t(t.INFORMATION), severity="information")

        self.app.push_screen(BodyFileDialog(download=True), callback=save_file)

    @on(Button.Pressed, "#body-upload-btn")
    def upload_body(self) -> None:
        self.upload_body_file()

    def upload_body_file(self, part_name=None) -> None:
        def load_file(result) -> None:
            if result is None:
                return
            file_path, _ = result
            try:
                body = self.backend.import_file(file_path)
            except Exception as error:
                logging.warning("TUI: Uploading endpoint body failed (%s)", type(error).__name__)
                self.notify(str(error), title=t(t.ERROR), severity="error", timeout=ERROR_NOTE_TIMEOUT)
                return
            if part_name is not None:
                self.endpoint_curr["body"][part_name]["value"] = body
            else:
                self.endpoint_curr["body"] = body
                self.query_one("#body", TextArea).load_text(body)
            self.notify(t(t.FILE_LOADED, file_path=file_path), title=t(t.INFORMATION), severity="information")

        self.app.push_screen(BodyFileDialog(), callback=load_file)

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
            logging.warning("TUI: Invalid endpoint parameters (%s)", type(e).__name__)
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
            logging.warning("TUI: Invalid endpoint labels (%s)", type(e).__name__)
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
            logging.warning("TUI: Invalid endpoint headers (%s)", type(e).__name__)
            self.notify(t(t.HEADERS) + ': ' + str(e), title=t(t.ERROR), severity="error", timeout=ERROR_NOTE_TIMEOUT)
            event.stop()
            return

        try:
            set_variables = json.loads(self.query_one("#set_variables", TextArea).text)
            if not isinstance(set_variables, dict):
                raise ValueError(t(t.ERR_VARIABLES_FORMAT))
            if not all(isinstance(k, str) and isinstance(v, str) for k, v in set_variables.items()):
                raise ValueError(t(t.ERR_VARIABLE_NOT_STRING))
        except (ValueError, TypeError) as e:
            logging.warning("TUI: Invalid endpoint set variables (%s)", type(e).__name__)
            self.notify(t(t.SET_VARIABLES) + ': ' + str(e), title=t(t.ERROR), severity="error", timeout=ERROR_NOTE_TIMEOUT)
            event.stop()
            return

        credential_id = self.query_one("#credential_id", Select).value
        if self.query_one("#credential_id", Select).is_blank():
            credential_id = None

        self.update_body_controls()
        if self.query_one("#body_type", Select).value in (BodyType.BINARY.value, BodyType.MULTIPART.value):
            body = self.endpoint_curr.get("body")
        else:
            body = self.query_one("#body", TextArea).text
            if body == "":
                body = None

        self.endpoint_curr["name"] = self.query_one("#name", Input).value
        self.endpoint_curr["desc"] = self.query_one("#desc", Input).value
        self.endpoint_curr["credential_id"] = credential_id
        self.endpoint_curr["method"] = self.query_one("#method", Select).value
        self.endpoint_curr["url"] = self.query_one("#url", Input).value
        self.endpoint_curr["params"] = endpoint_params_dict
        self.endpoint_curr["timeout"] = int(self.query_one("#timeout", Input).value)
        self.endpoint_curr["response_type"] = self.query_one("#response_type", Select).value
        self.endpoint_curr["follow_redirects"] = self.query_one("#follow_redirects", Select).value
        self.endpoint_curr["ignore_proxy"] = self.query_one("#ignore_proxy", Select).value
        self.endpoint_curr["labels"] = endpoint_labels_list
        self.endpoint_curr["headers"] = endpoint_headers_dict
        self.endpoint_curr["set_variables"] = set_variables
        self.endpoint_curr["body_type"] = self.query_one("#body_type", Select).value
        self.endpoint_curr["body"] = body

        self.dismiss(self.endpoint_curr)


class Properties(ModalScreen):

    BINDINGS = [
        Binding("escape", "cancel_dialog", t(t.CANCEL), priority=True)
    ]

    def __init__(self, backend: KrestBackend):
        super().__init__()
        self.backend = backend

    def compose(self) -> ComposeResult:
        dialog_content = Vertical(classes="dialog-container")
        dialog_content.styles.width = "90%"
        dialog_content.styles.height = "80%"

        with dialog_content:
            yield Label(t(t.PROPERTIES_SETTINGS), classes="title")
            yield TextArea.code_editor(
                text=json.dumps(self.backend.file_data["settings"], indent=4),
                language="json",
                id="settings-editor",
                show_line_numbers=True,
                name=t(t.EDITOR),
            )
            with Horizontal(classes="button-container"):
                yield Button(t(t.CANCEL), variant="default", id="properties-cancel-btn")
                yield Button(t(t.SAVE), variant="success", id="properties-save-btn")

    @on(Button.Pressed, "#properties-save-btn")
    def action_save(self) -> None:
        try:
            settings = json.loads(self.query_one("#settings-editor", TextArea).text)
            self.backend.save_settings(settings)
        except (ValueError, TypeError) as error:
            logging.warning("TUI: Settings update rejected (%s)", type(error).__name__)
            self.notify(str(error), title=t(t.ERROR), severity="error", timeout=ERROR_NOTE_TIMEOUT)
            return
        self.dismiss()

    @on(Button.Pressed, "#properties-cancel-btn")
    def action_cancel_dialog(self) -> None:
        self.dismiss()


class ChangePassword(ModalScreen):

    BINDINGS = [
        Binding("escape", "cancel_dialog", t(t.CANCEL), priority=True)
    ]

    def __init__(self, backend: KrestBackend):
        super().__init__()
        self.backend = backend

    def compose(self) -> ComposeResult:
        dialog_content = Vertical(classes="dialog-container")
        dialog_content.styles.width = 60
        with dialog_content:
            yield Label(t(t.CHANGE_PASSWORD), classes="title")
            yield Label(t(t.OLD_PASSWORD))
            yield Input(password=True, id="old-password")
            yield Label(t(t.NEW_PASSWORD))
            yield Input(password=True, id="new-password")
            yield Label(t(t.NEW_PASSWORD_AGAIN))
            yield Input(password=True, id="new-password-again")
            with Horizontal(classes="button-container"):
                yield Button(t(t.CANCEL), variant="default", id="password-cancel-btn")
                yield Button(t(t.OK), variant="primary", id="password-ok-btn")

    @on(Button.Pressed, "#password-ok-btn")
    def action_save(self) -> None:
        old_password = self.query_one("#old-password", Input)
        new_password = self.query_one("#new-password", Input)
        confirmation = self.query_one("#new-password-again", Input)
        if old_password.value != self.backend.file_password:
            self.notify(t(t.ERR_INVALID_PASSWD), title=t(t.ERROR), severity="error")
            old_password.focus()
            return
        if new_password.value != confirmation.value:
            self.notify(t(t.ERR_PASSWORDS_NOT_MATCH), title=t(t.ERROR), severity="error")
            confirmation.focus()
            return
        self.backend.file_password = new_password.value
        self.backend.dirty_bit = True
        self.dismiss()

    @on(Button.Pressed, "#password-cancel-btn")
    def action_cancel_dialog(self) -> None:
        self.dismiss()


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
                logging.warning("TUI: Advanced editor input rejected (%s)", type(e).__name__)
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
        dialog_content.styles.width = 75
        dialog_content.styles.max_width = "95%"

        with dialog_content:
            yield Label(t(t.CONFIRMATION), classes="title")
            yield Label(self.question).set_styles(width="100%", height="auto")

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

    def __init__(self, directories_only: bool=False, all_files: bool=False):
        super().__init__()
        self.selected_path = None
        self.directories_only = directories_only
        self.all_files = all_files

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
            elif self.all_files:
                yield DirectoryTree(Path.home(), id="krest-dir-tree")
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
            if self.directories_only and self.selected_path.is_dir() or not self.directories_only and self.selected_path.is_file():
                self.dismiss(self.selected_path)

    @on(Button.Pressed, "#cancel-btn")
    def action_cancel_dialog(self) -> None:
        self.dismiss()


class BodyFileDialog(ModalScreen):
    BINDINGS = [("escape", "cancel_dialog", t(t.CANCEL))]

    def __init__(self, download: bool=False):
        super().__init__()
        self.download = download

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog-container"):
            yield Label(t(t.DOWNLOAD) if self.download else t(t.UPLOAD), classes="title")
            path_label = t(t.DIRECTORY_NAME) if self.download else t(t.FILE_NAME)
            yield Label(path_label)
            with Horizontal(classes="input-row"):
                yield Input(placeholder=path_label, id="body-directory-name" if self.download else "body-file-name", classes="input-row-left")
                yield Button(t(t.BROWSE), variant="primary", id="body-browse-btn", classes="input-row-right-btn")
            if self.download:
                yield Label(t(t.FILE_NAME))
                yield Input(placeholder=t(t.FILE_NAME), id="body-file-name")
                yield Checkbox(t(t.OVERWRITE), value=False, id="body-overwrite")
            with Horizontal(classes="button-container"):
                yield Button(t(t.CANCEL), id="body-file-cancel-btn")
                yield Button(t(t.SAVE) if self.download else t(t.OPEN), variant="success", id="body-file-confirm-btn")

    @on(Button.Pressed, "#body-browse-btn")
    def browse_file(self, event: Button.Pressed) -> None:
        def update_file_name(result) -> None:
            if result is not None:
                selector = "#body-directory-name" if self.download else "#body-file-name"
                self.query_one(selector, Input).value = str(result)

        self.app.push_screen(SelectFileDialog(directories_only=self.download, all_files=True), callback=update_file_name)
        event.stop()

    @on(Button.Pressed, "#body-file-confirm-btn")
    def confirm_file(self) -> None:
        file_path = self.query_one("#body-file-name", Input).value
        if self.download:
            directory = self.query_one("#body-directory-name", Input).value
            file_path = str(Path(directory) / file_path)
        overwrite = self.query_one("#body-overwrite", Checkbox).value if self.download else False
        self.dismiss((file_path, overwrite))

    @on(Button.Pressed, "#body-file-cancel-btn")
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

    def __init__(self, credential:dict|None=None, backend:KrestBackend|None=None):
        super().__init__()
        self.backend = backend
        self.credential = {}

        if credential:
            self.credential = credential

    @on(events.Mount)
    def draw_form_on_mount(self, event: events.Mount)-> None:
        credential_type = self.credential.get("credential_type", None)
        if credential_type == CredentialType.OAUTH2.value:
            credential = self.credential

            ### For backward compatibility with 1.0.2.
            token_body = credential.get("token_body", None)
            token_headers = credential.get("token_headers", None)
            if not token_body and not token_headers:
                token_body = "grant_type=client_credentials"
                token_headers = {"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"}
                if credential.get("scope", None):
                    token_body += "&scope=" + credential["scope"]
                credential["scope"] = None
                credential["token_body"] = token_body
                credential["token_headers"] = token_headers
                self.backend.save_credential(credential)
            ###

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
            dialog_content.mount(LineInput(label=t(t.CLIENT_ID), value=self.credential.get("client_id", ""), id="client_id"))
            dialog_content.mount(LineInput(label=t(t.CLIENT_SECRET), value=self.credential.get("client_secret", ""), id="client_secret"))
            dialog_content.mount(Label(t(t.HEADERS) + ":"))
            dialog_content.mount(TextArea.code_editor(
                text=json.dumps(self.credential.get("token_headers", {}) or {}, indent=4),
                name=t(t.HEADERS), id="token_headers", language="json",
                show_line_numbers=True, classes="height10",
            ))
            dialog_content.mount(Label(t(t.BODY) + " (application/x-www-form-urlencoded):"))
            dialog_content.mount(TextArea(
                text=self.credential.get("token_body", "") or "",
                name=t(t.BODY), id="token_body", classes="height10",
            ))

        if credential_type in (CredentialType.BASIC.value, CredentialType.DIGEST.value, CredentialType.OAUTH2.value):
            dialog_content.mount(Label(t(t.SET_VARIABLES) + ":"))
            dialog_content.mount(TextArea.code_editor(
                text=json.dumps(self.credential.get("set_variables") or {}, indent=4),
                name=t(t.SET_VARIABLES), id="set_variables", language="json",
                show_line_numbers=True, classes="height10",
            ))
            for field, label, default in (
                ("follow_redirects", t(t.ALLOW_REDIRECTS), True),
                ("ignore_proxy", t(t.IGNORE_PROXY), False),
            ):
                dialog_content.mount(Horizontal(
                    Label(label + ": ", classes="input-row-left"),
                    Select(
                        value=self.credential.get(field, default),
                        id=field,
                        classes="input-row-right",
                        compact=True,
                        allow_blank=False,
                        options=[("True", True), ("False", False)],
                    ),
                    classes="input-row",
                ))

    def compose(self) -> ComposeResult:

        dialog_content = Vertical(classes="dialog-container", id="credential_editor_dialog_content")
        dialog_content.styles.width = "65%"
        dialog_content.styles.max_height = "95%"
        dialog_content.styles.overflow_y = "auto"
        
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
            if selected_credential_type == CredentialType.OAUTH2.value:
                self.credential["token_body"] = ""
                self.credential["token_headers"] = {}
            self.draw_form(self.credential["credential_type"])
            self.query_one("#credential_type_selector", Select).disabled = True

    @on(Button.Pressed, "#credential-cancel-btn")
    def action_cancel_dialog(self) -> None:
        self.dismiss()

    @on(Button.Pressed, "#credential-apply-btn")
    def action_apply(self, event: Button.Pressed) -> None:
        credential_type = self.credential.get("credential_type", None)

        if credential_type in (CredentialType.BASIC.value, CredentialType.DIGEST.value, CredentialType.OAUTH2.value):
            try:
                set_variables = json.loads(self.query_one("#set_variables", TextArea).text)
                if not isinstance(set_variables, dict):
                    raise ValueError(t(t.ERR_VARIABLES_FORMAT))
                if not all(isinstance(k, str) and isinstance(v, str) for k, v in set_variables.items()):
                    raise ValueError(t(t.ERR_VARIABLE_NOT_STRING))
            except (ValueError, TypeError) as e:
                logging.warning("TUI: Invalid credential set variables (%s)", type(e).__name__)
                self.notify(t(t.SET_VARIABLES) + ': ' + str(e), title=t(t.ERROR), severity="error", timeout=ERROR_NOTE_TIMEOUT)
                event.stop()
                return

        if credential_type in (CredentialType.BASIC.value, CredentialType.DIGEST.value):
            try:
                credentials_labels_list = ast.literal_eval(self.query_one("#labels", Input).value)

                if not isinstance(credentials_labels_list, list):
                    raise ValueError(t(t.ERR_LABELS_FORMAT))

                if not all(isinstance(item, str) for item in credentials_labels_list):
                    raise ValueError(t(t.ERR_LABELS_STR))

            except Exception as e:
                logging.warning("TUI: Invalid credential labels (%s)", type(e).__name__)
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
                logging.warning("TUI: Invalid credential labels (%s)", type(e).__name__)
                self.notify(t(t.LABELS) + ': ' + str(e), title=t(t.ERROR), severity="error", timeout=ERROR_NOTE_TIMEOUT)
                event.stop()
                return
            
            try:
                token_headers = json.loads(self.query_one("#token_headers", TextArea).text)
                if not isinstance(token_headers, dict):
                    raise ValueError(t(t.ERR_HEADERS_FORMAT))
                if not all(isinstance(k, str) and isinstance(v, str) for k, v in token_headers.items()):
                    raise ValueError(t(t.ERR_HEADERS_STR))
            except (ValueError, TypeError) as e:
                logging.warning("TUI: Invalid OAuth2 token headers (%s)", type(e).__name__)
                self.notify(t(t.HEADERS) + ': ' + str(e), title=t(t.ERROR), severity="error", timeout=ERROR_NOTE_TIMEOUT)
                event.stop()
                return
            
            self.credential["name"] = self.query_one("#name", Input).value
            self.credential["desc"] = self.query_one("#desc", Input).value
            self.credential["labels"] = credentials_labels_list
            self.credential["token_url"] = self.query_one("#token_url", Input).value
            self.credential["token_body"] = self.query_one("#token_body", TextArea).text
            self.credential["token_headers"] = token_headers
            self.credential.pop("scope", None)
            self.credential["client_id"] = self.query_one("#client_id", Input).value
            self.credential["client_secret"] = self.query_one("#client_secret", Input).value

        else:
            logging.error("TUI: Cannot apply credential with unsupported authentication type")
            self.notify(t(t.ERR_CREDENTIAL_TYPE, credential_type=credential_type), title=t(t.ERROR), severity="error", timeout=ERROR_NOTE_TIMEOUT)
            event.stop()
            return
        
        self.credential["follow_redirects"] = self.query_one("#follow_redirects", Select).value
        self.credential["ignore_proxy"] = self.query_one("#ignore_proxy", Select).value
        self.credential["set_variables"] = set_variables
        self.dismiss(self.credential)

class Credentials(ModalScreen):

    AUTO_FOCUS = "#credentials_data_table"

    BINDINGS = [
        ("escape", "cancel_dialog", t(t.CLOSE)),
        ("r", "refresh_content", t(t.REFRESH_CREDENTIALS)),
        ("m", "credentials_data_table_modify_selected", t(t.MODIFY_CREDENTIAL)),
        ("a", "credentials_data_table_add", t(t.NEW_CREDENTIAL)),
        ("d", "credentials_data_table_delete_selected", t(t.DELETE)),
    ]

    def __init__(self, backend, ignore_columns:list=["headers", "method", "body", "password", "client_secret"]):
        super().__init__()
        self.backend = backend
        self.credentials_data_table_selected_row = None
        self.credentials_data_table_sort_column: str | None = None
        self.credentials_data_table_sort_reverse = False

        self.ignore_columns = []
        if ignore_columns:
            self.ignore_columns = ignore_columns

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Header(show_clock=True)
            yield Label(t(t.MANAGE_CREDENTIALS))
            yield Input(id="credentials_filter", compact=True, placeholder=t(t.SEARCH_LABEL))
            yield DataTable(id="credentials_data_table")
            yield Static("")
            with Horizontal(classes="button-container"):
                yield Button(t(t.CLOSE), variant="default", id="credentials-cancel-btn")
                yield Button(t(t.DELETE), variant="error", id="credentials-delete-btn")
                yield Button(t(t.MODIFY), variant="primary", id="credentials-edit-btn")
                yield Button(t(t.NEW), variant="success", id="credentials-add-btn")

            yield Footer()

    @on(Input.Changed, "#credentials_filter")
    def filter_credentials(self, event: Input.Changed) -> None:
        self.action_refresh_content()

    @on(Input.Submitted, "#credentials_filter")
    def filter_submitted(self, event: Input.Submitted) -> None:
        self.query_one("#credentials_data_table", DataTable).focus()

    @on(DataTable.RowHighlighted, "#credentials_data_table")
    @on(DataTable.RowSelected, "#credentials_data_table")
    def update_selected_row(self, event: DataTable.RowHighlighted | DataTable.RowSelected):
        self.credentials_data_table_selected_row = event.row_key

    @on(DataTable.HeaderSelected, "#credentials_data_table")
    def sort_credentials_by_header(self, event: DataTable.HeaderSelected) -> None:
        if event.column_key.value == ROW_NUMBER_COLUMN:
            return

        if self.credentials_data_table_sort_column == event.column_key.value:
            self.credentials_data_table_sort_reverse = not self.credentials_data_table_sort_reverse
        else:
            self.credentials_data_table_sort_column = event.column_key.value
            self.credentials_data_table_sort_reverse = False

        sort_data_table(self.query_one("#credentials_data_table", DataTable), event.column_key.value, self.credentials_data_table_sort_reverse)

        if self.credentials_data_table_selected_row is not None:
            table = self.query_one("#credentials_data_table", DataTable)
            table.move_cursor(row=table.get_row_index(self.credentials_data_table_selected_row), scroll=True)

    def handle_save_credential(self, credential):
        if credential:
            try:
                self.backend.save_credential(credential)
                self.notify(message=t(t.DATA_UPD), title=t(t.INFORMATION), severity="information", markup=True)
                self.action_refresh_content()
            except Exception as e:
                logging.error("TUI: Saving credential failed (%s)", type(e).__name__)
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
                self.app.push_screen(CredentialEditor(credential=credential, backend=self.backend), callback=self.handle_save_credential)
            else:
                self.notify(message=t(t.ERR_NO_FILE_SELECTED), title=t(t.INFORMATION), severity="information", markup=True)

    @on(Button.Pressed, "#credentials-delete-btn")
    def action_credentials_data_table_delete_selected(self) -> None:
        def perform_delete(credential_id):
            if credential_id is not None:
                try:
                    self.backend.delete_credential(credential_id)
                    self.notify(message=t(t.DATA_DLTD), title=t(t.INFORMATION), severity="warning", markup=True)
                    self.action_refresh_content()
                except Exception as e:
                    logging.error("TUI: Deleting credential failed (%s)", type(e).__name__)
                    self.notify(str(e), title=t(t.ERROR), severity="error", timeout=ERROR_NOTE_TIMEOUT)
            else:
                self.notify(t(t.NO_UPD), title=t(t.INFORMATION), severity="information")

        if self.credentials_data_table_selected_row is None:
            self.notify(message=t(t.ERR_NO_ROW_SELECTED), title=t(t.INFORMATION), severity="information", markup=True)
        else:
            if self.backend.file_path:
                credential_id = self.credentials_data_table_selected_row.value
                self.app.push_screen(
                    YesNoQuestion(t(t.CONFIRM_DELETE)),
                    callback=lambda confirmed: perform_delete(credential_id) if confirmed else self.notify(t(t.NO_UPD), title=t(t.INFORMATION), severity="information")
                )
            else:
                self.notify(message=t(t.ERR_NO_FILE_SELECTED), title=t(t.INFORMATION), severity="information", markup=True)

    @on(events.Mount)
    def loading_dialog(self, event: events.Mount):
        self.action_refresh_content()

    @on(Button.Pressed, "#credentials-cancel-btn")
    def action_cancel_dialog(self) -> None:
        self.dismiss()

    def action_refresh_content(self, column_ordering_function=None):

        credentials_data_table = self.query_one("#credentials_data_table", DataTable)
        filter_text = self.query_one("#credentials_filter", Input).value.strip().casefold()
        columns, rows, keys = format_data_table(
            self.backend.file_data["credentials"],
            column_ordering_function=column_ordering_function,
            ignore_columns=self.ignore_columns
        )
        refresh_data_table(
            credentials_data_table, columns, rows, keys,
            filter_text=filter_text,
            sort_column=self.credentials_data_table_sort_column,
            sort_reverse=self.credentials_data_table_sort_reverse,
        )

        self.credentials_data_table_selected_row = None
        if credentials_data_table.row_count:
            credentials_data_table.move_cursor(row=0)
            self.credentials_data_table_selected_row = credentials_data_table.coordinate_to_cell_key(credentials_data_table.cursor_coordinate).row_key

class WorkflowEditor(ModalScreen):
    BINDINGS = [("escape", "cancel_dialog", t(t.CLOSE))]

    def __init__(self, workflow=None, backend=None):
        super().__init__()
        self.backend = backend
        self.workflow = deepcopy(workflow) if workflow is not None else empty_workflow()
        self.steps = list(self.workflow.get("steps", []))
        self.endpoints = backend.file_data.get("endpoints", []) if backend else []

    def compose(self) -> ComposeResult:
        dialog = Vertical(classes="dialog-container")
        dialog.styles.max_height = "95%"
        dialog.styles.overflow_y = "auto"
        with dialog:
            yield Label(t(t.WORKFLOW_EDITOR), classes="title")
            yield LineInput(t(t.NAME), self.workflow.get("name", ""), id="name")
            yield LineInput(t(t.DESC), self.workflow.get("desc", ""), id="desc")
            yield LineInput(t(t.LABELS), self.workflow.get("labels", []), id="labels")
            yield Label(t(t.CHOOSE_ENDPOINT))
            yield Select(
                [(Text(f"{endpoint.get('name', '')} ("+t(t.ID)+": {endpoint['id']})"), endpoint["id"]) for endpoint in self.endpoints],
                id="workflow-endpoint", prompt=t(t.SEL_ENDPOINT), type_to_search=True,
                compact=True, disabled=not self.endpoints,
            )
            with Horizontal(classes="input-row"):
                yield Button(t(t.ADD_STEP), id="workflow-step-add", disabled=not self.endpoints)
            yield Label(t(t.STEPS_IN_ORDER))
            yield DataTable(id="workflow-steps", cursor_type="row").set_styles(height=8)
            with Horizontal(classes="input-row"):
                yield Button(t(t.REMOVE_STEP), id="workflow-step-remove")
                yield Button(t(t.MOVE_UP), id="workflow-step-up")
                yield Button(t(t.MOVE_DOWN), id="workflow-step-down")
            with Horizontal(classes="button-container"):
                yield Button(t(t.CANCEL), id="workflow-cancel-btn")
                yield Button(t(t.SAVE), variant="success", id="workflow-save-btn")

    def on_mount(self) -> None:
        self.query_one("#workflow-steps", DataTable).add_columns("#", t(t.NAME), t(t.ENDPOINT_ID))
        self.refresh_steps()

    def refresh_steps(self, selected=0) -> None:
        table = self.query_one("#workflow-steps", DataTable)
        table.clear()
        names = {endpoint["id"]: endpoint.get("name", "") for endpoint in self.endpoints}
        for index, endpoint_id in enumerate(self.steps):
            table.add_row(str(index + 1), Text(names.get(endpoint_id, t(t.ERR_MISSING_ENDPOINT))), str(endpoint_id))
        if self.steps:
            table.move_cursor(row=max(0, min(selected, len(self.steps) - 1)))
        self.query_one("#workflow-step-remove", Button).disabled = not self.steps
        self.query_one("#workflow-step-up", Button).disabled = len(self.steps) < 2
        self.query_one("#workflow-step-down", Button).disabled = len(self.steps) < 2

    @on(Button.Pressed, "#workflow-step-add")
    def add_step(self) -> None:
        endpoint_id = self.query_one("#workflow-endpoint", Select).value
        if endpoint_id is not Select.BLANK:
            self.steps.append(endpoint_id)
            self.refresh_steps(len(self.steps) - 1)

    @on(Button.Pressed, "#workflow-step-remove")
    def remove_step(self) -> None:
        if self.steps:
            index = self.query_one("#workflow-steps", DataTable).cursor_row
            self.steps.pop(index)
            self.refresh_steps(index)

    @on(Button.Pressed, "#workflow-step-up")
    @on(Button.Pressed, "#workflow-step-down")
    def move_step(self, event: Button.Pressed) -> None:
        index = self.query_one("#workflow-steps", DataTable).cursor_row
        target = index + (-1 if event.button.id == "workflow-step-up" else 1)
        if self.steps and 0 <= target < len(self.steps):
            self.steps[index], self.steps[target] = self.steps[target], self.steps[index]
            self.refresh_steps(target)

    @on(Button.Pressed, "#workflow-cancel-btn")
    def action_cancel_dialog(self) -> None:
        self.dismiss()

    @on(Button.Pressed, "#workflow-save-btn")
    def action_apply(self) -> None:
        try:
            labels = ast.literal_eval(self.query_one("#labels", Input).value)
            if not isinstance(labels, list):
                raise ValueError(t(t.ERR_LABELS_FORMAT))
            if not all(isinstance(label, str) for label in labels):
                raise ValueError(t(t.ERR_LABELS_STR))
        except (ValueError, SyntaxError) as error:
            self.notify(t(t.LABELS) + ": " + str(error), title=t(t.ERROR), severity="error")
            return
        self.workflow.update(
            name=self.query_one("#name", Input).value,
            desc=self.query_one("#desc", Input).value,
            labels=labels,
            steps=list(self.steps),
        )
        self.dismiss(self.workflow)


class Workflows(ModalScreen):

    AUTO_FOCUS = "#workflows_data_table"

    BINDINGS = [
        ("escape", "cancel_dialog", t(t.CLOSE)),
        ("r", "refresh_content", t(t.REFRESH_WORKFLOW)),
        ("m", "workflows_data_table_modify_selected", t(t.MODIFY_WORKFLOW)),
        ("a", "workflows_data_table_add", t(t.NEW_WORKFLOW)),
        ("d", "workflows_data_table_delete_selected", t(t.DELETE)),
        ("x", "workflows_data_table_execute_selected", t(t.EXECUTE)),
    ]

    def __init__(self, backend, ignore_columns:list|None=None):
        super().__init__()
        self.backend = backend
        self.backend.file_data.setdefault("workflows", [])
        self.backend.file_data.setdefault("max_workflow_id", -1)
        self.workflows_data_table_selected_row = None
        self.workflows_data_table_sort_column: str | None = None
        self.workflows_data_table_sort_reverse = False

        self.ignore_columns = []
        if ignore_columns:
            self.ignore_columns = ignore_columns

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Header(show_clock=True)
            yield Label(t(t.MANAGE_WORKFLOWS))
            yield Input(id="workflows_filter", compact=True, placeholder=t(t.SEARCH_LABEL))
            yield DataTable(id="workflows_data_table")
            yield Static("")
            with Horizontal(classes="button-container"):
                yield Button(t(t.CLOSE), variant="default", id="workflows-cancel-btn")
                yield Button(t(t.DELETE), variant="error", id="workflows-delete-btn")
                yield Button(t(t.MODIFY), variant="primary", id="workflows-edit-btn")
                yield Button(t(t.NEW), variant="success", id="workflows-add-btn")
                yield Button(t(t.EXECUTE), variant="warning", id="workflow-execute-btn")

            yield Footer()

    @on(Input.Changed, "#workflows_filter")
    def filter_workflows(self, event: Input.Changed) -> None:
        self.action_refresh_content()

    @on(Input.Submitted, "#workflows_filter")
    def filter_submitted(self, event: Input.Submitted) -> None:
        self.query_one("#workflows_data_table", DataTable).focus()

    @on(DataTable.RowHighlighted, "#workflows_data_table")
    @on(DataTable.RowSelected, "#workflows_data_table")
    def update_selected_row(self, event: DataTable.RowHighlighted | DataTable.RowSelected):
        self.workflows_data_table_selected_row = event.row_key

    @on(DataTable.HeaderSelected, "#workflows_data_table")
    def sort_workflows_by_header(self, event: DataTable.HeaderSelected) -> None:
        if event.column_key.value == ROW_NUMBER_COLUMN:
            return

        if self.workflows_data_table_sort_column == event.column_key.value:
            self.workflows_data_table_sort_reverse = not self.workflows_data_table_sort_reverse
        else:
            self.workflows_data_table_sort_column = event.column_key.value
            self.workflows_data_table_sort_reverse = False

        sort_data_table(self.query_one("#workflows_data_table", DataTable), event.column_key.value, self.workflows_data_table_sort_reverse)

        if self.workflows_data_table_selected_row is not None:
            table = self.query_one("#workflows_data_table", DataTable)
            table.move_cursor(row=table.get_row_index(self.workflows_data_table_selected_row), scroll=True)

    def handle_save_workflow(self, workflow):
        if workflow:
            try:
                self.backend.save_workflow(workflow)
                self.notify(message=t(t.DATA_UPD), title=t(t.INFORMATION), severity="information", markup=True)
                self.action_refresh_content()
            except Exception as e:
                logging.error("TUI: Saving workflow failed (%s)", type(e).__name__)
                error_stack = traceback.format_exc()
                self.notify(str(error_stack), title=t(t.ERROR), severity="error", timeout=ERROR_NOTE_TIMEOUT)
        else:
            self.notify(t(t.NO_UPD), title=t(t.INFORMATION), severity="information")

    @on(Button.Pressed, "#workflows-add-btn")
    def action_workflows_data_table_add(self) -> None:
        if self.backend.file_path:
            self.app.push_screen(WorkflowEditor(workflow=None, backend=self.backend), callback=self.handle_save_workflow)
        else:
            self.notify(message=t(t.ERR_NO_FILE_SELECTED), title=t(t.INFORMATION), severity="information", markup=True)

    @on(Button.Pressed, "#workflows-edit-btn")
    def action_workflows_data_table_modify_selected(self) -> None:
        if self.workflows_data_table_selected_row is None:
            self.notify(message=t(t.ERR_NO_ROW_SELECTED), title=t(t.INFORMATION), severity="information", markup=True)
        else:
            if self.backend.file_path:
                workflow_id = self.workflows_data_table_selected_row.value
                workflow = self.backend.get_workflow(workflow_id)
                self.app.push_screen(WorkflowEditor(workflow=workflow, backend=self.backend), callback=self.handle_save_workflow)
            else:
                self.notify(message=t(t.ERR_NO_FILE_SELECTED), title=t(t.INFORMATION), severity="information", markup=True)

    @on(Button.Pressed, "#workflow-execute-btn")
    def action_workflows_data_table_execute_selected(self) -> None:
        if self.workflows_data_table_selected_row is None:
            self.notify(message=t(t.ERR_NO_ROW_SELECTED), title=t(t.INFORMATION), severity="information", markup=True)
        else:
            record_id = self.workflows_data_table_selected_row.value
            logging.info("TUI: Executing selected workflow id=%s", record_id)
            self.app.push_screen(ExecutionProgress(
                partial(self.backend.run_workflow, record_id), "workflow", record_id,
            ))

    @on(Button.Pressed, "#workflows-delete-btn")
    def action_workflows_data_table_delete_selected(self) -> None:
        def perform_delete(workflow_id):
            if workflow_id is not None:
                try:
                    self.backend.delete_workflow(workflow_id)
                    self.notify(message=t(t.DATA_DLTD), title=t(t.INFORMATION), severity="warning", markup=True)
                    self.action_refresh_content()
                except Exception as e:
                    logging.error("TUI: Deleting workflow failed (%s)", type(e).__name__)
                    self.notify(str(e), title=t(t.ERROR), severity="error", timeout=ERROR_NOTE_TIMEOUT)
            else:
                self.notify(t(t.NO_UPD), title=t(t.INFORMATION), severity="information")

        if self.workflows_data_table_selected_row is None:
            self.notify(message=t(t.ERR_NO_ROW_SELECTED), title=t(t.INFORMATION), severity="information", markup=True)
        else:
            if self.backend.file_path:
                workflow_id = self.workflows_data_table_selected_row.value
                self.app.push_screen(
                    YesNoQuestion(t(t.CONFIRM_DELETE)),
                    callback=lambda confirmed: perform_delete(workflow_id) if confirmed else self.notify(t(t.NO_UPD), title=t(t.INFORMATION), severity="information")
                )
            else:
                self.notify(message=t(t.ERR_NO_FILE_SELECTED), title=t(t.INFORMATION), severity="information", markup=True)

    @on(events.Mount)
    def loading_dialog(self, event: events.Mount):
        self.action_refresh_content()

    @on(Button.Pressed, "#workflows-cancel-btn")
    def action_cancel_dialog(self) -> None:
        self.dismiss()

    def action_refresh_content(self, column_ordering_function=None):

        workflows_data_table = self.query_one("#workflows_data_table", DataTable)
        filter_text = self.query_one("#workflows_filter", Input).value.strip().casefold()
        columns, rows, keys = format_data_table(
            self.backend.file_data["workflows"],
            column_ordering_function=column_ordering_function,
            ignore_columns=self.ignore_columns
        )
        refresh_data_table(
            workflows_data_table, columns, rows, keys,
            filter_text=filter_text,
            sort_column=self.workflows_data_table_sort_column,
            sort_reverse=self.workflows_data_table_sort_reverse,
        )

        self.workflows_data_table_selected_row = None
        if workflows_data_table.row_count:
            workflows_data_table.move_cursor(row=0)
            self.workflows_data_table_selected_row = workflows_data_table.coordinate_to_cell_key(workflows_data_table.cursor_coordinate).row_key

class VariableEditor(ModalScreen):
    BINDINGS = [("escape", "cancel_dialog", t(t.CANCEL))]

    def __init__(self, name=None, value="", existing_names=()):
        super().__init__()
        self.variable_name = name
        self.value = value
        self.existing_names = set(existing_names) - {name}

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog-container"):
            yield Label(t(t.VARIABLE_EDITOR), classes="title")
            yield Label(t(t.NAME))
            yield Input(value=self.variable_name or "", id="variable-name")
            yield Label(t(t.VALUE_TYPE))
            yield Select([(t(t.TEXT), "text"), (t(t.JSON), "json")], value="text" if isinstance(self.value, str) else "json", allow_blank=False, id="variable-value-type")
            yield Label(t(t.VALUE))
            yield TextArea(self.value if isinstance(self.value, str) else json.dumps(self.value, ensure_ascii=False), id="variable-value").set_styles(height=6)
            with Horizontal(classes="button-container"):
                yield Button(t(t.CANCEL), id="variable-cancel-btn")
                yield Button(t(t.SAVE), variant="success", id="variable-save-btn")

    @on(Button.Pressed, "#variable-save-btn")
    def save_variable(self) -> None:
        name = self.query_one("#variable-name", Input).value.strip()
        if not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*", name):
            self.notify(t(t.ERR_VARIABLE_NAME), title=t(t.ERROR), severity="error")
            return
        if name in self.existing_names:
            self.notify(t(t.ERR_UNIQUE_ATTR_NAME), title=t(t.ERROR), severity="error")
            return
        value = self.query_one("#variable-value", TextArea).text
        if self.query_one("#variable-value-type", Select).value == "json":
            try:
                value = json.loads(value)
            except ValueError as error:
                self.notify(str(error), title=t(t.ERROR), severity="error", markup=False)
                return
        self.dismiss((name, value))

    @on(Button.Pressed, "#variable-cancel-btn")
    def action_cancel_dialog(self) -> None:
        self.dismiss()


class Variables(ModalScreen):
    AUTO_FOCUS = "#variables_data_table"
    BINDINGS = [
        ("escape", "cancel_dialog", t(t.CLOSE)),
        ("a", "add_variable", t(t.NEW_VARIABLE)),
        ("m", "edit_variable", t(t.MODIFY_VARIABLE)),
        ("d", "delete_variable", t(t.DELETE)),
    ]

    def __init__(self, backend):
        super().__init__()
        self.backend = backend

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Header(show_clock=True)
            yield Label(t(t.MANAGE_VARIABLES))
            yield Input(id="variables_filter", compact=True, placeholder=t(t.SEARCH_LABEL))
            yield DataTable(id="variables_data_table")
            with Horizontal(classes="button-container"):
                yield Button(t(t.CLOSE), id="variables-close-btn")
                yield Button(t(t.DELETE), variant="error", id="variables-delete-btn")
                yield Button(t(t.MODIFY), variant="primary", id="variables-edit-btn")
                yield Button(t(t.NEW), variant="success", id="variables-add-btn")
            yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#variables_data_table", DataTable)
        table.add_columns(t(t.NAME), t(t.VALUE))
        table.cursor_type = "row"
        table.zebra_stripes = True
        self.refresh_variables()

    @on(Input.Changed, "#variables_filter")
    def filter_variables(self, event: Input.Changed) -> None:
        self.refresh_variables()

    @on(Input.Submitted, "#variables_filter")
    def filter_submitted(self, event: Input.Submitted) -> None:
        self.query_one("#variables_data_table", DataTable).focus()

    def refresh_variables(self, selected_name=None) -> None:
        table = self.query_one("#variables_data_table", DataTable)
        filter_text = self.query_one("#variables_filter", Input).value.strip().casefold()
        table.clear()
        visible_names = []
        for name, value in self.backend.file_data.get("variables", {}).items():
            text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
            if filter_text and not any(filter_text in cell.casefold() for cell in (name, text)):
                continue
            table.add_row(Text(name), Text(text), key=name)
            visible_names.append(name)
        if table.row_count:
            row = table.get_row_index(selected_name) if selected_name in visible_names else 0
            table.move_cursor(row=row)

    def selected_name(self):
        table = self.query_one("#variables_data_table", DataTable)
        if table.row_count:
            coordinate = table.cursor_coordinate
            cell_key = table.coordinate_to_cell_key(coordinate)
            row_key = cell_key.row_key
            name = row_key.value
            return name
        self.notify(t(t.ERR_NO_ROW_SELECTED), title=t(t.INFORMATION))
        return None

    def handle_save_variable(self, result, old_name=None) -> None:
        if result is None:
            return
        name, value = result
        variables = dict(self.backend.file_data.get("variables", {}))
        if old_name is not None:
            variables.pop(old_name, None)
        variables[name] = value
        self.backend.save_variables(variables)
        self.refresh_variables(name)

    @on(Button.Pressed, "#variables-add-btn")
    def action_add_variable(self) -> None:
        self.app.push_screen(VariableEditor(existing_names=self.backend.file_data.get("variables", {})), callback=self.handle_save_variable)

    @on(Button.Pressed, "#variables-edit-btn")
    def action_edit_variable(self) -> None:
        name = self.selected_name()
        if name is not None:
            variables = self.backend.file_data.get("variables", {})
            self.app.push_screen(VariableEditor(name, variables[name], variables), callback=partial(self.handle_save_variable, old_name=name))

    # open Editor when selected:
    # @on(DataTable.RowSelected, "#variables_data_table")
    # def edit_selected_variable(self) -> None:
    #     self.action_edit_variable()

    @on(Button.Pressed, "#variables-delete-btn")
    def action_delete_variable(self) -> None:
        name = self.selected_name()
        if name is None:
            return

        def delete_variable(confirmed):
            if confirmed:
                variables = dict(self.backend.file_data.get("variables", {}))
                variables.pop(name, None)
                self.backend.save_variables(variables)
                self.refresh_variables()

        self.app.push_screen(YesNoQuestion(t(t.CONFIRM_DELETE)), callback=delete_variable)

    @on(Button.Pressed, "#variables-close-btn")
    def action_cancel_dialog(self) -> None:
        self.dismiss()


class KrestTui(App):

    CSS_PATH = "krest_tui.tcss"

    BINDINGS = [
        ("ctrl+o", "open_file", t(t.OPEN)),
        ("ctrl+n", "new_file", t(t.NEW)),
        ("ctrl+s", "save_file", t(t.SAVE)),
        ("ctrl+w", "close_file", t(t.CLOSE)),
        ("ctrl+q", "quit_krest", t(t.QUIT)),
        ("e", "edit_file", t(t.PFE)),  ### "Advanced Editor" - can kill memory if file too big ###
        # ("|", "none", "║"),
        ("a", "endpoints_data_table_add", t(t.NEW_ENDPOINT)),
        ("x", "endpoints_data_table_execute_selected", t(t.EXECUTE)),
        ("l", "endpoints_data_table_view_logs_selected", t(t.CALL_HISTORY)),
        ("m", "endpoints_data_table_modify_selected", t(t.MODIFY)),
        ("d", "endpoints_data_table_delete_selected", t(t.DELETE)),
        # ("S", "endpoints_data_table_sort_by_name", "Sort by Name"),
        # ("|", "none", "║"),
        ("c", "edit_credentials", t(t.MANAGE_CREDENTIALS)),
        ("w", "edit_workflows", t(t.MANAGE_WORKFLOWS)),
        ("v", "edit_variables", t(t.MANAGE_VARIABLES)),
        ("h", "view_all_logs", t(t.ALL_CALL_HISTORIES)),
        ("p", "properties", t(t.PROPERTIES)),
        ("ctrl+u", "change_password", t(t.CHANGE_PASSWORD)),
        ("f1", "about", t(t.ABOUT)),
    ]

    '''
    current_sorts: set = set()
    '''

    def __init__(self, *args, file_path=None, file_password=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.startup_file_path = file_path
        self.startup_file_password = file_password
        self.backend = KrestBackend()
        logging.debug("TUI: Application initialized")
        self.endpoints_data_table_selected_row = None
        self.endpoints_data_table_sort_column: str | None = None
        self.endpoints_data_table_sort_reverse = False

    def _handle_exception(self, error: Exception) -> None:
        logging.error("TUI: Unhandled application exception", exc_info=(type(error), error, error.__traceback__))
        super()._handle_exception(error)

    def on_unmount(self) -> None:
        self.backend.unload_file()

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        if action == "edit_file":
            return logging.getLogger().isEnabledFor(logging.DEBUG)
        if action in {
            "save_file",
            "close_file",
            "endpoints_data_table_add",
            "endpoints_data_table_execute_selected",
            "endpoints_data_table_view_logs_selected",
            "endpoints_data_table_modify_selected",
            "endpoints_data_table_delete_selected",
            "edit_credentials",
            "edit_workflows",
            "edit_variables",
            "view_all_logs",
            "properties",
            "change_password",
        }:
            return bool(self.backend.file_path)
        return super().check_action(action, parameters)

    def get_system_commands(self, screen: Screen) -> Iterable[SystemCommand]:
        # Textual calls this when Command Palette activated.
        yield from super().get_system_commands(screen)
        seen = set()
        for active_binding in screen.active_bindings.values():
            node, binding, enabled, _ = active_binding
            if node not in (self, screen) or not enabled or not binding.description:
                continue
            command = (node, binding.action)
            if command in seen or binding.action == "command_palette":
                continue
            seen.add(command)
            yield SystemCommand(
                binding.description,
                t(t.SHORTCUT, binding_key=binding.key),
                partial(self.run_action, binding.action, default_namespace=node),
            )

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        yield Static(t(t.FILE) + ": -", id="opened_file_name")
        endpoints_filter = Input(id="endpoints_filter", compact=True, placeholder=t(t.SEARCH_LABEL))
        endpoints_filter.display = bool(self.backend.file_path)
        yield endpoints_filter
        yield DataTable(id="endpoints_data_table")

        with Horizontal(classes="button-container", id="endpoints-actions") as endpoints_actions:
            endpoints_actions.display = bool(self.backend.file_path)
            yield Button(t(t.DELETE), variant="error", id="endpoints-delete-btn")
            yield Button(t(t.MODIFY), variant="primary", id="endpoints-edit-btn")
            yield Button(t(t.NEW), variant="success", id="endpoints-add-btn")
            yield Button(t(t.EXECUTE), variant="warning", id="endpoints-execute-btn")
            yield Button(t(t.CALL_HISTORY), variant="primary", id="endpoints-history-btn")

        yield Footer()


    @on(events.Mount)
    def update_screen_title(self) -> None:
        self.title = APP_TITLE
        self.sub_title = t(t.MOTTO) + f"  (v{version('krest-utils')}) "
        self.call_after_refresh(self.query_one("#endpoints_data_table", DataTable).focus)
        if self.startup_file_path is not None:
            self.perform_load(self.startup_file_path, self.startup_file_password)
            self.startup_file_password = None

    @on(Input.Changed, "#endpoints_filter")
    def filter_endpoints(self, event: Input.Changed) -> None:
        self.action_refresh_content()

    @on(Input.Submitted, "#endpoints_filter")
    def filter_submitted(self, event: Input.Submitted) -> None:
        self.query_one("#endpoints_data_table", DataTable).focus()

    @on(DataTable.HeaderSelected, "#endpoints_data_table")
    def sort_endpoints_by_header(self, event: DataTable.HeaderSelected) -> None:
        if event.column_key.value == ROW_NUMBER_COLUMN:
            return

        if self.endpoints_data_table_sort_column == event.column_key.value:
            self.endpoints_data_table_sort_reverse = not self.endpoints_data_table_sort_reverse
        else:
            self.endpoints_data_table_sort_column = event.column_key.value
            self.endpoints_data_table_sort_reverse = False

        sort_data_table(self.query_one("#endpoints_data_table", DataTable), event.column_key.value, self.endpoints_data_table_sort_reverse)

        if self.endpoints_data_table_selected_row is not None:
            table = self.query_one("#endpoints_data_table", DataTable)
            table.move_cursor(row=table.get_row_index(self.endpoints_data_table_selected_row), scroll=True)

    @on(DataTable.RowHighlighted, "#endpoints_data_table")
    @on(DataTable.RowSelected, "#endpoints_data_table")
    def update_selected_row(self, event: DataTable.RowHighlighted | DataTable.RowSelected):
        self.endpoints_data_table_selected_row = event.row_key

    def handle_save_endpoint(self, endpoint):
        if endpoint:
            try:
                self.backend.save_endpoint(endpoint)
                self.notify(message=t(t.DATA_UPD), title=t(t.INFORMATION), severity="information", markup=True)
                self.action_refresh_content()
            except Exception as e:
                logging.error("TUI: Saving endpoint failed (%s)", type(e).__name__)
                error_stack = traceback.format_exc()
                self.notify(str(error_stack), title=t(t.ERROR), severity="error", timeout=ERROR_NOTE_TIMEOUT)
        else:
            self.notify(t(t.NO_UPD), title=t(t.INFORMATION), severity="information")

    def action_none(self) -> None:
        pass

    def action_about(self) -> None:
        self.push_screen(About())

    def action_properties(self) -> None:
        if self.backend.file_path:
            self.push_screen(Properties(self.backend))
        else:
            self.notify(message=t(t.ERR_NO_FILE_SELECTED), title=t(t.INFORMATION), severity="information", markup=True)

    def action_change_password(self) -> None:
        if self.backend.file_path:
            self.push_screen(ChangePassword(self.backend))
        else:
            self.notify(message=t(t.ERR_NO_FILE_SELECTED), title=t(t.INFORMATION), severity="information", markup=True)

    @on(Button.Pressed, "#endpoints-history-btn")
    def action_endpoints_data_table_view_logs_selected(self) -> None:
        if self.endpoints_data_table_selected_row is None:
            self.notify(message=t(t.ERR_NO_ROW_SELECTED), title=t(t.INFORMATION), severity="information", markup=True)
        else:
            if self.backend.file_path:
                endpoint_id = self.endpoints_data_table_selected_row.value
                self.push_screen(CallHistoryViewer(self.backend, endpoint_id=endpoint_id))
            else:
                self.notify(message=t(t.ERR_NO_FILE_SELECTED), title=t(t.INFORMATION), severity="information", markup=True)

    def action_view_all_logs(self) -> None:
        if self.backend.file_path:
            self.push_screen(CallHistoryViewer(self.backend))
        else:
            self.notify(message=t(t.ERR_NO_FILE_SELECTED), title=t(t.INFORMATION), severity="information", markup=True)

    def action_edit_variables(self) -> None:
        if self.backend.file_path:
            self.push_screen(Variables(self.backend))
        else:
            self.notify(message=t(t.ERR_NO_FILE_SELECTED), title=t(t.INFORMATION), severity="information", markup=True)

    def action_edit_workflows(self) -> None:
        if self.backend.file_path:
            self.push_screen(Workflows(self.backend))
        else:
            self.notify(message=t(t.ERR_NO_FILE_SELECTED), title=t(t.INFORMATION), severity="information", markup=True)

    def action_edit_credentials(self) -> None:
        if self.backend.file_path:
            self.push_screen(Credentials(self.backend))
        else:
            self.notify(message=t(t.ERR_NO_FILE_SELECTED), title=t(t.INFORMATION), severity="information", markup=True)

    @on(Button.Pressed, "#endpoints-add-btn")
    def action_endpoints_data_table_add(self) -> None:
        if self.backend.file_path:
            available_credentials = [(str(credential["name"]), credential["id"]) for credential in self.backend.file_data.get("credentials")]
            self.push_screen(EndpointEditor(available_credentials=available_credentials, backend=self.backend), callback=self.handle_save_endpoint)
        else:
            self.notify(message=t(t.ERR_NO_FILE_SELECTED), title=t(t.INFORMATION), severity="information", markup=True)

    @on(Button.Pressed, "#endpoints-delete-btn")
    def action_endpoints_data_table_delete_selected(self) -> None:
        def perform_delete(endpoint_id):
            if endpoint_id:
                try:
                    self.backend.delete_endpoint(endpoint_id)
                    self.notify(message=t(t.DATA_DLTD), title=t(t.INFORMATION), severity="warning", markup=True)
                    self.action_refresh_content()
                except Exception as e:
                    logging.error("TUI: Deleting endpoint failed (%s)", type(e).__name__)
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

    @on(Button.Pressed, "#endpoints-edit-btn")
    def action_endpoints_data_table_modify_selected(self) -> None:
        if self.endpoints_data_table_selected_row is None:
            self.notify(message=t(t.ERR_NO_ROW_SELECTED), title=t(t.INFORMATION), severity="information", markup=True)
        else:
            if self.backend.file_path:
                endpoint_id = self.endpoints_data_table_selected_row.value
                endpoint = self.backend.get_endpoint(endpoint_id)

                available_credentials = [(str(credential["name"]), credential["id"]) for credential in self.backend.file_data.get("credentials")]
                self.push_screen(EndpointEditor(available_credentials=available_credentials, endpoint=endpoint, backend=self.backend), callback=self.handle_save_endpoint)
            else:
                self.notify(message=t(t.ERR_NO_FILE_SELECTED), title=t(t.INFORMATION), severity="information", markup=True)


    @on(Button.Pressed, "#endpoints-execute-btn")
    def action_endpoints_data_table_execute_selected(self) -> None:
        if self.endpoints_data_table_selected_row is None:
            self.notify(message=t(t.ERR_NO_ROW_SELECTED), title=t(t.INFORMATION), severity="information", markup=True)
        else:
            record_id = self.endpoints_data_table_selected_row.value
            logging.info("TUI: Executing selected endpoint id=%s", record_id)
            self.push_screen(ExecutionProgress(
                partial(self.backend.run_endpoint, record_id), "endpoint", record_id,
            ))
    '''
    def sort_reverse(self, sort_type: str):
        reverse = sort_type in self.current_sorts
        if reverse:
            self.current_sorts.remove(sort_type)
        else:
            self.current_sorts.add(sort_type)
        return reverse
    '''

    '''
    def action_endpoints_data_table_sort_by_name(self) -> None:
        self.action_refresh_content(row_ordering_function=lambda x: x.get("name", ""), column_ordering_function=None)
    '''

    def action_refresh_content(self, column_ordering_function=None) -> None:

        self.query_one("#opened_file_name", Static).content = t(t.FILE_NAME) + ": " + str(self.backend.file_path)

        endpoints_data_table = self.query_one("#endpoints_data_table", DataTable)
        endpoints_filter = self.query_one("#endpoints_filter", Input)
        endpoints_filter.display = bool(self.backend.file_path)
        self.query_one("#endpoints-actions", Horizontal).display = bool(self.backend.file_path)
        filter_text = endpoints_filter.value.strip().casefold()
        columns, rows, keys = format_data_table(
            [{**endpoint, "response_type": endpoint.get("response_type", ValueType.TEXT.value)} for endpoint in self.backend.file_data.get("endpoints", [])],
            column_ordering_function=column_ordering_function,
            ignore_columns=["headers", "body", "params"]
        )
        refresh_data_table(
            endpoints_data_table, columns, rows, keys,
            filter_text=filter_text,
            sort_column=self.endpoints_data_table_sort_column,
            sort_reverse=self.endpoints_data_table_sort_reverse,
        )

        self.endpoints_data_table_selected_row = None
        if endpoints_data_table.row_count:
            endpoints_data_table.move_cursor(row=0)
            self.endpoints_data_table_selected_row = endpoints_data_table.coordinate_to_cell_key(endpoints_data_table.cursor_coordinate).row_key

        self.refresh_bindings()

    def action_quit_krest(self) -> None:
        def perform_quit():
            logging.info("TUI: Quitting; unsaved_changes=%s", bool(self.backend.dirty_bit))
            self.exit()

        if self.backend.dirty_bit:
            logging.debug("TUI: Confirming unsaved changes before quitting")
            self.push_screen(
                YesNoQuestion(t(t.NOTE_UNSAVED_CHANGES)),
                callback=lambda confirmed: perform_quit() if confirmed else None
            )
        else:
            perform_quit()

    def action_close_file(self) -> None:
        def perform_close():
            self.backend.unload_file()
            self.action_refresh_content()

        if self.backend.dirty_bit:
            self.push_screen(
                YesNoQuestion(t(t.NOTE_UNSAVED_CHANGES)),
                callback=lambda confirmed: perform_close() if confirmed else None
            )
        else:
            perform_close()

    def action_edit_file(self) -> None:

        def handle_update_file_data(result) -> None:
            if result:
                try:
                    self.backend.file_data = json.loads(result)
                    self.backend.dirty_bit = True
                    logging.info("TUI: Applied advanced file edits")
                    self.action_refresh_content()
                except Exception as e:
                    logging.error("TUI: Applying advanced file edits failed (%s)", type(e).__name__)
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
            logging.debug("TUI: Save skipped: no file selected")
            self.notify(message=t(t.ERR_NO_FILE_SELECTED), title=t(t.INFORMATION), severity="information", markup=True)
        else:
            if self.backend.dirty_bit:
                try:
                    self.backend.save_file()
                    self.notify(message=t(t.FILE_SAVED), title=t(t.INFORMATION), severity="information", markup=True)
                except Exception as e:
                    logging.error("TUI: Saving file failed (%s)", type(e).__name__)
                    error_stack = traceback.format_exc()
                    self.notify(str(error_stack), title=t(t.ERROR), severity="error", timeout=ERROR_NOTE_TIMEOUT)
            else:
                logging.debug("TUI: Save skipped: no unsaved changes")
                self.notify(message=t(t.FILE_NOSAVE), title=t(t.INFORMATION), severity="information", markup=True)

    def action_new_file(self) -> None:

        def perform_create_file(path, password):
            try:
                self.backend.unload_file()
            except OSError as e:
                self.notify(str(e), title=t(t.ERROR), severity="error", timeout=ERROR_NOTE_TIMEOUT)
                return
            try:
                if Path(path + ".krest.lock").exists():
                    raise FileExistsError(t(t.ERR_FILE_LOCKED))
                self.backend.create_file(path, password)
                self.backend.load_file()
            except Exception as e:
                logging.error("TUI: Creating file failed (%s)", type(e).__name__)
                self.backend.file_path = None
                self.backend.unload_file()
                self.action_refresh_content()
                error_stack = traceback.format_exc()
                self.notify(str(error_stack), title=t(t.ERROR), severity="error", timeout=ERROR_NOTE_TIMEOUT)
            else:
                self.action_refresh_content()
                self.notify(message=t(t.FILE_CREATED), title=t(t.INFORMATION), severity="information", markup=True)

        def perform_new_file():

            def handle_selection_dialog(result):

                if result:
                    path, password = result
                    if path is None or path == "":
                        self.notify(message=t(t.ERR_NO_FILE_SELECTED), title=t(t.INFORMATION), severity="information", markup=True)
                        return
                else:
                    logging.debug("TUI: New file selection cancelled")
                    #selecting cancelled
                    return

                if Path(path).is_file():
                    logging.debug("TUI: Requesting confirmation to overwrite file")
                    self.push_screen(
                        YesNoQuestion(t(t.FILE_EXISTS)),
                        callback=lambda confirmed: perform_create_file(path, password) if confirmed else None
                    )
                else:
                    perform_create_file(path, password)

            self.push_screen(OpenFileDialog(new_file=True), callback=handle_selection_dialog)

        if self.backend.dirty_bit:
            logging.debug("TUI: Confirming unsaved changes before creating a file")
            self.push_screen(
                YesNoQuestion(t(t.NOTE_UNSAVED_CHANGES)),
                callback=lambda confirmed: perform_new_file() if confirmed else None
            )
        else:
            perform_new_file()

    def perform_load(self, file_path, file_password):
        try:
            self.backend.unload_file()
        except OSError as e:
            self.notify(str(e), title=t(t.ERROR), severity="error", timeout=ERROR_NOTE_TIMEOUT)
            return
        try:
            self.backend.file_path, self.backend.file_password = file_path, file_password
            self.backend.load_file()
        except Exception as e:
            logging.error("TUI: Opening file failed (%s)", type(e).__name__)
            self.backend.file_path = None
            self.backend.unload_file()
            self.notify(str(e), title=t(t.ERROR), severity="error", timeout=ERROR_NOTE_TIMEOUT)
        else:
            self.notify(message=t(t.FILE_LOADED, file_path=file_path), title=t(t.INFORMATION), severity="information", markup=True)
        self.action_refresh_content()

    def action_open_file(self) -> None:

        def handle_file_open_dialog(result):
            if result:
                path, password = result
                if path is None or path == "":
                    self.notify(message=t(t.ERR_NO_FILE_SELECTED), title=t(t.INFORMATION), severity="information", markup=True)
                    return
            else:
                logging.debug("TUI: Open file selection cancelled")
                #opening cancelled
                return

            if self.backend.dirty_bit:
                logging.debug("TUI: Confirming unsaved changes before opening a file")
                self.push_screen(
                    YesNoQuestion(t(t.NOTE_UNSAVED_CHANGES)),
                    callback=lambda confirmed: self.perform_load(path, password) if confirmed else None
                )
            else:
                self.perform_load(path, password)

        self.push_screen(OpenFileDialog(), callback=handle_file_open_dialog)

def prompt_file_password(file_path):
    backend = KrestBackend()
    for attempt in range(3):
        try:
            password = getpass.getpass(t(t.PASSWORD))
        except (EOFError, KeyboardInterrupt):
            print("\n" + t(t.ERR_CANCEL_OPEN_FILE), file=sys.stderr)
            raise SystemExit(1) from None
        try:
            backend.select_file(file_path, password)
            backend.load_file()
            backend.unload_file()
            return password
        except ValueError as error:
            if str(error) != t(t.ERR_INVALID_PASSWD):
                print(str(error), file=sys.stderr)
                raise SystemExit(1) from None
            print(f"{error} ({attempt + 1}/3)", file=sys.stderr)
        except OSError as error:
            print(str(error), file=sys.stderr)
            raise SystemExit(1) from None
    raise SystemExit(1)


def tui():
    parser = argparse.ArgumentParser(description=APP_TITLE)
    parser.add_argument("--debug", "-d", action="store_true", help=t(t.INFO_DEBUG))
    parser.add_argument("--debug_level", type=int, metavar="INTEGER", help=t(t.INFO_DEBUG_LEVEL))
    parser.add_argument("--file", "-f", metavar="FILE_PATH", help=t(t.INFO_FILE))
    args = parser.parse_args()

    if args.debug_level:
        setup_logging(LOG_LEVELS.get(args.debug_level, logging.CRITICAL))
    elif args.debug:
        setup_logging(logging.DEBUG)
    else:
       logging.disable(logging.CRITICAL)

    file_password = prompt_file_password(args.file) if args.file is not None else None

    logging.info('TUI: Start...')
    krest_main_page = None
    try:
        krest_main_page = KrestTui(file_path=args.file, file_password=file_password)
        krest_main_page.run()
        if krest_main_page.return_code:
            logging.error("TUI: Exited with status %s", krest_main_page.return_code)
            raise SystemExit(krest_main_page.return_code)
    except Exception:
        logging.exception("TUI: Application failed")
        raise
    finally:
        if krest_main_page is not None:
            krest_main_page.backend.unload_file()
        krest_main_page = None
        gc.collect()
    logging.info('TUI: End.')

def main():
    tui()

if __name__ == "__main__":
    tui()


