import asyncio
from copy import deepcopy

from textual.app import App
from textual.widgets import Button, DataTable, Input, Select

from krest.krest_backend import KrestBackend, empty_workflow
from krest.krest_tui import KrestTui, WorkflowEditor, Workflows
from krest import krest_tui


def test_workflow_editor_order_save_and_cancel():
    async def check():
        backend = KrestBackend()
        backend.file_data['endpoints'] = [{'id': 0, 'name': 'Login'}, {'id': 7, 'name': 'Fetch'}]
        workflow = empty_workflow()
        workflow['steps'] = [7, 99]
        original = deepcopy(workflow)
        app = App(css_path=krest_tui.Path(krest_tui.__file__).with_suffix(".tcss"))
        saved = []
        async with app.run_test(size=(120, 50)) as pilot:
            editor = WorkflowEditor(workflow, backend)
            app.push_screen(editor, saved.append)
            await pilot.pause()
            table = editor.query_one('#workflow-steps', DataTable)
            assert str(table.get_row_at(0)[1]) == 'Fetch'
            assert str(table.get_row_at(1)[1]) == 'Missing endpoint'
            editor.query_one('#workflow-endpoint', Select).value = 0
            editor.add_step()
            editor.add_step()
            editor.move_step(Button.Pressed(editor.query_one('#workflow-step-up', Button)))
            assert editor.steps == [7, 99, 0, 0]
            table.move_cursor(row=1)
            editor.remove_step()
            table.move_cursor(row=1)
            editor.move_step(Button.Pressed(editor.query_one('#workflow-step-up', Button)))
            assert editor.steps == [0, 7, 0]
            editor.query_one('#labels', Input).value = '{}'
            editor.action_apply()
            await pilot.pause()
            assert not saved
            editor.query_one('#labels', Input).value = "['smoke']"
            editor.query_one('#name', Input).value = 'Smoke test'
            editor.action_apply()
            await pilot.pause()
            assert saved[0]['steps'] == [0, 7, 0]
            assert saved[0]['name'] == 'Smoke test'
            assert workflow == original
            editor = WorkflowEditor(workflow, backend)
            app.push_screen(editor, saved.append)
            await pilot.pause()
            editor.remove_step()
            editor.action_cancel_dialog()
            await pilot.pause()
            assert workflow == original
            assert saved[-1] is None
    asyncio.run(check())


def test_workflow_manager_old_file_create_update_delete():
    async def check():
        backend = KrestBackend()
        backend.file_path = 'test.krest'
        backend.file_data.pop('workflows', None)
        backend.file_data.pop('max_workflow_id', None)
        backend.dirty_bit = False
        app = App(css_path=krest_tui.Path(krest_tui.__file__).with_suffix(".tcss"))
        async with app.run_test(size=(120, 50)) as pilot:
            manager = Workflows(backend)
            app.push_screen(manager)
            await pilot.pause()
            assert backend.file_data['workflows'] == []
            assert not backend.dirty_bit
            manager.action_workflows_data_table_add()
            await pilot.pause()
            editor = app.screen
            assert isinstance(editor, WorkflowEditor)
            editor.query_one('#name', Input).value = 'First'
            editor.action_apply()
            await pilot.pause()
            assert backend.dirty_bit
            assert len(backend.file_data['workflows']) == 1
            backend.dirty_bit = False
            manager.action_workflows_data_table_modify_selected()
            await pilot.pause()
            app.screen.query_one('#name', Input).value = 'Updated'
            app.screen.action_apply()
            await pilot.pause()
            assert backend.dirty_bit
            assert len(backend.file_data['workflows']) == 1
            assert backend.file_data['workflows'][0]['name'] == 'Updated'
            manager.action_workflows_data_table_delete_selected()
            await pilot.pause()
            app.screen.dismiss(True)
            await pilot.pause()
            assert backend.file_data['workflows'] == []
    asyncio.run(check())


def test_workflow_binding_requires_file():
    app = KrestTui()
    assert ('w', 'edit_workflows', 'Manage Workflows') in app.BINDINGS
    assert not app.check_action('edit_workflows', ())
    app.backend.file_path = 'test.krest'
    assert app.check_action('edit_workflows', ())
