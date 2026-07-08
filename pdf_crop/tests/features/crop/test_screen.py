import fitz
import pytest

from pdf_crop.app import PdfCropApp
from pdf_crop.features.crop.screen import CropScreen
import zbar_skip


def test_screen_default_sanitize_false(three_page_pdf):
    screen = CropScreen(three_page_pdf)
    assert screen._sanitize_default is False


def test_screen_accepts_sanitize_kwarg(three_page_pdf):
    screen = CropScreen(three_page_pdf, sanitize=True)
    assert screen._sanitize_default is True


def test_app_threads_sanitize_to_screen(three_page_pdf):
    app = PdfCropApp(three_page_pdf, sanitize=True)
    assert app._sanitize is True


def test_app_threads_output_to_screen(three_page_pdf):
    app = PdfCropApp(three_page_pdf, output="~/out")
    assert app._output == "~/out"


async def test_output_input_prefilled_from_constructor_arg(three_page_pdf):
    app = PdfCropApp(three_page_pdf, output="~/out/report.pdf")
    async with app.run_test(size=(120, 60)) as pilot:
        screen = app.screen
        assert screen.query_one("#output_input").value == "~/out/report.pdf"


async def test_output_input_blank_when_no_output_arg(three_page_pdf):
    app = PdfCropApp(three_page_pdf)
    async with app.run_test(size=(120, 60)) as pilot:
        screen = app.screen
        assert screen.query_one("#output_input").value == ""


def test_crop_worker_receives_output_from_main_thread(three_page_pdf):
    # _crop_worker runs on a background thread (@work(thread=True)), which must
    # not touch the DOM. The output-path value is read on the main thread in
    # _start_crop and threaded in, so it appears as a worker parameter rather
    # than being read via query_one inside the worker.
    import inspect

    params = inspect.signature(CropScreen._crop_worker).parameters
    assert "output" in params


async def test_crop_writes_to_resolved_output_input_path(three_page_pdf, tmp_path):
    folder = tmp_path / "somewhere"
    app = PdfCropApp(three_page_pdf)
    async with app.run_test(size=(120, 60)) as pilot:
        screen = app.screen
        screen.query_one("#range_input").value = "1"
        screen.query_one("#output_input").value = str(folder)
        await pilot.pause()
        await pilot.click("#crop_btn")
        await app.workers.wait_for_complete()
        await pilot.pause()
        result = str(screen.query_one("#result_msg").content)
        assert "Wrote" in result

    assert (folder / "three_cropped.pdf").exists()


async def test_typing_output_input_does_not_clear_redaction_preview(text_pdf_factory):
    # The output-path field doesn't affect what a redaction scan finds, so
    # typing into it must not clear the "Found: …" preview or re-disable
    # "Apply redaction" — unlike the category checkboxes.
    src = text_pdf_factory(["CLABE 002010077777777771 fin"])
    app = PdfCropApp(src)
    async with app.run_test(size=(120, 60)) as pilot:
        screen = app.screen
        screen.query_one("#range_input").value = "1"
        screen.query_one("#cat_clabe_chk").value = True
        await pilot.pause()
        await pilot.click("#scan_btn")
        await app.workers.wait_for_complete()
        await pilot.pause()
        apply_chk = screen.query_one("#apply_redaction_chk")
        assert apply_chk.disabled is False
        apply_chk.value = True
        screen.query_one("#output_input").value = "some/output/path"
        await pilot.pause()
        assert apply_chk.value is True
        assert apply_chk.disabled is False
        assert "Found" in str(screen.query_one("#preview_msg").content)


async def test_crop_button_reachable_in_short_terminal(three_page_pdf):
    # The redact/QR/OCR/sanitize/metadata options make the form taller than a
    # normal terminal, and the action buttons sit at the very bottom. The form
    # must scroll, or "Crop" is clipped off-screen and unreachable.
    app = PdfCropApp(three_page_pdf)
    async with app.run_test(size=(80, 20)) as pilot:
        screen = app.screen
        crop_btn = screen.query_one("#crop_btn")
        crop_btn.scroll_visible(animate=False)
        await pilot.pause()
        assert screen.region.contains_region(crop_btn.region)


