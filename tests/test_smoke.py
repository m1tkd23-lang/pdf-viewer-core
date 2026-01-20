# tests/test_smoke.py
"""
最低限のスモークテスト。
importできること、および main() が呼べることだけを確認する。
"""

def test_import():
    import pdf_viewer_core.core  # noqa: F401


def test_main_runs(capsys):
    from pdf_viewer_core.core import main

    main()
    out = capsys.readouterr().out
    assert "pdf_viewer_core is running" in out
