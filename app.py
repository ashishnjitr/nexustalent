from pathlib import Path
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(layout="wide")

# Read the HTML file generated from Gemini Canvas
html_content = Path("index.html").read_text(encoding="utf-8")

# Render inside Streamlit iframe
components.html(html_content, height=800, scrolling=True)