@pytest.mark.parametrize("size", [(120, 40), (200, 60)])
async def test_action_buttons_not_clipped_by_footer(three_page_pdf, size):
    # The Crop/Cancel buttons live in the bottom action bar. They must sit *above*
    # the Footer, fully visible — not have their bottom row hidden behind the
    # footer (which also docks bottom). Regression for the dock-edge collision
    # that clipped the last button row off-screen.
    from textual.widgets import Footer

    app = PdfCropApp(three_page_pdf)
    async with app.run_test(size=size) as pilot:
        await pilot.pause()
        screen = app.screen
        footer = screen.query_one(Footer)
        crop_btn = screen.query_one("#crop_btn")
        cancel_btn = screen.query_one("#cancel_btn")
        assert crop_btn.region.bottom <= footer.region.y
        assert cancel_btn.region.bottom <= footer.region.y


async def test_crop_body_fills_header_to_action_bar(three_page_pdf):
    # The two-pane body (controls + preview) must use the full vertical space
    # between the Header and the action bar — no wasted band. Its top sits just
    # below the Header and its bottom meets the action bar's top.
    from textual.widgets import Header

    app = PdfCropApp(three_page_pdf)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        screen = app.screen
        header = screen.query_one(Header)
        body = screen.query_one("#crop_body")
        action_bar = screen.query_one("#action_bar")
        assert body.region.y == header.region.bottom
        assert body.region.bottom == action_bar.region.y


async def test_list_metadata_button_renders_inventory(pdf_with_metadata):
    app = PdfCropApp(pdf_with_metadata)
    async with app.run_test(size=(120, 60)) as pilot:
        screen = app.screen
        await pilot.click("#list_metadata_btn")
        await pilot.pause()
        msg = str(screen.query_one("#metadata_msg").content)
        assert "Metadata:" in msg
        assert "total" in msg


async def test_sanitize_checkbox_strips_on_crop(pdf_with_metadata):
    from pdf_crop.features.sanitize.service import inventory
    from pdf_crop.shared.pdf_io import open_pdf

    app = PdfCropApp(pdf_with_metadata)
    async with app.run_test(size=(120, 60)) as pilot:
        screen = app.screen
        screen.query_one("#range_input").value = "1"
        screen.query_one("#sanitize_chk").value = True
        await pilot.pause()
        await pilot.click("#crop_btn")
        await app.workers.wait_for_complete()
        await pilot.pause()

    out = pdf_with_metadata.with_name("with_metadata_xmp_cropped.pdf")
    assert inventory(open_pdf(out)).total() == 0


async def test_scan_then_redact_writes_clean_pdf(text_pdf_factory):
    src = text_pdf_factory(["CLABE 002010077777777771 fin"])
    app = PdfCropApp(src)
    async with app.run_test(size=(120, 60)) as pilot:
        screen = app.screen
        screen.query_one("#range_input").value = "1"
        screen.query_one("#cat_clabe_chk").value = True
        await pilot.pause()
        await pilot.click("#scan_btn")
        await app.workers.wait_for_complete()
        await pilot.pause()
        preview = str(screen.query_one("#preview_msg").content)
        assert "1" in preview
        assert screen.query_one("#apply_redaction_chk").disabled is False
        screen.query_one("#apply_redaction_chk").value = True
        await pilot.click("#crop_btn")
        await app.workers.wait_for_complete()
        await pilot.pause()

    from pdf_crop.shared.pdf_io import open_pdf
    out = next(p for p in src.parent.glob("*_cropped*.pdf"))
    assert "002010077777777771" not in open_pdf(out).pages[0].extract_text()


async def test_scan_no_matches_keeps_apply_disabled(text_pdf_factory):
    src = text_pdf_factory(["nothing to see here"])
    app = PdfCropApp(src)
    async with app.run_test(size=(120, 60)) as pilot:
        screen = app.screen
        screen.query_one("#range_input").value = "1"
        screen.query_one("#cat_clabe_chk").value = True
        await pilot.pause()
        await pilot.click("#scan_btn")
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert screen.query_one("#apply_redaction_chk").disabled is True
        assert "nothing to redact" in str(screen.query_one("#preview_msg").content)


