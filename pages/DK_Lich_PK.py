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
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
    )

def get_gspread_client():
    creds = load_credentials()
    return gspread.authorize(creds)

def get_sheet(spreadsheet_name, worksheet_name):
    gc = get_gspread_client()
    sh = gc.open(spreadsheet_name)
    return sh.worksheet(worksheet_name)

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
    """Gửi dữ liệu lên Google Sheets với cột tuần (H)"""
    sheet = connect_gsheet_pk()
    current_row_count = len(sheet.get_all_values())
    flat_data = []
    timestamp = datetime.now(VN_TZ).strftime('%Y/%m/%d %H:%M:%S')
    for i, info in enumerate(data_dict):
        new_stt = current_row_count + i
        flat_data.append([
            new_stt,
            timestamp,
            info["Bác sĩ"],
            info["Mã nhân sự"],
            info["Ngày"],
            info["Loại"],
            info["Buổi"],
            info["Tuần số"]
        ])
    if flat_data:
        sheet.append_rows(flat_data)
    return True

def ds_bs(loai_pk):
    data = load_data(st.secrets["sheet_name"]["input_2"], "Trang tính1")
    data['ID'] = data['ID'].str[:6]
    if loai_pk == st.secrets["PK"]["pk1"]:
        PKTB = ["PK - S", "PK - C"]
        data = data[(data['VỊ TRÍ'].isin(PKTB)) & (data['KHẢ NĂNG'] == "1")]
    if loai_pk == st.secrets["PK"]["pk2"]:
        data = data[(data['VỊ TRÍ'] == "NL") & (data['KHẢ NĂNG'] == "1")]
    if loai_pk == st.secrets["PK"]["pk3"]:
        data = data[(data['VỊ TRÍ'] == "QA") & (data['KHẢ NĂNG'] == "1")]
    return data[['ID', 'TÊN']].drop_duplicates().to_dict('records')

# ======================== WEEK NUMBER LOGIC ========================
ANCHOR_DATE = date(2026, 4, 27)  # Tuần số 1

def get_week_number(monday: date) -> int:
    """Trả về số tuần (1-4) dựa trên ngày thứ 2 của tuần"""
    delta_weeks = (monday - ANCHOR_DATE).days // 7
    return (delta_weeks % 4) + 1

def get_monday(d: date) -> date:
    return d - timedelta(days=d.weekday())

def get_weeks_in_range(start_date: date, end_date: date):
    """Trả về danh sách các tuần (monday) trong khoảng thời gian"""
    start_monday = get_monday(start_date)
    weeks = []
    current = start_monday
    while current <= end_date:
        if current >= get_monday(start_date):
            weeks.append(current)
        current += timedelta(weeks=1)
    return weeks

# ======================== PAGE CONFIG ========================
st.set_page_config(layout="wide", page_title="Đăng ký lịch phòng khám")

# ======================== HEADER ========================
css_path = pathlib.Path("asset/style.css")
if css_path.exists():
    load_css(css_path)

logo_path = "pages/img/logo.png"
if pathlib.Path(logo_path).exists():
    img = get_img_as_base64(logo_path)
    st.markdown(f"""
        <div class="fixed-header">
            <div class="header-content">
                <img src="data:image/png;base64,{img}" alt="logo">
                <div class="header-text">
                    <h1>BỆNH VIỆN ĐA KHOA MỸ ĐỨC<span style="vertical-align: super; font-size: 0.6em;">&#174;</span></h1>
                </div>
            </div>
            <div class="header-subtext">
                <p>ĐĂNG KÝ LỊCH PHÒNG KHÁM</p>
            </div>
        </div>
        <div class="header-underline"></div>
    """, unsafe_allow_html=True)

nhan_vien = st.session_state.get("username", "Không xác định")
st.markdown(f'<p style="font-style:italic; color:#555;">Bác sĩ đang thực hiện: {nhan_vien}</p>', unsafe_allow_html=True)

st.title("🏥 Hệ thống Đăng ký Lịch phòng khám")

# ======================== TABS ========================
tab1, tab2 = st.tabs(["📅 Gán lịch phòng khám", "✏️ Thay đổi lịch phòng khám"])

