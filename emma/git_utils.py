"""Git related utils."""

from datetime import datetime, timedelta

import pytz
import streamlit as st
from git import Repo

SCHEMA_LIBRARY_REPO = "https://github.com/opsmill/schema-library.git"
SCHEMA_LIBRARY_REFRESH_INTERVAL = timedelta(hours=1)


@st.cache_resource
def get_repo() -> Repo:
    """Retrieve or return the git repository."""
    if st.session_state.repo["exists"]:
        return Repo(st.session_state.repo["local_path"])

    repo = Repo.clone_from(SCHEMA_LIBRARY_REPO, st.session_state.repo["local_path"], depth=1)
    st.session_state.repo["exists"] = True
    st.session_state.repo["last_pull"] = datetime.now(pytz.UTC)
    return repo