async def test_apply_redaction_survives_independent_toggles(text_pdf_factory):
    # Toggling the non-scan checkboxes (QR/OCR/sanitize) must not silently
    # un-check or re-disable an already-enabled "Apply redaction" — those toggles
    # don't invalidate the scan preview. Regression for the deselect bug.
    src = text_pdf_factory(["CLABE 002010077777777771 fin"])
    app = PdfCropApp(src)
    async with app.run_test(size=(120, 60)) as pilot:
        screen = app.screen
        screen.query_one("#range_input").value = "1"
        screen.query_one("#cat_clabe_chk").value = True
        await pilot.pause()
        await pilot.click("#scan_btn")
        await app.workers.wait_for_complete()
        await pilot.pause()
        apply_chk = screen.query_one("#apply_redaction_chk")
        assert apply_chk.disabled is False
        apply_chk.value = True
        for chk_id in ("#redact_qr_chk", "#ocr_chk", "#sanitize_chk"):
            screen.query_one(chk_id).value = True
            await pilot.pause()
            assert apply_chk.value is True
            assert apply_chk.disabled is False


async def test_category_toggle_still_resets_apply(text_pdf_factory):
    # Toggling a scan-category checkbox *does* invalidate the preview, so it still
    # clears the "Found: …" summary and resets "Apply redaction".
    src = text_pdf_factory(["CLABE 002010077777777771 fin"])
    app = PdfCropApp(src)
    async with app.run_test(size=(120, 60)) as pilot:
        screen = app.screen
        screen.query_one("#range_input").value = "1"
        screen.query_one("#cat_clabe_chk").value = True
        await pilot.pause()
        await pilot.click("#scan_btn")
        await app.workers.wait_for_complete()
        await pilot.pause()
        apply_chk = screen.query_one("#apply_redaction_chk")
        apply_chk.value = True
        screen.query_one("#cat_card_chk").value = True
        await pilot.pause()
        assert apply_chk.value is False
        assert apply_chk.disabled is True
        assert str(screen.query_one("#preview_msg").content) == ""


@zbar_skip.SKIP
async def test_scan_lists_found_qr_codes(qr_pdf_factory):
    src = qr_pdf_factory(["CLABE002010077777777771"])
    app = PdfCropApp(src)
    async with app.run_test(size=(120, 60)) as pilot:
        screen = app.screen
        screen.query_one("#range_input").value = "1"
        screen.query_one("#redact_qr_chk").value = True
        await pilot.pause()
        await pilot.click("#scan_btn")
        await app.workers.wait_for_complete()
        await pilot.pause()
        preview = str(screen.query_one("#preview_msg").content)
        # The decoded payload is exposed so the user can verify it's their data.
        assert "CLABE002010077777777771" in preview


async def test_crop_shows_error_on_qr_second_pass_failure(text_pdf_factory, monkeypatch):
    # A decode/imaging failure in the QR second pass must surface as the red
    # error message (translated to PdfCropError), not an uncaught traceback.
    from pdf_crop.features.qr_redact import service as qr_service

    findings = qr_service.QrFindings()
    findings.codes.append(
        qr_service.QrCode(page=1, symbology="QRCODE", payload="x", rect=None)
    )
    monkeypatch.setattr(qr_service, "scan", lambda *a, **k: findings)

    def boom(*a, **k):
        raise ValueError("pyzbar decode failure")

    monkeypatch.setattr(qr_service, "redact", boom)

    src = text_pdf_factory(["no real qr here, redact is faked"])
    app = PdfCropApp(src)
    async with app.run_test(size=(120, 60)) as pilot:
        screen = app.screen
        screen.query_one("#range_input").value = "1"
        screen.query_one("#redact_qr_chk").value = True
        await pilot.pause()
        await pilot.click("#crop_btn")
        await app.workers.wait_for_complete()
        await pilot.pause()
        error = str(screen.query_one("#error_msg").content)
        assert "QR" in error or "redaction failed" in error


