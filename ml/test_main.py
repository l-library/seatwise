import pytest

import main


@pytest.mark.parametrize("task", sorted(main.TASKS))
def test_task_prints_and_returns_zero(task: str, capsys: pytest.CaptureFixture[str]) -> None:
    assert main.main(["--task", task]) == 0
    assert task in capsys.readouterr().out


def test_unknown_task_is_rejected() -> None:
    with pytest.raises(SystemExit) as excinfo:
        main.main(["--task", "unknown"])
    assert excinfo.value.code == 2