# ======================== TAB 1 ========================
with tab1:
    st.subheader("Gán lịch phòng khám")

    col_range = st.columns(2)
    with col_range[0]:
        tu_ngay = st.date_input("Từ ngày", value=datetime.now().date(), format="DD/MM/YYYY", key="tab1_tu_ngay")
    with col_range[1]:
        den_ngay = st.date_input("Đến ngày", value=datetime.now().date() + timedelta(days=27), format="DD/MM/YYYY", key="tab1_den_ngay")

    if tu_ngay > den_ngay:
        st.error("Ngày bắt đầu phải nhỏ hơn hoặc bằng ngày kết thúc!")
        st.stop()

    all_weeks = get_weeks_in_range(tu_ngay, den_ngay)
    if not all_weeks:
        st.warning("Không có tuần nào trong khoảng thời gian đã chọn.")
        st.stop()

    # Lấy danh sách phòng khám
    ds_pk = list(st.secrets["PK"].values()) if "PK" in st.secrets else ["PK Tân Bình", "PK Ngọc Lan", "PK Quốc Ánh"]

    # Tuần mẫu: tuần đầu tiên trong khoảng
    mau_monday = all_weeks[0]
    mau_week_num = get_week_number(mau_monday)
    mau_saturday = mau_monday + timedelta(days=5)

    st.info(f"**Tuần mẫu (Tuần {mau_week_num}):** Từ {mau_monday.strftime('%d/%m/%Y')} đến {mau_saturday.strftime('%d/%m/%Y')} — Chọn lịch cho tuần này, hệ thống sẽ tự áp dụng cho các tuần còn lại.")

    days_vn = ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7"]

    # --- Giao diện chọn lịch mẫu theo từng phòng khám ---
    mau_data = {}  # mau_data[loai_pk][day_idx] = {"sang": [...], "chieu": [...]}

    for pk_idx, loai_pk in enumerate(ds_pk):
        st.markdown(f"---\n#### 🏢 {loai_pk}")
        try:
            ds_bs_pk = ds_bs(loai_pk)
        except Exception:
            ds_bs_pk = []

        mau_data[loai_pk] = {}
        cols = st.columns(6)
        for i, day in enumerate(days_vn):
            ngay_mau = (mau_monday + timedelta(days=i)).strftime('%d/%m/%Y')
            with cols[i]:
                st.write(f"**{day}**")
                st.caption(ngay_mau)
                sang_key = f"mau_{loai_pk}_{i}_sang"
                chieu_key = f"mau_{loai_pk}_{i}_chieu"
                bs_sang = st.multiselect("☀️ Sáng", options=ds_bs_pk,
                                         format_func=lambda x: x['TÊN'],
                                         key=sang_key)
                bs_chieu = st.multiselect("🌙 Chiều", options=ds_bs_pk,
                                          format_func=lambda x: x['TÊN'],
                                          key=chieu_key)
                mau_data[loai_pk][i] = {"sang": bs_sang, "chieu": bs_chieu}

    # --- Hiển thị & cho phép chỉnh sửa từng tuần còn lại ---
    if len(all_weeks) > 1:
        st.markdown("---")
        st.subheader("📋 Lịch các tuần — Có thể điều chỉnh từng tuần")

        for week_monday in all_weeks[1:]:
            week_num = get_week_number(week_monday)
            week_saturday = week_monday + timedelta(days=5)
            with st.expander(f"Tuần {week_num}: {week_monday.strftime('%d/%m/%Y')} — {week_saturday.strftime('%d/%m/%Y')}", expanded=False):
                for loai_pk in ds_pk:
                    st.markdown(f"**🏢 {loai_pk}**")
                    try:
                        ds_bs_pk = ds_bs(loai_pk)
                    except Exception:
                        ds_bs_pk = []
                    cols = st.columns(6)
                    for i, day in enumerate(days_vn):
                        ngay = (week_monday + timedelta(days=i)).strftime('%d/%m/%Y')
                        with cols[i]:
                            st.write(f"**{day}**")
                            st.caption(ngay)
                            sang_key = f"w_{week_monday}_{loai_pk}_{i}_sang"
                            chieu_key = f"w_{week_monday}_{loai_pk}_{i}_chieu"
                            # Mặc định copy từ tuần mẫu
                            default_sang = mau_data[loai_pk][i]["sang"]
                            default_chieu = mau_data[loai_pk][i]["chieu"]
                            # Dùng session_state để lưu default nếu chưa có
                            if sang_key not in st.session_state:
                                st.session_state[sang_key] = default_sang
                            if chieu_key not in st.session_state:
                                st.session_state[chieu_key] = default_chieu
                            st.multiselect("☀️ Sáng", options=ds_bs_pk,
                                           format_func=lambda x: x['TÊN'],
                                           default=default_sang,
                                           key=sang_key)
                            st.multiselect("🌙 Chiều", options=ds_bs_pk,
                                           format_func=lambda x: x['TÊN'],
                                           default=default_chieu,
                                           key=chieu_key)

    # --- Nút lưu ---
    st.markdown("---")
    if st.button("💾 Lưu lịch phòng khám", type="primary"):
        data_to_sheets = []

        for week_monday in all_weeks:
            week_num = get_week_number(week_monday)
            is_mau = (week_monday == mau_monday)

            for loai_pk in ds_pk:
                for i, day in enumerate(days_vn):
                    ngay_thang_nam = (week_monday + timedelta(days=i)).strftime('%d/%m/%Y')

                    if is_mau:
                        bs_sang = mau_data[loai_pk][i]["sang"]
                        bs_chieu = mau_data[loai_pk][i]["chieu"]
                    else:
                        sang_key = f"w_{week_monday}_{loai_pk}_{i}_sang"
                        chieu_key = f"w_{week_monday}_{loai_pk}_{i}_chieu"
                        bs_sang = st.session_state.get(sang_key, mau_data[loai_pk][i]["sang"])
                        bs_chieu = st.session_state.get(chieu_key, mau_data[loai_pk][i]["chieu"])

                    for bs in bs_sang:
                        data_to_sheets.append({
                            "Ngày": ngay_thang_nam,
                            "Thứ": day,
                            "Bác sĩ": bs['TÊN'],
                            "Mã nhân sự": bs['ID'],
                            "Buổi": "S",
                            "Loại": loai_pk,
                            "Tuần số": week_num,
                        })
                    for bs in bs_chieu:
                        data_to_sheets.append({
                            "Ngày": ngay_thang_nam,
                            "Thứ": day,
                            "Bác sĩ": bs['TÊN'],
                            "Mã nhân sự": bs['ID'],
                            "Buổi": "C",
                            "Loại": loai_pk,
                            "Tuần số": week_num,
                        })

        if data_to_sheets:
            try:
                send_to_gsheet(data_to_sheets)
                st.success(f"✅ Đã lưu {len(data_to_sheets)} bản ghi lịch phòng khám!")
            except Exception as e:
                st.error(f"Lỗi khi lưu dữ liệu: {e}")
        else:
            st.warning("Chưa có bác sĩ nào được chọn!")