async def test_crop_runs_ocr_second_pass_with_selected_categories(text_pdf_factory, monkeypatch):
    # When #ocr_chk is ticked, the OCR second pass runs over the written file
    # using the selected category checkboxes + names input.
    from pdf_crop.features.crop import command

    calls = {}

    def fake_ocr(dest, *, categories, names):
        calls["dest"] = dest
        calls["categories"] = categories
        calls["names"] = names
        return 0

    monkeypatch.setattr(command, "_redact_ocr_in_place", fake_ocr)

    src = text_pdf_factory(["some text"])
    app = PdfCropApp(src)
    async with app.run_test(size=(120, 60)) as pilot:
        screen = app.screen
        screen.query_one("#range_input").value = "1"
        screen.query_one("#ocr_chk").value = True
        screen.query_one("#cat_clabe_chk").value = True
        screen.query_one("#names_input").value = "Jane Doe"
        screen.query_one("#cat_name_chk").value = True
        await pilot.pause()
        await pilot.click("#crop_btn")
        await app.workers.wait_for_complete()
        await pilot.pause()

    assert calls["categories"] == {"clabe", "name"}
    assert calls["names"] == ["Jane Doe"]


async def test_crop_shows_error_on_ocr_second_pass_failure(text_pdf_factory, monkeypatch):
    # An OCR/tesseract failure in the second pass must surface as the red error
    # message (translated to PdfCropError), not an uncaught traceback.
    from pdf_crop.features.ocr_redact import service as ocr_service

    def boom(*a, **k):
        raise ValueError("tesseract failure")

    monkeypatch.setattr(ocr_service, "scan", boom)

    src = text_pdf_factory(["no ocr here, scan is faked"])
    app = PdfCropApp(src)
    async with app.run_test(size=(120, 60)) as pilot:
        screen = app.screen
        screen.query_one("#range_input").value = "1"
        screen.query_one("#ocr_chk").value = True
        screen.query_one("#cat_clabe_chk").value = True  # a category so OCR runs
        await pilot.pause()
        await pilot.click("#crop_btn")
        await app.workers.wait_for_complete()
        await pilot.pause()
        error = str(screen.query_one("#error_msg").content)
        assert "OCR" in error or "redaction failed" in error


async def test_scan_shows_error_on_qr_preview_failure(text_pdf_factory, monkeypatch):
    # A decode/imaging failure while scanning QR for the preview must surface as
    # the red error message, not crash the TUI.
    from pdf_crop.features.qr_redact import service as qr_service

    def boom(*a, **k):
        raise ValueError("pyzbar decode failure")

    monkeypatch.setattr(qr_service, "scan", boom)

    src = text_pdf_factory(["no real qr here, scan is faked"])
    app = PdfCropApp(src)
    async with app.run_test(size=(120, 60)) as pilot:
        screen = app.screen
        screen.query_one("#range_input").value = "1"
        screen.query_one("#redact_qr_chk").value = True
        await pilot.pause()
        await pilot.click("#scan_btn")
        await app.workers.wait_for_complete()
        await pilot.pause()
        error = str(screen.query_one("#error_msg").content)
        assert "QR" in error or "scan failed" in error


@zbar_skip.SKIP
async def test_crop_with_redact_qr_removes_qr_from_output(qr_pdf_factory):
    from PIL import Image
    from pyzbar.pyzbar import decode

    src = qr_pdf_factory(["CLABE002010077777777771"])
    app = PdfCropApp(src)
    async with app.run_test(size=(120, 60)) as pilot:
        screen = app.screen
        screen.query_one("#range_input").value = "1"
        screen.query_one("#redact_qr_chk").value = True
        await pilot.pause()
        await pilot.click("#crop_btn")
        await pilot.pause()

    out = next(p for p in src.parent.glob("*_cropped*.pdf"))
    doc = fitz.open(str(out))
    pix = doc[0].get_pixmap(dpi=200)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    assert decode(img) == []


