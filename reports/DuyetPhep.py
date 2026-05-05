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


def get_sheet():
    creds = load_credentials()
    client = gspread.authorize(creds)
    spreadsheet_name = st.secrets["sheet_name"]["output_2"]
    spreadsheet = client.open(spreadsheet_name)
    worksheet = spreadsheet.worksheet("Trang tính1")
    return worksheet


@st.cache_data(ttl=60)
def load_data():
    worksheet = get_sheet()
    data = worksheet.get_all_values()
    if len(data) <= 1:
        return pd.DataFrame()
    headers = data[0]
    rows = data[1:]
    df = pd.DataFrame(rows, columns=headers)
    # Rename columns by position to standardized names
    col_map = {
        df.columns[0]: "STT",
        df.columns[1]: "TIMESTAMP",
        df.columns[2]: "NHAN_VIEN",
        df.columns[3]: "LOAI_YEU_CAU",
        df.columns[4]: "NGAY",
        df.columns[5]: "BUOI",
        df.columns[6]: "LI_DO",
        df.columns[7]: "TINH_TRANG_DUYET",
    }
    df = df.rename(columns=col_map)
    # Parse dates
    df["NGAY"] = pd.to_datetime(df["NGAY"], format="%d/%m/%Y", errors="coerce")
    df["TIMESTAMP"] = pd.to_datetime(df["TIMESTAMP"], format="%d/%m/%Y %H:%M:%S", errors="coerce")
    df["STT"] = pd.to_numeric(df["STT"], errors="coerce")
    # Keep row index for mapping back to sheet (1-indexed header + 1 offset)
    df["_row_idx"] = range(2, len(df) + 2)
    return df


def update_tinh_trang(row_indices, value):
    """Update column H (TINH_TRANG_DUYET) for given sheet row indices."""
    try:
        creds = load_credentials()
        client = gspread.authorize(creds)
        spreadsheet_name = st.secrets["sheet_name"]["output_2"]
        spreadsheet = client.open(spreadsheet_name)
        worksheet = spreadsheet.worksheet("Trang tính1")
        
        for row_idx in row_indices:
            worksheet.update_cell(row_idx, 8, value)
        
        # Clear cache after update
        load_data.clear()
    except Exception as e:
        raise Exception(f"Lỗi cập nhật Google Sheet: {e}")


def thu_trong_tuan(d):
    thu_map = {0: "Thứ 2", 1: "Thứ 3", 2: "Thứ 4", 3: "Thứ 5",
               4: "Thứ 6", 5: "Thứ 7", 6: "Chủ nhật"}
    if pd.isna(d):
        return ""
    return thu_map[d.weekday()]


def buoi_sort_key(b):
    return 0 if b == "S" else 1


def format_buoi(b):
    return "Sáng" if b == "S" else "Chiều" if b == "C" else b


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
            <p>DUYỆT YÊU CẦU NGHỈ PHÉP</p>
        </div>
    </div>
    <div class="header-underline"></div>
