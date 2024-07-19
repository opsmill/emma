import os

import streamlit as st
from langchain_community.agents.openai_assistant import OpenAIAssistantV2Runnable

from emma.streamlit_utils import set_page_config
from menu import menu_with_redirect

set_page_config(title="Schema Builder")
st.markdown("# Schema Builder")
menu_with_redirect()

if not os.environ.get("OPENAI_API_KEY"):
    st.error("You must provide a valid OpenAI API Key to use this application : OPENAI_API_KEY")
else:
    agent = OpenAIAssistantV2Runnable(assistant_id="asst_qgYySlyquR4WcJp294IR5f2L", as_agent=True)

    if "openai_model" not in st.session_state:
        st.session_state.openai_model = "gpt-4o"

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("What is up?"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            input = {"content": prompt}

            if "thread_id" in st.session_state:
                input["thread_id"] = st.session_state.thread_id

            response = agent.invoke(input=input)

            if "thread_id" not in st.session_state:
                st.session_state.thread_id = response.return_values["thread_id"]

            st.write(response.return_values["output"])

        st.session_state.messages.append({"role": "assistant", "content": response.return_values["output"]})