async def test_account_checkbox_feeds_selected_categories(text_pdf_factory):
    # UTILS-19: ticking "Redact: Account numbers" puts "account" in the selected
    # category set that scan/crop pass through to the detectors.
    src = text_pdf_factory(["Cuenta: 0123456789"])
    app = PdfCropApp(src)
    async with app.run_test(size=(120, 60)) as pilot:
        screen = app.screen
        assert "account" not in screen._selected_categories()
        screen.query_one("#cat_account_chk").value = True
        await pilot.pause()
        assert "account" in screen._selected_categories()


async def test_address_checkbox_feeds_selected_categories(text_pdf_factory):
    # UTILS-20: ticking "Redact: Addresses" puts "address" in the selected
    # category set that scan/crop pass through to the detectors.
    src = text_pdf_factory(["Calle Reforma 123, C.P. 64000"])
    app = PdfCropApp(src)
    async with app.run_test(size=(120, 60)) as pilot:
        screen = app.screen
        assert "address" not in screen._selected_categories()
        screen.query_one("#cat_address_chk").value = True
        await pilot.pause()
        assert "address" in screen._selected_categories()


async def test_screen_has_three_labeled_sections(three_page_pdf):
    app = PdfCropApp(three_page_pdf)
    async with app.run_test(size=(120, 60)) as pilot:
        screen = app.screen
        # The three grouped sections are present and queryable by id.
        assert screen.query_one("#pages_section")
        assert screen.query_one("#redaction_section")
        assert screen.query_one("#output_section")


async def test_screen_has_preview_pane(three_page_pdf):
    app = PdfCropApp(three_page_pdf)
    async with app.run_test(size=(120, 60)) as pilot:
        from pdf_crop.features.crop.preview import PagePreview

        screen = app.screen
        preview = screen.query_one(PagePreview)
        assert preview.total == 3
        assert preview.current == 1


async def test_typing_range_updates_included_badge(three_page_pdf):
    from pdf_crop.features.crop.preview import PagePreview

    app = PdfCropApp(three_page_pdf)
    async with app.run_test(size=(120, 60)) as pilot:
        screen = app.screen
        preview = screen.query_one(PagePreview)
        # Page 1 is in "1-2"; the badge should read "included".
        screen.query_one("#range_input").value = "1-2"
        await pilot.pause()
        status = str(screen.query_one("#preview_status").content)
        assert "1/3" in status
        assert "included" in status
        # Page 1 is NOT in "3"; the badge should flip to "excluded".
        screen.query_one("#range_input").value = "3"
        await pilot.pause()
        status = str(screen.query_one("#preview_status").content)
        assert "excluded" in status


async def test_crop_shows_persistent_result_without_exiting(three_page_pdf):
    app = PdfCropApp(three_page_pdf)
    async with app.run_test(size=(120, 60)) as pilot:
        screen = app.screen
        screen.query_one("#range_input").value = "1"
        await pilot.pause()
        await pilot.click("#crop_btn")
        await app.workers.wait_for_complete()
        await pilot.pause()
        result = str(screen.query_one("#result_msg").content)
        assert "Wrote" in result
        # Crop no longer exits the app; it's still running and can crop again.
        assert app.is_running is True


async def test_z_key_toggles_preview_zoom(three_page_pdf):
    # The `z` binding delegates to the preview's zoom toggle (Fit <-> 100%) and
    # doesn't collide with another binding.
    from pdf_crop.features.crop.preview import FIT, NATIVE, PagePreview

    app = PdfCropApp(three_page_pdf)
    async with app.run_test(size=(120, 60)) as pilot:
        preview = app.screen.query_one(PagePreview)
        assert preview.mode == FIT
        await pilot.press("z")
        assert preview.mode == NATIVE
        await pilot.press("z")
        assert preview.mode == FIT


async def test_z_in_input_does_not_toggle_zoom(three_page_pdf):
    # While an Input is focused, `z` is a literal character, not the zoom toggle.
    from pdf_crop.features.crop.preview import FIT, PagePreview

    app = PdfCropApp(three_page_pdf)
    async with app.run_test(size=(120, 60)) as pilot:
        screen = app.screen
        preview = screen.query_one(PagePreview)
        screen.query_one("#names_input").focus()
        await pilot.pause()
        await pilot.press("z")
        assert preview.mode == FIT  # unchanged
        assert "z" in screen.query_one("#names_input").value


