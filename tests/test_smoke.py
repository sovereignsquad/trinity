from trinity_core import __doc__


def test_package_imports() -> None:
    assert __doc__ is not None

