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
    for i, info in enumerate(data_dict):
        new_stt = current_row_count + i
        flat_data.append([new_stt, timestamp, info["Bác sĩ"], info["Mã nhân sự"], info["Ngày"], info["Loại"], info["Buổi"]])
    if flat_data:
        sheet.append_rows(flat_data)
    return True

def ds_bs(loai_pk):
    data = load_data(st.secrets["sheet_name"]["input_2"], "Trang tính1")
    data['ID'] = data['ID'].str[:6]
    if loai_pk == st.secrets["PK"]["pk1"]:
        PKTB = ["PK - S", "PK - C"]         
        data = data[(data['VỊ TRÍ'].isin(PKTB))&(data['KHẢ NĂNG'] == "1")]
    if loai_pk == st.secrets["PK"]["pk2"]:
        data = data[(data['VỊ TRÍ'] == "NL")&(data['KHẢ NĂNG'] == "1")]
    if loai_pk == st.secrets["PK"]["pk3"]:
        data = data[(data['VỊ TRÍ'] == "QA")&(data['KHẢ NĂNG'] == "1")]
    return data[['ID', 'TÊN']].drop_duplicates().to_dict('records')
###################################################################################################################
st.set_page_config(layout="wide")
st.title("🏥 Hệ thống Đăng ký Lịch phòng khám")
col_week = st.columns(2)
with col_week[0]:
    ds_pk = list(st.secrets["PK"].values())
    loai_pk = st.selectbox("Vị trí phòng khám", ds_pk, key="loai_pk_select")
    ds_bs_pk = ds_bs(loai_pk)
    monday_of_week = st.date_input("Chọn ngày bất kì trong tuần cần đăng ký", value=datetime.now().date(),format="DD/MM/YYYY", key="date_input_pk")
    if monday_of_week.weekday() != 0:
        monday_of_week = monday_of_week - timedelta(days=monday_of_week.weekday())
    saturday_of_week = monday_of_week + timedelta(days=5)
    st.info(f"Tuần đăng ký: Từ {monday_of_week.strftime('%d/%m/%Y')} đến {saturday_of_week.strftime('%d/%m/%Y')}")
st.write("### Bảng đăng ký lịch phòng khám (Tích chọn buổi đi khám)")
cols = st.columns(6)
days = ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7"]
data_to_sheets = [] 
for i, day in enumerate(days):
    with cols[i]:
        st.write(f"**{day}**", "(", (monday_of_week + timedelta(days=i)).strftime('%d/%m/%Y'), ")")
        ngay_thang_nam = (monday_of_week + timedelta(days=i)).strftime('%d/%m/%Y')
        ds_bs_sang = st.multiselect("Buổi sáng", options=ds_bs_pk, 
                        format_func=lambda x: x['TÊN'], key=f"{ngay_thang_nam}_bs_pk_s")
        ds_bs_chieu = st.multiselect("Buổi chiều", options=ds_bs_pk, 
                        format_func=lambda x: x['TÊN'], key=f"{ngay_thang_nam}_bs_pk_c")
        for bs in ds_bs_sang:
            data_to_sheets.append({
                "Ngày": ngay_thang_nam,
                "Thứ": day,
                "Bác sĩ": bs['TÊN'],
                "Mã nhân sự": bs['ID'],
                "Buổi": "Sáng",
                "Loại": loai_pk,
            })
        for bs in ds_bs_chieu:
            data_to_sheets.append({
                "Ngày": ngay_thang_nam,
                "Thứ": day,
                "Bác sĩ": bs['TÊN'],
                "Mã nhân sự": bs['ID'],
                "Buổi": "Chiều",
                "Loại": loai_pk,
            })
submit = st.button("Gửi đăng ký lịch phòng khám")
if submit:
    send_to_gsheet(data_to_sheets)
    st.success("Đã gửi đăng ký lịch phòng khám!")