""", unsafe_allow_html=True)

nhan_vien = st.session_state.get("username", "Không xác định")
st.html(f'<p class="demuc"><i>Bác sĩ đang thực hiện: {nhan_vien}</i></p>')

for key in ["edit_row_idx", "view_df", "confirm_delete_idx"]:
    if key not in st.session_state:
        st.session_state[key] = None

# Session states for tab functionality
if "tab1_submitted" not in st.session_state:
    st.session_state["tab1_submitted"] = False
if "tab1_from" not in st.session_state:
    st.session_state["tab1_from"] = date.today()
if "tab1_to" not in st.session_state:
    st.session_state["tab1_to"] = date.today() + timedelta(days=7)
if "tab2_submitted" not in st.session_state:
    st.session_state["tab2_submitted"] = False
if "tab2_from" not in st.session_state:
    st.session_state["tab2_from"] = date.today()
if "tab2_to" not in st.session_state:
    st.session_state["tab2_to"] = date.today() + timedelta(days=7)
if "tab2_loai" not in st.session_state:
    st.session_state["tab2_loai"] = "Tất cả"
# approval_changes: dict stt -> "Đã duyệt" | "Không duyệt" | ""
if "approval_changes" not in st.session_state:
    st.session_state["approval_changes"] = {}
# tab2_change_day: selected date for inline editing
if "tab2_change_day" not in st.session_state:
    st.session_state["tab2_change_day"] = None
if "tab2_approval_changes" not in st.session_state:
    st.session_state["tab2_approval_changes"] = {}

# ======================== TABS ========================
tab1, tab2 = st.tabs(["📋 Duyệt phép", "🔄 Thay đổi đột xuất"])

# ======================== TAB 1 ========================
with tab1:
    st.subheader("Chọn khoảng thời gian")
    with st.form("form_tab1"):
        col1, col2 = st.columns(2)
        with col1:
            t1_from = st.date_input("Từ ngày", value=st.session_state["tab1_from"], format = "DD/MM/YYYY", key="t1_from_input")
        with col2:
            t1_to = st.date_input("Đến ngày", value=st.session_state["tab1_to"], format = "DD/MM/YYYY", key="t1_to_input")
        submitted1 = st.form_submit_button("✅ OK")

    if submitted1:
        st.session_state["tab1_from"] = t1_from
        st.session_state["tab1_to"] = t1_to
        st.session_state["tab1_submitted"] = True
        st.session_state["approval_changes"] = {}

    if st.session_state["tab1_submitted"]:
        df_all = load_data()
        if df_all.empty:
            st.warning("Không có dữ liệu.")
        else:
            from_dt = pd.Timestamp(st.session_state["tab1_from"])
            to_dt = pd.Timestamp(st.session_state["tab1_to"])
            df_range = df_all[
                (df_all["NGAY"] >= from_dt) & (df_all["NGAY"] <= to_dt)
            ].copy()

            # ---- BẢNG THỐNG KÊ NGHỈ PHÉP ----
            with st.expander("📊 Bảng thống kê nghỉ phép", expanded=True):
                if df_range.empty:
                    st.info("Không có dữ liệu trong khoảng thời gian này.")
                else:
                    # Get unique (ngay, buoi) combos sorted
                    ngay_buoi_pairs = (
                        df_range[["NGAY", "BUOI"]]
                        .drop_duplicates()
                        .copy()
                    )
                    ngay_buoi_pairs["_buoi_sort"] = ngay_buoi_pairs["BUOI"].map(buoi_sort_key)
                    ngay_buoi_pairs = ngay_buoi_pairs.sort_values(["NGAY", "_buoi_sort"])

                    stats_rows = []
                    for _, pair in ngay_buoi_pairs.iterrows():
                        ngay = pair["NGAY"]
                        buoi = pair["BUOI"]
                        mask = (df_range["NGAY"] == ngay) & (df_range["BUOI"] == buoi)
                        sub = df_range[mask]

                        # Registered count
                        dk_new = (sub["LOAI_YEU_CAU"] == "Đăng ký phép mới").sum()
                        huy = (sub["LOAI_YEU_CAU"] == "Hủy phép đã đăng ký").sum()
                        so_phep_dk = dk_new - huy

                        # Approved count
                        dk_approved = (
                            (sub["LOAI_YEU_CAU"] == "Đăng ký phép mới") &
                            (sub["TINH_TRANG_DUYET"] == "Đã duyệt")
                        ).sum()
                        huy_approved = (
                            (sub["LOAI_YEU_CAU"] == "Hủy phép đã đăng ký") &
                            (sub["TINH_TRANG_DUYET"] == "Đã duyệt")
                        ).sum()
                        so_phep_duyet = dk_approved - huy_approved

                        # Rejected count
                        dk_rejected = (
                            (sub["LOAI_YEU_CAU"] == "Đăng ký phép mới") &
                            (sub["TINH_TRANG_DUYET"] == "Không duyệt")
                        ).sum()
                        huy_rejected = (
                            (sub["LOAI_YEU_CAU"] == "Hủy phép đã đăng ký") &
                            (sub["TINH_TRANG_DUYET"] == "Không duyệt")
                        ).sum()
                        so_phep_khong_duyet = dk_rejected - huy_rejected

                        # Names approved: registered new + approved, minus those with approved cancellation
                        approved_new_names = set(
                            sub[
                                (sub["LOAI_YEU_CAU"] == "Đăng ký phép mới") &
                                (sub["TINH_TRANG_DUYET"] == "Đã duyệt")
                            ]["NHAN_VIEN"].tolist()
                        )
                        cancelled_approved_names = set(
                            sub[
                                (sub["LOAI_YEU_CAU"] == "Hủy phép đã đăng ký") &
                                (sub["TINH_TRANG_DUYET"] == "Đã duyệt")
                            ]["NHAN_VIEN"].tolist()
                        )
                        net_approved_names = approved_new_names - cancelled_approved_names
                        ten_nv_duyet = ", ".join(sorted(net_approved_names)) if net_approved_names else ""

                        stats_rows.append({
                            "Thứ": thu_trong_tuan(ngay),
                            "Ngày": ngay.strftime("%d/%m/%Y") if not pd.isna(ngay) else "",
                            "Buổi": format_buoi(buoi),
                            "Số phép đã đăng ký": max(so_phep_dk, 0),
                            "Số phép đã được duyệt": max(so_phep_duyet, 0),
                            "Số phép không duyệt": max(so_phep_khong_duyet, 0),
                            "Nhân viên đã duyệt": ten_nv_duyet,
                            "_ngay_raw": ngay,
                        })

                    df_stats = pd.DataFrame(stats_rows)

                    # Render with merged date rows using HTML table
                    html = """
                    <style>
                    .stats-table { border-collapse: collapse; width: 100%; font-size: 13px; }
                    .stats-table th { background: #1a5276; color: white; padding: 8px 10px; text-align: center; border: 1px solid #ddd; }
                    .stats-table td { padding: 7px 10px; border: 1px solid #ddd; text-align: center; }
                    .stats-table tr:nth-child(even) { background: #f2f2f2; }
                    .stats-table td.name-col { text-align: left; }
                    .merged-date { font-weight: bold; vertical-align: middle; background: #d6eaf8; }
                    </style>
                    <table class="stats-table">
                    <thead>
                    <tr>
                        <th>Thứ</th><th>Ngày</th><th>Buổi</th>
                        <th>Số phép<br>đã đăng ký</th>
                        <th>Số phép<br>đã được duyệt</th>
                        <th>Số phép<br>không duyệt</th>
                        <th>Nhân viên đã duyệt</th>
                    </tr>
                    </thead><tbody>
                    """

                    # Group by date for merging
                    dates_grouped = {}
                    for row in stats_rows:
                        key = row["_ngay_raw"]
                        dates_grouped.setdefault(key, []).append(row)

                    for ngay_key, rows in sorted(dates_grouped.items()):
                        rowspan = len(rows)
                        for i, row in enumerate(rows):
                            html += "<tr>"
                            if i == 0:
                                html += f'<td class="merged-date" rowspan="{rowspan}">{row["Thứ"]}</td>'
                                html += f'<td class="merged-date" rowspan="{rowspan}">{row["Ngày"]}</td>'
                            html += f'<td>{row["Buổi"]}</td>'
                            html += f'<td>{row["Số phép đã đăng ký"]}</td>'
                            html += f'<td>{row["Số phép đã được duyệt"]}</td>'
                            html += f'<td>{row["Số phép không duyệt"]}</td>'
                            html += f'<td class="name-col">{row["Nhân viên đã duyệt"]}</td>'
                            html += "</tr>"

                    html += "</tbody></table>"
                    st.markdown(html, unsafe_allow_html=True)

            # ---- BẢNG DUYỆT PHÉP ----
            with st.expander("✅ Bảng duyệt phép", expanded=True):
                # Show only rows with empty TINH_TRANG_DUYET in date range
                df_duyet = df_range[
                    df_range["TINH_TRANG_DUYET"].str.strip() == ""
                ].copy()

                if df_duyet.empty:
                    st.info("Không có yêu cầu nào đang chờ duyệt trong khoảng thời gian này.")
                else:
                    # Group by STT (each package)
                    df_duyet_sorted = df_duyet.sort_values("TIMESTAMP", ascending=True)
                    packages = df_duyet_sorted.groupby("STT", sort=False)

                    # Create table data
                    table_data = []
                    for stt, grp in packages:
                        first = grp.iloc[0]
                        ts_str = first["TIMESTAMP"].strftime("%d/%m/%Y %H:%M:%S") if not pd.isna(first["TIMESTAMP"]) else ""
                        
                        # Build ngay + buoi list
                        ngay_buoi_list = []
                        for _, r in grp.iterrows():
                            ngay_str = r['NGAY'].strftime('%d/%m/%Y') if not pd.isna(r['NGAY']) else ''
                            buoi_str = format_buoi(r['BUOI'])
                            ngay_buoi_list.append(f"{ngay_str} ({buoi_str})")
                        
                        ngay_buoi_combined = "\n".join(ngay_buoi_list)
                        
                        table_data.append({
                            "STT": str(stt),
                            "Thời gian ĐK": ts_str,
                            "Nhân viên": first["NHAN_VIEN"],
                            "Loại yêu cầu": first["LOAI_YEU_CAU"],
                            "Ngày/Buổi": ngay_buoi_combined,
                            "Lí do": first["LI_DO"],
                        })

                    df_table = pd.DataFrame(table_data)
                    
                    # Render table with buttons
                    st.markdown("""
                    <style>
                    .duyet-container { display: flex; flex-direction: column; gap: 10px; }
                    .duyet-package { border: 1px solid #e0e0e0; padding: 12px; border-radius: 6px; background: #fafafa; }
                    .duyet-package:hover { background: #f0f0f0; }
                    .duyet-label { font-weight: 600; color: #1a5276; margin-bottom: 8px; font-size: 14px; }
                    .duyet-info { display: grid; grid-template-columns: 1fr 2fr 2fr 2fr 3fr; gap: 12px; margin-bottom: 10px; font-size: 13px; }
                    .duyet-info-item { padding: 6px; }
                    .duyet-info-label { font-weight: 600; color: #555; margin-bottom: 3px; }
                    .duyet-info-value { color: #333; }
                    .duyet-buttons { display: flex; gap: 8px; }
                    </style>
                    """, unsafe_allow_html=True)

                    for idx, row in df_table.iterrows():
                        stt_val = float(row["STT"])
                        current_status = st.session_state["approval_changes"].get(stt_val, "")
                        
                        st.markdown(f"""
                        <div class="duyet-package">
                            <div class="duyet-label">📌 Gói #{idx+1} (STT: {row['STT']})</div>
                            <div class="duyet-info">
                                <div class="duyet-info-item">
                                    <div class="duyet-info-label">Thời gian</div>
                                    <div class="duyet-info-value">{row['Thời gian ĐK']}</div>
                                </div>
                                <div class="duyet-info-item">
                                    <div class="duyet-info-label">Nhân viên</div>
                                    <div class="duyet-info-value">{row['Nhân viên']}</div>
                                </div>
                                <div class="duyet-info-item">
                                    <div class="duyet-info-label">Loại yêu cầu</div>
                                    <div class="duyet-info-value">{row['Loại yêu cầu']}</div>
                                </div>
                                <div class="duyet-info-item">
                                    <div class="duyet-info-label">Ngày/Buổi</div>
                                    <div class="duyet-info-value">{row['Ngày/Buổi'].replace(chr(10), '<br>')}</div>
                                </div>
                                <div class="duyet-info-item">
                                    <div class="duyet-info-label">Lí do</div>
                                    <div class="duyet-info-value">{row['Lí do']}</div>
                                </div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        col1, col2, col3 = st.columns([2, 1, 1])
                        
                        status_text = ""
                        if current_status == "Đã duyệt":
                            status_text = "✅ Đã chọn: Duyệt"
                        elif current_status == "Không duyệt":
                            status_text = "❌ Đã chọn: Không duyệt"
                        
                        with col1:
                            st.caption(status_text)
                        
                        with col2:
                            if col2.button("✔ Duyệt", key=f"btn_duyet_{stt_val}", use_container_width=True):
                                if st.session_state["approval_changes"].get(stt_val) == "Đã duyệt":
                                    st.session_state["approval_changes"].pop(stt_val, None)
                                else:
                                    st.session_state["approval_changes"][stt_val] = "Đã duyệt"
                                st.rerun()
                        
                        with col3:
                            if col3.button("✘ Không", key=f"btn_khong_{stt_val}", use_container_width=True):
                                if st.session_state["approval_changes"].get(stt_val) == "Không duyệt":
                                    st.session_state["approval_changes"].pop(stt_val, None)
                                else:
                                    st.session_state["approval_changes"][stt_val] = "Không duyệt"
                                st.rerun()

                    st.divider()

                    # Save button
                    pending = st.session_state["approval_changes"]
                    if pending:
                        st.info(f"Có {len(pending)} gói đã được chọn trạng thái duyệt.")

                    if st.button("💾 Lưu duyệt phép", type="primary", key="save_duyet"):
                        if not pending:
                            st.warning("Chưa có thay đổi nào để lưu.")
                        else:
                            with st.spinner("Đang lưu..."):
                                for stt_val, trang_thai in pending.items():
                                    row_indices = df_duyet[df_duyet["STT"] == stt_val]["_row_idx"].tolist()
                                    update_tinh_trang(row_indices, trang_thai)
                            st.session_state["approval_changes"] = {}
                            st.success("✅ Đã lưu duyệt phép thành công!")
                            st.rerun()


# ======================== TAB 2 ========================
with tab2:
    st.subheader("Chọn khoảng thời gian và loại yêu cầu")
    with st.form("form_tab2"):
        col1, col2, col3 = st.columns(3)
        with col1:
            t2_from = st.date_input("Từ ngày", value=st.session_state["tab2_from"], key="t2_from_input")
        with col2:
            t2_to = st.date_input("Đến ngày", value=st.session_state["tab2_to"], key="t2_to_input")
        with col3:
            t2_loai = st.selectbox(
                "Loại yêu cầu",
                ["Tất cả", "Đăng ký phép mới", "Hủy phép đã đăng ký"],
                index=["Tất cả", "Đăng ký phép mới", "Hủy phép đã đăng ký"].index(st.session_state["tab2_loai"]),
                key="t2_loai_input"
            )
        submitted2 = st.form_submit_button("✅ OK")

    if submitted2:
        st.session_state["tab2_from"] = t2_from
        st.session_state["tab2_to"] = t2_to
        st.session_state["tab2_loai"] = t2_loai
        st.session_state["tab2_submitted"] = True
        st.session_state["tab2_change_day"] = None
        st.session_state["tab2_approval_changes"] = {}

    if st.session_state["tab2_submitted"]:
        df_all = load_data()
        if df_all.empty:
            st.warning("Không có dữ liệu.")
        else:
            from_dt2 = pd.Timestamp(st.session_state["tab2_from"])
            to_dt2 = pd.Timestamp(st.session_state["tab2_to"])
            df_range2 = df_all[
                (df_all["NGAY"] >= from_dt2) & (df_all["NGAY"] <= to_dt2)
            ].copy()

            if st.session_state["tab2_loai"] != "Tất cả":
                df_range2 = df_range2[df_range2["LOAI_YEU_CAU"] == st.session_state["tab2_loai"]]

            if df_range2.empty:
                st.info("Không có dữ liệu trong khoảng thời gian này.")
            else:
                # Sort: newest first (by NGAY desc, then BUOI)
                df_range2["_buoi_sort"] = df_range2["BUOI"].map(buoi_sort_key)
                df_range2 = df_range2.sort_values(
                    ["NGAY", "_buoi_sort", "TIMESTAMP"], ascending=[False, True, False]
                )

                # Style for tinh trang
                def render_tinh_trang_badge(val):
                    val = val.strip() if val else ""
                    if val == "Đã duyệt":
                        return f'<span style="color: green; font-weight: bold;">✅ Đã duyệt</span>'
                    elif val == "Không duyệt":
                        return f'<span style="color: red; font-weight: bold;">❌ Không duyệt</span>'
                    else:
                        return f'<span style="color: gray;">⏳ Đợi duyệt</span>'

                # Group by date
                dates_in_range = df_range2["NGAY"].dt.date.unique()
                dates_sorted = sorted(dates_in_range, reverse=True)

                for ngay_date in dates_sorted:
                    ngay_ts = pd.Timestamp(ngay_date)
                    df_day = df_range2[df_range2["NGAY"] == ngay_ts].copy()
                    thu = thu_trong_tuan(ngay_ts)
                    ngay_str = ngay_ts.strftime("%d/%m/%Y")

                    with st.expander(f"📅 {thu}, {ngay_str}  —  {len(df_day)} yêu cầu", expanded=True):
                        # Table header
                        hdr = st.columns([0.8, 1, 0.6, 1.2, 1.5, 1.5, 1.2])
                        for col, h in zip(hdr, ["Thứ", "Ngày", "Buổi", "Loại yêu cầu", "Nhân viên", "Lí do", "Tình trạng duyệt"]):
                            col.markdown(f"**{h}**")
                        st.divider()

                        for _, row in df_day.iterrows():
                            r_cols = st.columns([0.8, 1, 0.6, 1.2, 1.5, 1.5, 1.2])
                            r_cols[0].write(thu_trong_tuan(row["NGAY"]))
                            r_cols[1].write(row["NGAY"].strftime("%d/%m/%Y") if not pd.isna(row["NGAY"]) else "")
                            r_cols[2].write(format_buoi(row["BUOI"]))
                            r_cols[3].write(row["LOAI_YEU_CAU"])
                            r_cols[4].write(row["NHAN_VIEN"])
                            r_cols[5].write(row["LI_DO"])
                            r_cols[6].markdown(render_tinh_trang_badge(row["TINH_TRANG_DUYET"]), unsafe_allow_html=True)

                        st.divider()

                        # Nút Thay đổi
                        if st.button(f"✏️ Thay đổi", key=f"btn_thayđoi_{ngay_date}"):
                            if st.session_state["tab2_change_day"] == ngay_date:
                                st.session_state["tab2_change_day"] = None
                            else:
                                st.session_state["tab2_change_day"] = ngay_date
                                st.session_state["tab2_approval_changes"] = {}
                            st.rerun()

                    # Inline editing panel
                    if st.session_state["tab2_change_day"] == ngay_date:
                        st.markdown(f"### ✏️ Thay đổi tình trạng duyệt — {thu}, {ngay_str}")
                        st.markdown("---")

                        # Group by (NHAN_VIEN, NGAY, BUOI) for display
                        df_day_edit = df_day.copy()

                        # Unique combinations of (nhan_vien, ngay, buoi) for display
                        combos = df_day_edit[["NHAN_VIEN", "NGAY", "BUOI", "LOAI_YEU_CAU", "LI_DO"]].drop_duplicates(
                            subset=["NHAN_VIEN", "NGAY", "BUOI"]
                        )

                        edit_hdr = st.columns([1.5, 1, 0.7, 1.5, 1.5, 2])
                        for col, h in zip(edit_hdr, ["Nhân viên", "Ngày", "Buổi", "Loại yêu cầu", "Lí do", "Thay đổi trạng thái"]):
                            col.markdown(f"**{h}**")
                        st.markdown("---")

                        for _, combo in combos.iterrows():
                            # Get all sheet rows for this combo
                            mask_combo = (
                                (df_day_edit["NHAN_VIEN"] == combo["NHAN_VIEN"]) &
                                (df_day_edit["NGAY"] == combo["NGAY"]) &
                                (df_day_edit["BUOI"] == combo["BUOI"])
                            )
                            combo_rows = df_day_edit[mask_combo]
                            row_indices = combo_rows["_row_idx"].tolist()
                            stts = combo_rows["STT"].tolist()
                            combo_key = f"{combo['NHAN_VIEN']}_{combo['NGAY'].strftime('%Y%m%d')}_{combo['BUOI']}"

                            edit_cols = st.columns([1.5, 1, 0.7, 1.5, 1.5, 2])
                            edit_cols[0].write(combo["NHAN_VIEN"])
                            edit_cols[1].write(combo["NGAY"].strftime("%d/%m/%Y") if not pd.isna(combo["NGAY"]) else "")
                            edit_cols[2].write(format_buoi(combo["BUOI"]))
                            edit_cols[3].write(combo["LOAI_YEU_CAU"])
                            edit_cols[4].write(combo["LI_DO"])

                            cur = st.session_state["tab2_approval_changes"].get(combo_key, "")
                            b1, b2 = edit_cols[5].columns(2)
                            t1 = "primary" if cur == "Đã duyệt" else "secondary"
                            t2 = "primary" if cur == "Không duyệt" else "secondary"

                            if b1.button("✔ Duyệt", key=f"edit_duyet_{combo_key}", type=t1, use_container_width=True):
                                if st.session_state["tab2_approval_changes"].get(combo_key) == "Đã duyệt":
                                    st.session_state["tab2_approval_changes"].pop(combo_key, None)
                                else:
                                    st.session_state["tab2_approval_changes"][combo_key] = "Đã duyệt"
                                    st.session_state["tab2_approval_changes"][combo_key + "_rows"] = row_indices
                                st.rerun()

                            if b2.button("✘ Không", key=f"edit_khong_{combo_key}", type=t2, use_container_width=True):
                                if st.session_state["tab2_approval_changes"].get(combo_key) == "Không duyệt":
                                    st.session_state["tab2_approval_changes"].pop(combo_key, None)
                                else:
                                    st.session_state["tab2_approval_changes"][combo_key] = "Không duyệt"
                                    st.session_state["tab2_approval_changes"][combo_key + "_rows"] = row_indices
                                st.rerun()

                        st.markdown("---")
                        if st.button("💾 Lưu thay đổi", type="primary", key=f"save_change_{ngay_date}"):
                            changes = st.session_state["tab2_approval_changes"]
                            if not any(v in ["Đã duyệt", "Không duyệt"] for v in changes.values()):
                                st.warning("Chưa có thay đổi nào để lưu.")
                            else:
                                with st.spinner("Đang lưu..."):
                                    for key_combo, val in changes.items():
                                        if val in ["Đã duyệt", "Không duyệt"]:
                                            rows_key = key_combo + "_rows"
                                            row_indices = changes.get(rows_key, [])
                                            if row_indices:
                                                update_tinh_trang(row_indices, val)
                                st.session_state["tab2_approval_changes"] = {}
                                st.session_state["tab2_change_day"] = None
                                st.success("✅ Đã lưu thay đổi thành công!")
                                st.rerun()