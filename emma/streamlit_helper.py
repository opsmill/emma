from typing import Tuple

import streamlit as st
from streamlit_theme import st_theme


def get_theme_settings() -> Tuple[str, str]:
    """
    Get theme settings for background and font color.

    Returns:
        Tuple[str, str]: Background color and font color.
    """
    theme = st_theme()
    if theme:
        return theme["backgroundColor"], theme["textColor"]
    return "#FFFFFF", "#000000"  # Default to light mode colors if not set

def display_expander(name: str, content: str) -> None:
    """
    Display an expander with the given name and content.

    Parameters:
        name (str): The title of the expander.
        content (str): The content to be displayed inside the expander.
    """
    with st.expander(name):
        st.markdown(content)