async def test_zoom_button_lives_in_action_bar_not_nav(three_page_pdf):
    # UTILS-16: the zoom toggle moved from the cramped preview nav row to the
    # bottom action bar (next to Crop/Cancel). Assert the new home and the move.
    from pdf_crop.features.crop.preview import PagePreview

    app = PdfCropApp(three_page_pdf)
    async with app.run_test(size=(120, 60)) as pilot:
        screen = app.screen
        preview = screen.query_one(PagePreview)
        # Found in the action buttons row, and no longer inside the preview nav.
        assert screen.query_one("#action_buttons #zoom_btn") is not None
        assert not preview.query("#preview_nav #zoom_btn")
        assert not preview.query("#zoom_btn")  # not anywhere inside the pane


async def test_zoom_button_toggles_preview_zoom(three_page_pdf):
    # The action-bar toggle button flips the mode and shows the mode you'd switch
    # to. The button now lives in the screen's action bar, not the preview pane.
    from pdf_crop.features.crop.preview import FIT, NATIVE, PagePreview

    app = PdfCropApp(three_page_pdf)
    async with app.run_test(size=(120, 60)) as pilot:
        screen = app.screen
        preview = screen.query_one(PagePreview)
        assert preview.mode == FIT
        assert str(screen.query_one("#zoom_btn").label) == "100%"
        await pilot.click("#zoom_btn")
        assert preview.mode == NATIVE
        assert str(screen.query_one("#zoom_btn").label) == "Fit"


async def test_z_key_updates_relocated_zoom_button_label(three_page_pdf):
    # The `z` key flips the mode and the relocated (action-bar) button's label
    # tracks it, so the screen-scoped watch_mode label sync is exercised.
    from pdf_crop.features.crop.preview import FIT, NATIVE, PagePreview

    app = PdfCropApp(three_page_pdf)
    async with app.run_test(size=(120, 60)) as pilot:
        screen = app.screen
        preview = screen.query_one(PagePreview)
        assert preview.mode == FIT
        assert str(screen.query_one("#zoom_btn").label) == "100%"
        await pilot.press("z")
        assert preview.mode == NATIVE
        assert str(screen.query_one("#zoom_btn").label) == "Fit"
        await pilot.press("z")
        assert preview.mode == FIT
        assert str(screen.query_one("#zoom_btn").label) == "100%"


async def test_all_buttons_are_compact_single_row(three_page_pdf):
    # UTILS-16: EVERY button on the screen is compacted to a single row of text
    # (height 1) instead of the default 3-row bordered box — one consistent style
    # across the action bar, the preview nav, and the left-pane controls.
    app = PdfCropApp(three_page_pdf)
    async with app.run_test(size=(120, 60)) as pilot:
        screen = app.screen
        for button_id in (
            "crop_btn",
            "cancel_btn",
            "zoom_btn",
            "prev_btn",
            "next_btn",
            "scan_btn",
            "list_metadata_btn",
        ):
            assert screen.query_one(f"#{button_id}").region.height == 1, button_id


async def test_typing_in_input_does_not_trigger_crop(three_page_pdf):
    # The single-letter `c` crop binding must not fire while an Input is focused.
    # With a *valid* range set, a broken gate would actually crop and write a file;
    # the char must instead just land in the focused (names) field, with no crop.
    app = PdfCropApp(three_page_pdf)
    async with app.run_test(size=(120, 60)) as pilot:
        screen = app.screen
        screen.query_one("#range_input").value = "1"
        screen.query_one("#names_input").focus()
        await pilot.pause()
        await pilot.press("c")
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert "c" in screen.query_one("#names_input").value
        assert "Wrote" not in str(screen.query_one("#result_msg").content)
        assert app.is_running is True
        assert not list(three_page_pdf.parent.glob("*_cropped*.pdf"))
