import os

import streamlit as st
from langchain_community.agents.openai_assistant import OpenAIAssistantV2Runnable
from openai import OpenAI

# from emma.streamlit_utils import set_page_config
from menu import menu_with_redirect

# Set your OpenAI API key from env
api_key = "EmmaDefaultAuthMakingInfrahubEasierToUse!!!11"

client = OpenAI(base_url="https://emma.opsmill.cloud/v1", api_key=api_key)

agent = OpenAIAssistantV2Runnable(
    assistant_id=os.environ.get("OPENAI_ASSISTANT_ID", "asst_8cxNchGlFYnODkEWDpTQlHud"),
    as_agent=True,
    client=client,
    check_every_ms=1000,
)

# System prompt used across all requests
# SYSTEM_PROMPT = """You are a technical writer.
# Your job is to rewrite software documentation so that it is:
# - Clear and free of jargon
# - Concise (removing repetition and verbose phrases)
# - Accurate with regard to the underlying code
# - Written in a friendly, active, and helpful tone

# Rewrite the following content accordingly.
# """

# Streamlit app layout
st.set_page_config(page_title="AI Doc Refactor", layout="wide")
st.title("📘 AI Documentation Refactorer")
menu_with_redirect()

col1, col2 = st.columns(2)

with col1:
    st.subheader("✍️ Paste Your Documentation")
    user_input = st.text_area("Input", height=400, placeholder="Paste Markdown or doc text here...")

with col2:
    st.subheader("🪄 AI-Refactored Output")
    if user_input:
        with st.spinner("Refactoring..."):

            response = agent.invoke(
                input={"content": user_input},
            )

            output = response.return_values["output"]  # type: ignore[union-attr]
            st.text_area("Output", output, height=400)

st.markdown("---")
st.caption("Powered by OpenAI · Built with Streamlit")
