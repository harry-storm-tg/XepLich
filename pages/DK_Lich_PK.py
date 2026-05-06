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

def ds_bs_all():
    """Lấy tất cả nhân sự kèm thông tin phòng khám để dùng ở Tab 2"""
    data = load_data(st.secrets["sheet_name"]["input_2"], "Trang tính1")
    data['ID'] = data['ID'].str[:6]
    return data[['ID', 'TÊN', 'VỊ TRÍ']].drop_duplicates()

def get_bs_by_pk(loai_pk):
    """Trả về dict {TÊN: ID} cho phòng khám cụ thể"""
    records = ds_bs(loai_pk)
    return {r['TÊN']: r['ID'] for r in records}

# ======================== WEEK NUMBER LOGIC ========================
ANCHOR_DATE = date(2026, 4, 27)  # Tuần số 1

def get_week_number(monday: date) -> int:
    delta_weeks = (monday - ANCHOR_DATE).days // 7
    return (delta_weeks % 4) + 1

def get_monday(d: date) -> date:
    return d - timedelta(days=d.weekday())

def get_weeks_in_range(start_date: date, end_date: date):
    start_monday = get_monday(start_date)
    weeks = []
    current = start_monday
    while current <= end_date:
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

    ds_pk = list(st.secrets["PK"].values()) if "PK" in st.secrets else ["PK Tân Bình", "PK Ngọc Lan", "PK Quốc Ánh"]
    days_vn = ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7"]
    sessions = [("S", "☀️ Sáng"), ("C", "🌙 Chiều"), ("T", "🌃 Tối")]

    mau_monday = all_weeks[0]
    mau_week_num = get_week_number(mau_monday)
    mau_saturday = mau_monday + timedelta(days=5)

    st.info(f"**Tuần mẫu (Tuần {mau_week_num}):** Từ {mau_monday.strftime('%d/%m/%Y')} đến {mau_saturday.strftime('%d/%m/%Y')} — Nhập lịch tuần mẫu, hệ thống sẽ tự động sao chép sang các tuần còn lại.")

    # --- Tuần mẫu ---
    mau_data = {}
    for loai_pk in ds_pk:
        st.markdown(f"---\n#### 🏢 {loai_pk} — Tuần mẫu (Tuần {mau_week_num})")
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
                mau_data[loai_pk][i] = {}
                for sess_code, sess_label in sessions:
                    key = f"mau_{loai_pk}_{i}_{sess_code}"
                    selected = st.multiselect(
                        sess_label,
                        options=ds_bs_pk,
                        format_func=lambda x: x['TÊN'],
                        key=key
                    )
                    mau_data[loai_pk][i][sess_code] = selected

    # --- Các tuần còn lại: tự động copy từ mẫu, cho phép chỉnh ---
    if len(all_weeks) > 1:
        st.markdown("---")
        st.subheader("📋 Lịch các tuần tiếp theo — Đã sao chép từ tuần mẫu, có thể điều chỉnh")

        for week_monday in all_weeks[1:]:
            week_num = get_week_number(week_monday)
            week_saturday = week_monday + timedelta(days=5)
            with st.expander(
                f"Tuần {week_num}: {week_monday.strftime('%d/%m/%Y')} — {week_saturday.strftime('%d/%m/%Y')}",
                expanded=True
            ):
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
                            for sess_code, sess_label in sessions:
                                key = f"w_{week_monday}_{loai_pk}_{i}_{sess_code}"
                                default_val = mau_data[loai_pk][i][sess_code]
                                st.multiselect(
                                    sess_label,
                                    options=ds_bs_pk,
                                    format_func=lambda x: x['TÊN'],
                                    default=default_val,
                                    key=key
                                )

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

                    for sess_code, sess_label in sessions:
                        if is_mau:
                            bs_list = mau_data[loai_pk][i][sess_code]
                        else:
                            key = f"w_{week_monday}_{loai_pk}_{i}_{sess_code}"
                            bs_list = st.session_state.get(key, mau_data[loai_pk][i][sess_code])

                        for bs in bs_list:
                            data_to_sheets.append({
                                "Ngày": ngay_thang_nam,
                                "Thứ": day,
                                "Bác sĩ": bs['TÊN'],
                                "Mã nhân sự": bs['ID'],
                                "Buổi": sess_code,
                                "Loại": loai_pk,
                                "Tuần số": week_num,
                            })

        if data_to_sheets:
            try:
                send_to_gsheet(data_to_sheets)
                st.success(f"✅ Đã lưu {len(data_to_sheets)} bản ghi lịch phòng khám cho {len(all_weeks)} tuần!")
            except Exception as e:
                st.error(f"Lỗi khi lưu dữ liệu: {e}")
        else:
            st.warning("Chưa có bác sĩ nào được chọn!")

