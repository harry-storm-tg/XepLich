import streamlit as st
import pandas

st.write("Chào mừng bạn đến với ứng dụng xếp lịch trực của chúng tôi!")
st.write("Bạn tên là " + st.session_state["username"])
st.write("Bạn là bác sĩ " + st.session_state["specialist"])