# ======================== TAB 2 ========================
with tab2:
    st.subheader("Thay đổi lịch phòng khám")

    with st.form("filter_form"):
        st.markdown("#### 🔍 Bộ lọc dữ liệu")
        col_f = st.columns(2)
        with col_f[0]:
            f_tu_ngay = st.date_input("Từ ngày", value=datetime.now().date(), format="DD/MM/YYYY", key="f_tu_ngay")
        with col_f[1]:
            f_den_ngay = st.date_input("Đến ngày", value=datetime.now().date() + timedelta(days=7), format="DD/MM/YYYY", key="f_den_ngay")

        col_f2 = st.columns(3)
        with col_f2[0]:
            f_buoi = st.selectbox("Buổi (cột G)", ["Tất cả", "S", "C"], key="f_buoi")
        with col_f2[1]:
            ds_pk_filter = list(st.secrets["PK"].values()) if "PK" in st.secrets else []
            f_pk = st.selectbox("Phòng khám (cột F)", ["Tất cả"] + ds_pk_filter, key="f_pk")
        with col_f2[2]:
            f_nv = st.text_input("Tên nhân viên (cột C)", value="", key="f_nv")

        submitted = st.form_submit_button("🔍 OK - Tìm kiếm")

    if submitted:
        try:
            sheet = connect_gsheet_pk()
            raw = sheet.get_all_values()
            if len(raw) < 2:
                st.warning("Không có dữ liệu trong sheet.")
            else:
                # Cột: A=STT, B=Timestamp, C=Bác sĩ, D=Mã nhân sự, E=Ngày, F=Loại, G=Buổi, H=Tuần số
                cols_header = ["STT", "Timestamp", "Bác sĩ", "Mã nhân sự", "Ngày", "Loại", "Buổi", "Tuần số"]
                df = pd.DataFrame(raw[1:], columns=cols_header[:len(raw[0])])
                # Thêm cột gốc để track row index trên sheet (1-based, +2 vì header)
                df["_row_index"] = list(range(2, len(df) + 2))

                # Lọc theo ngày
                def parse_date(d_str):
                    for fmt in ('%d/%m/%Y', '%Y/%m/%d', '%Y-%m-%d'):
                        try:
                            return datetime.strptime(d_str, fmt).date()
                        except Exception:
                            continue
                    return None

                df["_date_parsed"] = df["Ngày"].apply(parse_date)
                df = df[df["_date_parsed"].apply(lambda d: d is not None and f_tu_ngay <= d <= f_den_ngay)]

                # Lọc buổi
                if f_buoi != "Tất cả":
                    df = df[df["Buổi"] == f_buoi]

                # Lọc phòng khám
                if f_pk != "Tất cả":
                    df = df[df["Loại"] == f_pk]

                # Lọc nhân viên
                if f_nv.strip():
                    df = df[df["Bác sĩ"].str.contains(f_nv.strip(), case=False, na=False)]

                if df.empty:
                    st.info("Không tìm thấy dữ liệu phù hợp với bộ lọc.")
                else:
                    st.success(f"Tìm thấy {len(df)} bản ghi. Bạn có thể chỉnh sửa bên dưới:")
                    st.session_state["filtered_df"] = df.reset_index(drop=True)
        except Exception as e:
            st.error(f"Lỗi khi tải dữ liệu: {e}")

    # Hiển thị bảng chỉnh sửa nếu có kết quả
    if "filtered_df" in st.session_state and not st.session_state["filtered_df"].empty:
        df_edit = st.session_state["filtered_df"]

        display_cols = ["STT", "Bác sĩ", "Mã nhân sự", "Ngày", "Loại", "Buổi", "Tuần số"]
        display_cols_exist = [c for c in display_cols if c in df_edit.columns]

        edited_df = st.data_editor(
            df_edit[display_cols_exist].copy(),
            use_container_width=True,
            num_rows="fixed",
            key="edit_table"
        )

        if st.button("💾 Lưu thay đổi", type="primary"):
            try:
                sheet = connect_gsheet_pk()
                errors = []
                for idx, row in edited_df.iterrows():
                    sheet_row = int(df_edit.loc[idx, "_row_index"])
                    # Cột: A=STT(1), B=Timestamp(2), C=Bác sĩ(3), D=Mã nhân sự(4),
                    #       E=Ngày(5), F=Loại(6), G=Buổi(7), H=Tuần số(8)
                    try:
                        if "Bác sĩ" in row:
                            sheet.update_cell(sheet_row, 3, row["Bác sĩ"])
                        if "Mã nhân sự" in row:
                            sheet.update_cell(sheet_row, 4, row["Mã nhân sự"])
                        if "Ngày" in row:
                            sheet.update_cell(sheet_row, 5, row["Ngày"])
                        if "Loại" in row:
                            sheet.update_cell(sheet_row, 6, row["Loại"])
                        if "Buổi" in row:
                            sheet.update_cell(sheet_row, 7, row["Buổi"])
                        if "Tuần số" in row:
                            sheet.update_cell(sheet_row, 8, str(row["Tuần số"]))
                    except Exception as e:
                        errors.append(f"Dòng {sheet_row}: {e}")

                if errors:
                    st.warning(f"Lưu xong nhưng có lỗi:\n" + "\n".join(errors))
                else:
                    st.success("✅ Đã lưu thay đổi thành công!")
                # Xóa cache để load lại
                del st.session_state["filtered_df"]
            except Exception as e:
                st.error(f"Lỗi khi cập nhật: {e}")