# ======================== TAB 2 ========================
with tab2:
    st.subheader("Thay đổi lịch phòng khám")

    # ---- FORM LỌC ----
    with st.form("filter_form"):
        st.markdown("#### 🔍 Bộ lọc dữ liệu")
        col_f = st.columns(2)
        with col_f[0]:
            f_tu_ngay = st.date_input("Từ ngày", value=datetime.now().date(), format="DD/MM/YYYY", key="f_tu_ngay")
        with col_f[1]:
            f_den_ngay = st.date_input("Đến ngày", value=datetime.now().date() + timedelta(days=27), format="DD/MM/YYYY", key="f_den_ngay")

        col_f2 = st.columns(3)
        with col_f2[0]:
            f_buoi = st.selectbox("Buổi (cột G)", ["Tất cả", "S", "C", "T"], key="f_buoi")
        with col_f2[1]:
            ds_pk_filter = list(st.secrets["PK"].values()) if "PK" in st.secrets else []
            f_pk = st.selectbox("Phòng khám (cột F)", ["Tất cả"] + ds_pk_filter, key="f_pk")
        with col_f2[2]:
            f_nv = st.text_input("Tên nhân viên (cột C)", value="", key="f_nv")

        submitted = st.form_submit_button("🔍 OK - Tìm kiếm")

    # ---- XỬ LÝ KẾT QUẢ LỌC ----
    def parse_date_str(d_str):
        for fmt in ('%d/%m/%Y', '%Y/%m/%d', '%Y-%m-%d'):
            try:
                return datetime.strptime(d_str, fmt).date()
            except Exception:
                continue
        return None

    if submitted:
        try:
            sheet = connect_gsheet_pk()
            raw = sheet.get_all_values()
            if len(raw) < 2:
                st.warning("Không có dữ liệu trong sheet.")
            else:
                cols_header = ["STT", "Timestamp", "Bác sĩ", "Mã nhân sự", "Ngày", "Loại", "Buổi", "Tuần số"]
                # Đảm bảo đủ cột
                n_cols = len(raw[0])
                df = pd.DataFrame(raw[1:], columns=cols_header[:n_cols])
                # Bổ sung cột thiếu nếu sheet chưa có cột H
                for col in cols_header:
                    if col not in df.columns:
                        df[col] = ""
                df["_row_index"] = list(range(2, len(df) + 2))
                df["_date_parsed"] = df["Ngày"].apply(parse_date_str)
                df = df[df["_date_parsed"].apply(lambda d: d is not None and f_tu_ngay <= d <= f_den_ngay)]

                if f_buoi != "Tất cả":
                    df = df[df["Buổi"] == f_buoi]
                if f_pk != "Tất cả":
                    df = df[df["Loại"] == f_pk]
                if f_nv.strip():
                    df = df[df["Bác sĩ"].str.contains(f_nv.strip(), case=False, na=False)]

                if df.empty:
                    st.info("Không tìm thấy dữ liệu phù hợp với bộ lọc.")
                    st.session_state.pop("filtered_df", None)
                else:
                    st.session_state["filtered_df"] = df.reset_index(drop=True)
                    st.session_state["filter_params"] = {
                        "tu_ngay": f_tu_ngay,
                        "den_ngay": f_den_ngay,
                        "buoi": f_buoi,
                        "pk": f_pk,
                        "nv": f_nv,
                    }
        except Exception as e:
            st.error(f"Lỗi khi tải dữ liệu: {e}")

    # ---- HIỂN THỊ KẾT QUẢ ----
    if "filtered_df" in st.session_state and not st.session_state["filtered_df"].empty:
        df_edit_source = st.session_state["filtered_df"]
        filter_params = st.session_state.get("filter_params", {})

        # ===== BẢNG MA TRẬN XEM THÔNG TIN =====
        st.markdown("---")
        st.markdown("#### 📊 Bảng xem lịch theo tuần")

        # Chuẩn bị dữ liệu ma trận
        days_order = ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7"]
        day_map = {0: "Thứ 2", 1: "Thứ 3", 2: "Thứ 4", 3: "Thứ 5", 4: "Thứ 6", 5: "Thứ 6"}
        sessions_order = ["S", "C", "T"]
        sessions_label = {"S": "Sáng", "C": "Chiều", "T": "Tối"}

        df_view = df_edit_source.copy()
        df_view["_date_obj"] = df_view["Ngày"].apply(parse_date_str)
        df_view = df_view.dropna(subset=["_date_obj"])
        df_view["_monday"] = df_view["_date_obj"].apply(get_monday)
        df_view["_week_num"] = df_view["_monday"].apply(get_week_number)
        df_view["_dow"] = df_view["_date_obj"].apply(lambda d: d.weekday())  # 0=Mon..5=Sat

        # Map weekday number to tên thứ
        dow_to_thu = {0: "Thứ 2", 1: "Thứ 3", 2: "Thứ 4", 3: "Thứ 5", 4: "Thứ 6", 5: "Thứ 7"}
        df_view["_thu"] = df_view["_dow"].map(dow_to_thu)

        # Nhóm theo tuần, thứ, buổi -> danh sách bác sĩ
        grouped = (
            df_view.groupby(["_monday", "_week_num", "_thu", "Buổi"])["Bác sĩ"]
            .apply(lambda x: ", ".join(sorted(set(x))))
            .reset_index()
        )

        all_mondays = sorted(grouped["_monday"].unique())

        for monday in all_mondays:
            week_num = get_week_number(monday)
            saturday = monday + timedelta(days=5)
            st.markdown(f"**Tuần {week_num}** &nbsp;|&nbsp; {monday.strftime('%d/%m/%Y')} — {saturday.strftime('%d/%m/%Y')}")

            week_data = grouped[grouped["_monday"] == monday]

            # Xây dựng HTML bảng matrix
            # Header row 1: Tuần / Thứ (merged 3 cột mỗi thứ)
            # Header row 2: Buổi S, C, T cho mỗi thứ
            # Data rows: tên bác sĩ

            th_style = "border:1px solid #ccc; padding:6px 10px; text-align:center; background:#1f77b4; color:white; font-weight:bold;"
            th_buoi_style = "border:1px solid #ccc; padding:4px 8px; text-align:center; background:#4a9edd; color:white; font-size:0.85em;"
            td_style = "border:1px solid #ccc; padding:5px 8px; text-align:center; font-size:0.85em; min-width:80px; vertical-align:top;"
            td_empty_style = "border:1px solid #ccc; padding:5px 8px; text-align:center; font-size:0.85em; color:#bbb; min-width:80px;"
            th_week_style = "border:1px solid #ccc; padding:6px 10px; text-align:center; background:#155a8a; color:white; font-weight:bold;"

            html = '<table style="border-collapse:collapse; width:100%; table-layout:fixed;">'

            # Header row 1: label cột đầu + các Thứ (mỗi thứ span 3 cột)
            html += "<thead><tr>"
            html += f'<th style="{th_week_style}" rowspan="2">Phòng khám</th>'
            for thu in days_order:
                html += f'<th colspan="3" style="{th_style}">{thu}</th>'
            html += "</tr>"

            # Header row 2: Buổi S/C/T cho mỗi thứ
            html += "<tr>"
            for thu in days_order:
                for s in sessions_order:
                    html += f'<th style="{th_buoi_style}">{sessions_label[s]}</th>'
            html += "</tr></thead>"

            # Data rows: mỗi phòng khám 1 dòng
            html += "<tbody>"

            # Lấy danh sách phòng khám có trong tuần này
            pks_in_week = sorted(df_view[df_view["_monday"] == monday]["Loại"].unique())
            all_pks_display = list(st.secrets["PK"].values()) if "PK" in st.secrets else pks_in_week

            for pk_name in all_pks_display:
                html += "<tr>"
                html += f'<td style="border:1px solid #ccc; padding:5px 8px; font-weight:bold; background:#f0f4f8; white-space:nowrap;">{pk_name}</td>'
                for thu in days_order:
                    for s in sessions_order:
                        match = week_data[
                            (week_data["_thu"] == thu) &
                            (week_data["Buổi"] == s)
                        ]
                        # Lọc thêm theo phòng khám từ df_view gốc
                        pk_thu_session = df_view[
                            (df_view["_monday"] == monday) &
                            (df_view["_thu"] == thu) &
                            (df_view["Buổi"] == s) &
                            (df_view["Loại"] == pk_name)
                        ]["Bác sĩ"].dropna().unique()

                        if len(pk_thu_session) > 0:
                            names = "<br>".join(sorted(pk_thu_session))
                            html += f'<td style="{td_style}">{names}</td>'
                        else:
                            html += f'<td style="{td_empty_style}">—</td>'
                html += "</tr>"

            html += "</tbody></table>"
            st.markdown(html, unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)

        # ===== BẢNG CHỈNH SỬA =====
        st.markdown("---")
        st.markdown("#### ✏️ Bảng chỉnh sửa dữ liệu")
        st.caption("Chỉnh sửa trực tiếp, sau đó bấm 'Lưu thay đổi'")

        display_cols = ["STT", "Bác sĩ", "Mã nhân sự", "Ngày", "Loại", "Buổi", "Tuần số"]
        display_cols_exist = [c for c in display_cols if c in df_edit_source.columns]

        # Xây dựng column_config cho Bác sĩ theo phòng khám
        # Lấy nhân sự cho phòng khám đang lọc (nếu có chọn cụ thể)
        try:
            selected_pk_for_edit = filter_params.get("pk", "Tất cả")
            if selected_pk_for_edit != "Tất cả":
                bs_options_edit = [r['TÊN'] for r in ds_bs(selected_pk_for_edit)]
            else:
                # Gộp tất cả nhân sự của tất cả phòng khám
                all_bs_edit = []
                for pk_item in (list(st.secrets["PK"].values()) if "PK" in st.secrets else []):
                    try:
                        all_bs_edit.extend([r['TÊN'] for r in ds_bs(pk_item)])
                    except Exception:
                        pass
                bs_options_edit = sorted(list(set(all_bs_edit)))
        except Exception:
            bs_options_edit = []

        col_config = {}
        if bs_options_edit:
            col_config["Bác sĩ"] = st.column_config.SelectboxColumn(
                "Bác sĩ",
                options=bs_options_edit,
                required=True
            )
        col_config["Buổi"] = st.column_config.SelectboxColumn(
            "Buổi",
            options=["S", "C", "T"],
            required=True
        )
        col_config["Loại"] = st.column_config.SelectboxColumn(
            "Phòng khám",
            options=list(st.secrets["PK"].values()) if "PK" in st.secrets else [],
        )
        col_config["Mã nhân sự"] = st.column_config.TextColumn(
            "Mã nhân sự",
            disabled=True  # Chỉ đọc, tự động cập nhật khi lưu
        )

        edited_df = st.data_editor(
            df_edit_source[display_cols_exist].copy(),
            use_container_width=True,
            num_rows="fixed",
            column_config=col_config,
            key="edit_table"
        )

        st.caption("💡 Cột **Mã nhân sự** sẽ tự động cập nhật theo Bác sĩ được chọn khi bấm Lưu.")

        if st.button("💾 Lưu thay đổi", type="primary"):
            try:
                # Xây dựng bảng tra cứu TÊN -> ID từ tất cả phòng khám
                ten_to_id = {}
                for pk_item in (list(st.secrets["PK"].values()) if "PK" in st.secrets else []):
                    try:
                        for r in ds_bs(pk_item):
                            ten_to_id[r['TÊN']] = r['ID']
                    except Exception:
                        pass

                sheet = connect_gsheet_pk()
                errors = []
                for idx, row in edited_df.iterrows():
                    sheet_row = int(df_edit_source.loc[idx, "_row_index"])
                    try:
                        ten_bs = row.get("Bác sĩ", "")
                        ma_ns = ten_to_id.get(ten_bs, df_edit_source.loc[idx, "Mã nhân sự"])

                        sheet.update_cell(sheet_row, 3, ten_bs)
                        sheet.update_cell(sheet_row, 4, ma_ns)
                        sheet.update_cell(sheet_row, 5, row.get("Ngày", ""))
                        sheet.update_cell(sheet_row, 6, row.get("Loại", ""))
                        sheet.update_cell(sheet_row, 7, row.get("Buổi", ""))
                        sheet.update_cell(sheet_row, 8, str(row.get("Tuần số", "")))
                    except Exception as e:
                        errors.append(f"Dòng {sheet_row}: {e}")

                if errors:
                    st.warning("Lưu xong nhưng có lỗi:\n" + "\n".join(errors))
                else:
                    st.success("✅ Đã lưu thay đổi thành công!")
                st.session_state.pop("filtered_df", None)
            except Exception as e:
                st.error(f"Lỗi khi cập nhật: {e}")