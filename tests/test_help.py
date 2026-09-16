from app.main import _help_text


def test_help_lists_group_and_private_commands() -> None:
    help_text = _help_text(False)

    for command in (
        "/start",
        "/help",
        "/setup",
        "/hubungkan-group",
        "/gabung",
        "/anggota",
        "/ganti-komunitas",
        "/wallet",
        "/saldo",
        "/masuk",
        "/keluar",
        "/transfer",
        "/cek",
        "/laporan",
        "/undo",
        "/export-laporan-pdf",
    ):
        assert command in help_text


def test_private_help_includes_member_approval() -> None:
    assert "/anggota setujui <nama>" in _help_text(True)
