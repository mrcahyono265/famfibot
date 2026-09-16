from app.main import _help_text


def test_group_help_excludes_private_commands() -> None:
    help_text = _help_text(False)

    assert "/gabung" in help_text
    assert "/saldo" not in help_text


def test_private_help_includes_member_approval() -> None:
    assert "/anggota setujui <nama>" in _help_text(True)
