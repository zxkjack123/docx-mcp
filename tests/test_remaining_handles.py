"""Handle routing regression tests for the remaining singleton tools."""

import json
from unittest.mock import Mock

import pytest

from docx_mcp import server

# Each batch appends only its own rows; future batches are never pre-registered.
CASES = [
    (
        "merge_cells",
        {
            "table_index": None,
            "start_row": None,
            "start_col": None,
            "end_row": None,
            "end_col": None,
        },
    ),
    ("set_header_row", {"table_index": None}),
    ("set_column_widths", {"table_index": None, "widths_cm": None}),
    ("csv_to_table", {"para_id": None, "csv_text": None}),
    ("table_to_csv", {"table_index": None}),
    ("delete_table", {"table_idx": None}),
    ("add_column_to_table", {"table_idx": None}),
    ("delete_column_from_table", {"table_idx": None, "col_idx": None}),
    ("set_cell_width", {"table_idx": None, "row_idx": None, "col_idx": None, "width_mm": None}),
    (
        "set_cell_vertical_alignment",
        {"table_idx": None, "row_idx": None, "col_idx": None, "alignment": None},
    ),
    ("set_row_height", {"table_idx": None, "row_idx": None, "height_mm": None}),
    ("set_table_alignment", {"table_idx": None, "alignment": None}),
    ("set_table_borders", {"table_idx": None}),
    ("set_cell_shading", {"table_idx": None, "row_idx": None, "col_idx": None, "fill_color": None}),
    ("set_table_style", {"table_idx": None, "style_name": None}),
    ("create_style", {"name": None, "style_type": None}),
    ("update_style", {"name": None}),
    ("delete_style", {"name": None}),
    ("get_style", {"name_or_id": None}),
    ("copy_style", {"source_name_or_id": None, "new_name": None}),
    ("apply_style_to_range", {"para_ids": None, "style_name_or_id": None}),
    ("delete_header", {}),
    ("delete_footer", {}),
    ("get_custom_properties", {}),
    ("set_custom_property", {"name": None, "value": None}),
    ("delete_custom_property", {"name": None}),
    (
        "insert_floating_image",
        {"para_id": None, "image_path": None, "width_cm": None, "height_cm": None},
    ),
    ("delete_image", {"rId": None}),
    ("set_image_size", {"rId": None, "width_cm": None, "height_cm": None}),
    ("set_image_alt_text", {"rId": None, "alt_text": None}),
    ("set_image_border", {"rId": None, "border_pt": None}),
    ("update_footnote", {"footnote_id": None, "text": None}),
    ("delete_footnote", {"footnote_id": None}),
    ("update_endnote", {"endnote_id": None, "text": None}),
    ("delete_endnote", {"endnote_id": None}),
    ("set_page_size", {"width_mm": None, "height_mm": None}),
    ("set_page_margins", {}),
    ("set_page_orientation", {"orientation": None}),
    ("get_sections", {}),
    ("set_section_columns", {"section_index": None, "num_columns": None}),
    ("delete_section_break", {"para_id": None}),
    ("set_different_first_page", {"section_index": None, "enabled": None}),
    ("set_odd_even_headers", {"enabled": None}),
    ("accept_change", {"change_id": None}),
    ("reject_change", {"change_id": None}),
    ("update_comment", {"comment_id": None, "text": None}),
    ("delete_comment", {"comment_id": None}),
    ("resolve_comment", {"comment_id": None}),
    ("list_comment_threads", {}),
    ("scrub_pii", {}),
    ("list_parts", {}),
    ("read_part", {"part_path": None}),
    ("write_part", {"part_path": None, "xml": None}),
    ("xpath_query", {"xpath": None}),
    ("list_bookmarks", {}),
    ("add_bookmark", {"para_id": None, "name": None}),
    ("remove_bookmark", {"name": None}),
    ("get_bookmarked_text", {"name": None}),
    ("list_hyperlinks", {}),
    ("add_hyperlink", {"para_id": None, "text": None, "url": None}),
]


@pytest.mark.parametrize("name,kwargs", CASES)
def test_remaining_handle_isolation(monkeypatch, name, kwargs):
    a, b = Mock(), Mock()
    getattr(b, name).return_value = {"selected": "B"}
    monkeypatch.setattr(server, "_docs", {"A": a, "B": b})
    monkeypatch.setattr(server, "_REQUIRE_HANDLE", True)
    result = getattr(server, name)(**kwargs, document_handle="B")
    assert json.loads(result) == {"selected": "B"}
    getattr(b, name).assert_called_once()
    assert not a.mock_calls
    with pytest.raises(RuntimeError, match="'C'"):
        getattr(server, name)(**kwargs, document_handle="C")


@pytest.mark.parametrize("name,kwargs", CASES)
def test_remaining_required_handle(monkeypatch, name, kwargs):
    monkeypatch.setattr(server, "_REQUIRE_HANDLE", True)
    with pytest.raises(RuntimeError, match="document_handle is required"):
        getattr(server, name)(**kwargs)


@pytest.mark.parametrize("name,kwargs", CASES)
def test_remaining_legacy_default(monkeypatch, name, kwargs):
    doc = Mock()
    getattr(doc, name).return_value = {"selected": "default"}
    monkeypatch.setattr(server, "_docs", {server._DEFAULT_HANDLE: doc})
    monkeypatch.setattr(server, "_REQUIRE_HANDLE", False)
    assert json.loads(getattr(server, name)(**kwargs)) == {"selected": "default"}
    assert json.loads(getattr(server, name)(**kwargs, document_handle="")) == {
        "selected": "default"
    }
