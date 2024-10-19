import streamlit as st

tab1,tab2,tab3=st.tabs(["Main","Upload","Configure"])

with tab1:
    st.write("Main App")


with tab2:
    st.write("Upload App")


with tab3:
    st.write("Configure App")
