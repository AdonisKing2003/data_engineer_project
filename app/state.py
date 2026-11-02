"""Selection state shared across dashboard pages.

The chosen offering ("BBB 2014J") lives in ``st.session_state`` so that a lecturer
who picks an offering on one page sees the same offering on the next page.
Only an explicit user choice is shared; a page's own default never overwrites it.
"""

from __future__ import annotations

from typing import Any, Iterable

import streamlit as st


OFFERING_KEY = "selected_offering"


def offering_label(code_module: Any, code_presentation: Any) -> str:
    return f"{code_module} {code_presentation}"


def split_offering(label: str) -> tuple[str, str]:
    code_module, code_presentation = label.split(" ", 1)
    return code_module, code_presentation


def select_offering(
    labels: Iterable[str],
    *,
    key: str,
    default: str | None = None,
    label: str = "Đợt học",
    container: Any = None,
) -> str:
    """Selectbox over offering labels that starts from the offering chosen elsewhere."""
    labels = list(labels)
    current = st.session_state.get(OFFERING_KEY)
    if current not in labels:
        current = default if default in labels else labels[0]

    def remember() -> None:
        st.session_state[OFFERING_KEY] = st.session_state[key]

    return (container or st).selectbox(
        label, labels, index=labels.index(current), key=key, on_change=remember
    )
