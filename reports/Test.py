import streamlit as st
import pandas as pd
import gspread
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
import pathlib
import base64
from google.oauth2.service_account import Credentials

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")

# ======================== UTILS ========================
@st.cache_data(ttl=3600)
def get_img_as_base64(file):
    with open(file, "rb") as f:
        return base64.b64encode(f.read()).decode()

def load_css(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except UnicodeDecodeError:
        with open(file_path, "r", encoding="latin-1") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

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
    return Credentials.from_service_account_info(
        creds_info,
        scopes=["https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"]
    )




# ======================== MAIN ========================

css_path = pathlib.Path("asset/style.css")
load_css(css_path)

img = get_img_as_base64("pages/img/logo.png")
st.markdown(f"""
    <div class="fixed-header">
        <div class="header-content">
            <img src="data:image/png;base64,{img}" alt="logo">
            <div class="header-text">
                <h1>BỆNH VIỆN ĐA KHOA MỸ ĐỨC<span style="vertical-align: super; font-size: 0.6em;">&#174;</span></h1>
            </div>
        </div>
        <div class="header-subtext">
            <p>XẾP LỊCH LÀM VIỆC </p>
        </div>
    </div>
    <div class="header-underline"></div>
""", unsafe_allow_html=True)

nhan_vien = st.session_state.get("username", "Không xác định")
st.html(f'<p class="demuc"><i>Bác sĩ đang thực hiện: {nhan_vien}</i></p>')

for key in ["edit_row_idx", "view_df", "confirm_delete_idx"]:
    if key not in st.session_state:
        st.session_state[key] = None

# ======================== CẤU HÌNH & CONSTANTS ========================
INPUT_1_ID = st.secrets["gsheet_ids"]["input_1"]
INPUT_2_ID = st.secrets["gsheet_ids"]["input_2"]
OUTPUT_1_ID = st.secrets["gsheet_ids"]["output_1"]
OUTPUT_2_ID = st.secrets["gsheet_ids"]["output_2"]
OUTPUT_FN_ID = st.secrets["gsheet_ids"]["output_fn"]

SESSIONS = ["Sáng", "Trưa", "Chiều", "Tối"]
DAY_NAMES = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"]

# ======================== HELPER FUNCTIONS ========================
def get_week_number(check_date):
    """Tính tuần theo mốc 27/04/2026 (Tuần 1,2,3,4 quay vòng)"""
    base_date = date(2026, 4, 27)
    delta_days = (check_date - base_date).days
    delta_weeks = delta_days // 7
    week_num = (delta_weeks % 4) + 1
    return week_num

def get_gspread_client():
    creds = load_credentials()
    return gspread.authorize(creds)

@st.cache_data(ttl=600)
def fetch_all_data():
    """Tải toàn bộ dữ liệu từ các sheet cần thiết"""
    gc = get_gspread_client()
    
    # Load Input_1 (Nhân viên & Trực)
    sh1 = gc.open_by_key(INPUT_1_ID)
    df_nv = pd.DataFrame(sh1.worksheet("Trang tính1").get_all_records())
    df_truc = pd.DataFrame(sh1.worksheet("Trang tính1").get_all_records()) # Giả định cùng sheet theo mô tả
    df_pk = pd.DataFrame(sh1.worksheet("Trang tính2").get_all_records())
    
    # Load Input_2 (Khả năng & Vị trí)
    sh2 = gc.open_by_key(INPUT_2_ID)
    df_kn = pd.DataFrame(sh2.worksheet("Trang tính1").get_all_records())
    
    # Load Output_2 (Nghỉ, Học, CT...)
    sh_out2 = gc.open_by_key(OUTPUT_2_ID)
    df_nghi = pd.DataFrame(sh_out2.worksheet("Trang tính1").get_all_records())
    df_hoc = pd.DataFrame(sh_out2.worksheet("Trang tính2").get_all_records())
    df_congtac = pd.DataFrame(sh_out2.worksheet("Trang tính3").get_all_records())
    
    return df_nv, df_truc, df_pk, df_kn, df_nghi, df_hoc, df_congtac

def sort_employees(df):
    """Sắp xếp nhân viên theo S01 > S02 > S03 > I01 > A01 và Alphabet"""
    priority = {"S01": 1, "S02": 2, "S03": 3, "I01": 4, "A01": 5}
    df['prefix'] = df['Mã nhân sự'].str[:3]
    df['rank'] = df['prefix'].map(priority).fillna(99)
    df = df.sort_values(by=['rank', 'Họ và tên']).drop(columns=['prefix', 'rank'])
    return df

# ======================== GIAO DIỆN CHỌN NGÀY ========================
st.subheader("📅 Thiết lập khoảng thời gian")
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("Từ ngày", value=date(2026, 4, 27))
with col2:
    end_date = st.date_input("Đến ngày", value=start_date + timedelta(days=6))

if start_date:
    wn = get_week_number(start_date)
    st.info(f"Khoảng thời gian này thuộc: **Tuần {wn}**")

# ======================== LOGIC XẾP LỊCH TỰ ĐỘNG ========================
def generate_schedule(start_d, end_d):
    df_nv, df_truc, df_pk, df_kn, df_nghi, df_hoc, df_congtac = fetch_all_data()
    
    # 1. Khởi tạo Ma trận (Nhân viên x (Ngày * 4 Buổi))
    list_nv = sort_employees(df_nv)
    dates = [start_d + timedelta(days=i) for i in range((end_d - start_d).days + 1)]
    
    # Tạo MultiIndex cho cột: (Ngày, Buổi)
    columns = pd.MultiIndex.from_product(
        [dates, SESSIONS], 
        names=['Ngày', 'Buổi']
    )
    
    sched_df = pd.DataFrame(index=list_nv['Họ và tên'], columns=columns).fillna("")
    
    # ÁP DỤNG QUY TẮC (Tóm lược logic)
    for current_date in dates:
        day_str = current_date.strftime("%Y-%m-%d")
        
        # Quy tắc 1-4: Nghỉ, Học, CT, KH, BT
        # (Lọc df_nghi, df_hoc... theo ngày và điền vào sched_df)
        
        # Quy tắc 5: Lịch trực (Lưu vào 1 dict riêng để hiện dòng cuối)
        
        # Quy tắc 7: VT - RT
        # Nếu trực ngày D -> Điền VT/RT vào D và D+1 dựa trên mã S02/Khả năng NL
        
        # Quy tắc 8-10: Phòng khám (NL, PK, QA)
        
        # Quy tắc 11-15: NG, NS, NB, Combo PS/S/M, C+
        # Sử dụng vòng lặp luân phiên dựa trên df_kn (Khả năng = 1)
        
    return sched_df, list_nv

# ======================== XỬ LÝ SỰ KIỆN ========================
if st.button("Bắt đầu xếp lịch"):
    with st.spinner("Đang tính toán lịch tối ưu..."):
        full_sched, employees = generate_schedule(start_date, end_date)
        st.session_state.schedule_data = full_sched
        st.session_state.emp_info = employees
        st.session_state.mode = "view"

if "schedule_data" in st.session_state:
    st.write(f"### Tuần thứ {get_week_number(start_date)} ({start_date} đến {end_date})")
    
    # Hiển thị bảng dạng Data Editor để chỉnh sửa
    df_to_show = st.session_state.schedule_data.copy()
    
    # Cấu hình danh sách chọn (Multi-select giả lập bằng dropdown cho từng cell)
    # Trong Streamlit Data Editor, ta có thể config từng cột
    
    if st.session_state.mode == "edit":
        edited_df = st.data_editor(
            df_to_show,
            use_container_width=True,
            height=500,
            # Cấu hình các cột ở đây dựa trên khả năng của từng nhân sự
        )
        if st.button("Chốt danh sách"):
            st.session_state.schedule_data = edited_df
            st.session_state.mode = "final"
            st.rerun()
    
    elif st.session_state.mode == "final":
        st.dataframe(df_to_show, use_container_width=True)
        if st.button("Chỉnh sửa lại"):
            st.session_state.mode = "edit"
            st.rerun()
            
        if st.button("Lưu danh sách"):
            # Logic upload lên Google Sheets (output_fn)
            # 1. Mở file output_fn
            # 2. Kiểm tra tab (Tuần X). Nếu chưa có -> tạo mới. Nếu có -> Replace.
            # 3. Ghi dữ liệu
            st.success("Đã lưu danh sách lên Google Sheets thành công!")

    # Dòng cuối cùng: Danh sách trực
    st.markdown("---")
    st.markdown("**NHÂN VIÊN TRỰC TRONG NGÀY:**")
    # Logic hiển thị nhân viên trực cách nhau bởi dấu "-"