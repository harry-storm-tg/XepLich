import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials
import pathlib
import base64
from zoneinfo import ZoneInfo

from pages.DK_Hoc import connect_gsheet_hoc

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")

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
def load_data(x, y):
    credentials = load_credentials()
    gc = gspread.authorize(credentials)
    sheet = gc.open(x).worksheet(y)
    data = sheet.get_all_values()
    header = data[0]
    values = data[1:]
    data_final = pd.DataFrame(values, columns=header)
    return data_final

def connect_gsheet_pk():
    credentials = load_credentials()
    gc = gspread.authorize(credentials)
    sheeto1 = st.secrets["sheet_name"]["output_1"]
    sheet = gc.open(sheeto1).worksheet("Trang tính2")
    return sheet

def send_to_gsheet(data_dict):
    """Gửi dữ liệu phẳng lên Google Sheets"""
    sheet = connect_gsheet_pk()
    current_row_count = len(sheet.get_all_values())
    flat_data = []
    timestamp = datetime.now(VN_TZ).strftime('%Y/%m/%d %H:%M:%S')
    for i, (day, info) in enumerate(data_dict.items()):
        new_stt = current_row_count + i
        flat_data.append([new_stt, timestamp, st.session_state.username, st.session_state.ma_nhan_su, info["Ngày"], info["Buổi"], info["Ghi chú"], info["Loại khám"]])
    if flat_data:
        sheet.append_rows(flat_data)
    return True

def ds_bs():
    data = load_data(st.secrets["sheet_name"]["output_1"], "Trang tính1")
    return data["HỌ VÀ TÊN BÁC SĨ"]

###################################################################################################################
st.set_page_config(layout="wide")
st.title("🏥 Hệ thống Đăng ký Lịch phòng khám")

col_week = st.columns(2)
with col_week[0]:
    monday_of_week = st.date_input("Chọn ngày bất kì trong tuần cần đăng ký", value=datetime.now().date(),format="DD/MM/YYYY", key="date_input_pk")
    if monday_of_week.weekday() != 0:
        monday_of_week = monday_of_week - timedelta(days=monday_of_week.weekday())
    saturday_of_week = monday_of_week + timedelta(days=5)
    st.info(f"Tuần đăng ký: Từ {monday_of_week.strftime('%d/%m/%Y')} đến {saturday_of_week.strftime('%d/%m/%Y')}")
st.write("### Bảng đăng ký lịch phòng khám (Tích chọn buổi đi khám)")
cols = st.columns(6)
days = ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7"]
loai_pk = st.secrets["PK"]["loai_pk"]
lich_pk = {}
chon_loai_pk = st.selectbox("Loại khám", loai_pk, key="loai_pk_select")
for i, day in enumerate(days):
    with cols[i]:
        st.write(f"**{day}**", "(", (monday_of_week + timedelta(days=i)).strftime('%d/%m/%Y'), ")")
        ngay_thang_nam = (monday_of_week + timedelta(days=i)).strftime('%d/%m/%Y')
       
        am = st.multiselect("Buổi sáng", ["7:00 - 9:00", "9:00 - 11:00"], key=f"{ngay_thang_nam}_am_pk")
        pm = st.checkbox("Buổi chiều", key=f"{ngay_thang_nam}_pm_pk")
        loai = st.selectbox("Loại khám", loai_pk, key=f"{ngay_thang_nam}_loai_pk")
        ghi_chu = st.text_input(f"Ghi chú", key=f"{ngay_thang_nam}_note_pk")
        if am and pm:
            buoi = "Cả ngày"
        elif am and not pm:
            buoi = "Buổi sáng"
        elif not am and pm:
            buoi = "Buổi chiều"
        else:
            buoi = "Không đi khám"
            continue
        lich_pk[day] = {"Ngày": ngay_thang_nam, "Buổi": buoi,  "Loại khám": loai, "Ghi chú": ghi_chu}
submit = st.button("Gửi đăng ký lịch phòng khám")
if submit:
    send_to_gsheet(lich_pk)
    st.success("Đã gửi đăng ký lịch phòng khám!")