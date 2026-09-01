from quick_tdsnr.ui.application import create_application
from quick_tdsnr.ui.pages.time_domain_page import TimeDomainPage


def test_time_domain_page_emits_valid_settings_and_rejects_invalid_values():
    app = create_application(["qts-test"])
    page = TimeDomainPage()
    emitted = []
    page.settings_confirmed.connect(emitted.append)
    page._emit_settings()
    app.processEvents()
    assert emitted and emitted[0].ui_ps == 100
    page.dt_edit.setText("0")
    page._emit_settings()
    assert not page.is_valid()
    assert "有限正数" in page.status_label.text()
