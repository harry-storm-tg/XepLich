import streamlit as st
import pandas as pd
import base64
import gspread
from google.oauth2.service_account import Credentials
import pathlib

@st.cache_data(ttl=3600)
def load_credentials():
    creds_info = {
    "type": st.secrets["google_service_account"]["type"],
    "project_id": st.secrets["google_service_account"]["project_id"],
    "private_key_id": st.secrets["google_service_account"]["private_key_id"],
    "private_key": st.secrets["google_service_account"]["private_key"],
    "client_email": st.secrets["google_service_account"]["client_email"],
    "client_id": st.secrets["google_service_account"]["client_id"],
    "auth_uri": st.secrets["google_service_account"]["auth_uri"],
    "token_uri": st.secrets["google_service_account"]["token_uri"],
    "auth_provider_x509_cert_url": st.secrets["google_service_account"]["auth_provider_x509_cert_url"],
    "client_x509_cert_url": st.secrets["google_service_account"]["client_x509_cert_url"],
    "universe_domain": st.secrets["google_service_account"]["universe_domain"],
    }
    # Dùng để kết nối Google APIs
    credentials = Credentials.from_service_account_info(
        creds_info,
        scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    )
    return credentials

@st.cache_data(ttl=3600)
def load_data(x):
    credentials = load_credentials()
    gc = gspread.authorize(credentials)
    sheet = gc.open(x).sheet1
    data = sheet.get_all_values()
    header = data[0]
    values = data[1:]
    data_final = pd.DataFrame(values, columns=header)
    return data_final

def login():
    #Lấy dữ liệu nhân viên
    sheeti1 = st.secrets["sheet_name"]["input_1"]
    data = load_data(sheeti1)
    user = data["HỌ VÀ TÊN"]
    passw = data['MẬT KHẨU']
    author = data["PHÂN QUYỀN"]
    specialist = data["CHUYÊN KHOA"]
    #Form đăng nhập nhân viên
    with st.form("LoginForm"):
        name = st.text_input("",placeholder="Username",)
        code = st.text_input("",type="password",placeholder="Password",)
        submit_button = st.form_submit_button("Login")
    if submit_button:
        index = 0
        found = 0
        for i in user:
            index +=1
            if name == i and code == passw[int(index-1)]:
                author = author[int(index-1)]
                specialist = specialist[int(index-1)]
                found +=1
                st.session_state["username"] = name
                st.session_state["auth"] = author
                st.session_state["specialist"] = specialist
                st.session_state["ma_nhan_su"] = data["MÃ NHÂN SỰ"][int(index-1)]
                st.rerun()
        if found != 1:
            st.warning("Please recheck your username or password")

def logout():
    for key in st.session_state.keys():
        del st.session_state[key]
    st.rerun()
    
#########################################################################################    
login_page = st.Page(login, title="Sign in", icon=":material/login:")
logout_page = st.Page(logout, title="Sign out", icon=":material/logout:")

TK = st.Page("users/TaiKhoan.py", title="Tài khoản", icon="🔸", default=True)
LT = st.Page("pages/DK_LichTruc.py", title="Lịch trực", icon="🔸")
CT = st.Page("pages/DK_CongTac.py", title="Đăng ký công tác", icon="🔸")
VT = st.Page("pages/DS_ViTri.py", title="Danh sách vị trí", icon="🔸")
P = st.Page("pages/DK_Phep.py", title="Đăng ký phép", icon="🔸")
H = st.Page("pages/DK_Hoc.py", title="Đăng ký học", icon="🔸")
DP = st.Page("reports/DuyetPhep.py", title="Duyệt phép", icon="🔸")
LLV = st.Page("reports/LichLamViec.py", title="Xếp lịch làm việc", icon="🔸")
PK = st.Page("pages/DK_Lich_PK.py", title="Đăng ký phòng khám", icon="🔸")

if "username" in st.session_state:
    if st.session_state.auth == "1":
        pg = st.navigation(
            {
                "Thông tin tài khoản": [ logout_page, TK],
                "Chuyên mục": [ LT, CT, VT, P, H, PK ],
                "Duyệt": [ DP, LLV ],
            },
        expanded=False,
        )
else:
    pg = st.navigation([login_page])
pg.run()

