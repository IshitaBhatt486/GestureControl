from unittest.mock import MagicMock

from handwave.actions.action_mapper import ActionMapper
from handwave.actions.action_queue import ActionQueue, ActionWorker


def test_action_queue_executes_accepted_actions_in_order(qtbot):
    actions = ActionQueue()
    calls = []
    actions.submit("first", lambda: calls.append("first"))
    actions.submit("second", lambda: calls.append("second"))
    actions.close()

    worker = ActionWorker(actions)
    with qtbot.waitSignal(worker.stopped):
        worker.run()

    assert calls == ["first", "second"]


def test_action_mapper_can_queue_without_blocking_on_os_call():
    actions = ActionQueue()
    gui = MagicMock()
    mapper = ActionMapper(
        pyautogui_module=gui,
        keyboard_module=MagicMock(),
        dispatcher=actions.submit,
    )

    assert mapper.execute("Open Palm")
    gui.press.assert_not_called()
    actions.close()
    ActionWorker(actions).run()
    gui.press.assert_called_once_with("playpause")


def test_action_failure_does_not_discard_later_actions(qtbot):
    actions = ActionQueue()
    calls = []

    def fail():
        raise RuntimeError("expected test failure")

    actions.submit("failure", fail)
    actions.submit("success", lambda: calls.append("success"))
    actions.close()
    worker = ActionWorker(actions)

    with qtbot.waitSignal(worker.stopped):
        worker.run()

    assert calls == ["success"]


def test_shutdown_discards_actions_that_have_not_started(qtbot):
    actions = ActionQueue()
    calls = []
    actions.submit("stale", lambda: calls.append("stale"))
    actions.close(discard_pending=True)

    worker = ActionWorker(actions)
    with qtbot.waitSignal(worker.stopped):
        worker.run()

    assert calls == []


def test_profile_change_after_shutdown_keeps_worker_stop_sentinel(qtbot):
    actions = ActionQueue()
    actions.close(discard_pending=True)
    actions.discard_pending()

    worker = ActionWorker(actions)
    with qtbot.waitSignal(worker.stopped):
        worker.run()
