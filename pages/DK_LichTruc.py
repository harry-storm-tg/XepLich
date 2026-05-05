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

# ======================== DATA HELPERS ========================

@st.cache_data(ttl=300)
def load_input_nhan_su():
    """Load danh sách nhân sự từ input_1, Trang tính 1, cột E (HỌ VÀ TÊN) và cột D (MÃ NS)."""
    ws = get_sheet(st.secrets["sheet_name"]["input_1"], "Trang tính1")
    data = ws.get_all_values()
    if not data or len(data) < 2:
        return pd.DataFrame(columns=["HO_VA_TEN", "MA_NHAN_SU"])
    headers = data[0]
    rows = data[1:]
    df = pd.DataFrame(rows, columns=headers)
    # Cột E = index 4 (HỌ VÀ TÊN), Cột D = index 3 (MÃ NHÂN SỰ)
    col_ten = df.columns[4] if len(df.columns) > 4 else None
    col_ma = df.columns[0] if len(df.columns) > 0 else None
    result = pd.DataFrame()
    result["HO_VA_TEN"] = df[col_ten].str.strip() if col_ten else []
    result["MA_NHAN_SU"] = df[col_ma].str.strip() if col_ma else []
    result = result[result["HO_VA_TEN"] != ""]
    return result

@st.cache_data(ttl=300)
def load_output_data():
    """Load toàn bộ dữ liệu từ output_1, Trang tính 1."""
    ws = get_sheet(st.secrets["sheet_name"]["output_1"], "Trang tính1")
    data = ws.get_all_values()
    if not data or len(data) < 2:
        return pd.DataFrame(columns=["STT","TIMESTAMP","NHAN_VIEN","MA_NHAN_SU","NGAY_TRUC","THU","TUAN_THU"])
    headers = ["STT","TIMESTAMP","NHAN_VIEN","MA_NHAN_SU","NGAY_TRUC","THU","TUAN_THU"]
    rows = data[1:]
    df = pd.DataFrame(rows, columns=headers[:len(data[0])] if len(data[0]) <= 7 else headers)
    df = df[df["NHAN_VIEN"].str.strip() != ""]
    return df

def get_next_stt(ws):
    """Lấy STT tiếp theo trong sheet output."""
    data = ws.get_all_values()
    if len(data) <= 1:
        return 1
    last_stts = [row[0] for row in data[1:] if row[0].strip().isdigit()]
    return max([int(s) for s in last_stts], default=0) + 1 if last_stts else 1

# ======================== LOGIC TUẦN ========================

THU_MAP = {
    "Thứ 2": 0, "Thứ 3": 1, "Thứ 4": 2,
    "Thứ 5": 3, "Thứ 6": 4, "Thứ 7": 5, "CN": 6
}
THU_LABEL = {0:"2", 1:"3", 2:"4", 3:"5", 4:"6", 5:"7", 6:"CN"}

def get_dates_for_weekdays(start_date, end_date, weekdays_selected):
    """
    Trả về list (date, thu_label, tuan_so) cho các ngày thuộc weekday được chọn
    trong khoảng [start_date, end_date].
    Tuần được đánh số theo thứ tự xuất hiện trong khoảng thời gian.
    """
    results = []
    # Tìm tất cả ngày thỏa mãn
    current = start_date
    week_counter = {}  # weekday -> số tuần đã gặp
    # Đếm tuần theo từng thứ riêng biệt
    day_list = []
    d = start_date
    while d <= end_date:
        wd = d.weekday()  # 0=Mon ... 6=Sun
        label = THU_LABEL.get(wd, "")
        thu_name = "Thứ " + label if label != "CN" else "CN"
        if thu_name in weekdays_selected or label in weekdays_selected:
            day_list.append((d, wd, label))
        d += timedelta(days=1)
    # Gán số tuần (theo thứ tự xuất hiện cho mỗi thứ)
    week_count = {}
    for (d, wd, label) in day_list:
        if wd not in week_count:
            week_count[wd] = 0
        week_count[wd] += 1
        results.append((d, label if label != "CN" else "CN", week_count[wd]))
    return results

def thu_label_to_sheet(label):
    """Chuyển label thứ sang giá trị lưu sheet: số hoặc 'CN'."""
    return label  # đã là "2","3",...,"7","CN"

# ======================== HEADER ========================

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
            <p>GÁN LỊCH TRỰC</p>
        </div>
    </div>
    <div class="header-underline"></div>
""", unsafe_allow_html=True)

nhan_vien = st.session_state.get("username", "Không xác định")
st.html(f'<p class="demuc"><i>Bác sĩ đang thực hiện: {nhan_vien}</i></p>')

# ======================== SESSION STATE ========================

for key in ["edit_row_idx", "view_df", "confirm_delete_idx"]:
    if key not in st.session_state:
        st.session_state[key] = None

if "nhom_truc_list" not in st.session_state:
    # Mỗi phần tử: {"nhan_su": [], "thu_chon": [], "ngay_list": [(date, thu, tuan)], "ngay_bo": set()}
    st.session_state["nhom_truc_list"] = [{}]

if "swap_result" not in st.session_state:
    st.session_state["swap_result"] = None

if "tab2_df" not in st.session_state:
    st.session_state["tab2_df"] = None

if "selected_rows" not in st.session_state:
    st.session_state["selected_rows"] = []

# ======================== TABS ========================

tab1, tab2 = st.tabs(["📋 Gán lịch trực", "🔄 Đổi lịch trực"])

# ================================================================
# TAB 1: GÁN LỊCH TRỰC
# ================================================================
with tab1:
    st.subheader("Giới hạn thời gian gán lịch trực")
    col_from, col_to = st.columns(2)
    with col_from:
        from_date = st.date_input("Từ ngày", value=date.today(), format="DD/MM/YYYY", key="tab1_from")
    with col_to:
        to_date = st.date_input("Đến ngày", value=date.today() + timedelta(days=30), format="DD/MM/YYYY", key="tab1_to")

    if from_date > to_date:
        st.error("⚠️ Ngày bắt đầu phải nhỏ hơn hoặc bằng ngày kết thúc.")
        st.stop()

    # Load nhân sự
    df_ns = load_input_nhan_su()
    danh_sach_ten = df_ns["HO_VA_TEN"].tolist()
    ma_ns_map = dict(zip(df_ns["HO_VA_TEN"], df_ns["MA_NHAN_SU"]))

    thu_options = ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "CN"]

    st.markdown("---")
    st.subheader("Nhóm trực")

    # Render từng nhóm
    for i, nhom in enumerate(st.session_state["nhom_truc_list"]):
        with st.container():
            st.markdown(f"**Nhóm {i+1}**")
            col1, col2 = st.columns([2, 1])

            with col1:
                nhan_su_chon = st.multiselect(
                    "Nhân sự",
                    options=danh_sach_ten,
                    default=nhom.get("nhan_su", []),
                    key=f"nhan_su_{i}"
                )
            with col2:
                thu_chon = st.multiselect(
                    "Thứ trong tuần",
                    options=thu_options,
                    default=nhom.get("thu_chon", []),
                    key=f"thu_{i}"
                )

            # Tính danh sách ngày dựa trên thứ được chọn
            ngay_list = []
            if thu_chon:
                ngay_list = get_dates_for_weekdays(from_date, to_date, thu_chon)

            # Hiển thị ngày và cho phép chỉnh sửa (thêm/bỏ)
            if ngay_list:
                st.markdown("📅 **Các ngày trực trong khoảng thời gian:**")
                ngay_bo_key = f"ngay_bo_{i}"
                if ngay_bo_key not in st.session_state:
                    st.session_state[ngay_bo_key] = set()

                # Render checkbox từng ngày
                # Chia thành nhiều cột cho gọn
                n_cols = 4
                cols = st.columns(n_cols)
                ngay_giu = []
                for j, (d, thu_lb, tuan_so) in enumerate(ngay_list):
                    thu_display = f"Thứ {thu_lb}" if thu_lb != "CN" else "CN"
                    label = f"{d.strftime('%d/%m/%Y')} ({thu_display} - Tuần {tuan_so})"
                    checked = d.strftime("%Y-%m-%d") not in st.session_state[ngay_bo_key]
                    col_idx = j % n_cols
                    is_checked = cols[col_idx].checkbox(label, value=checked, key=f"ngay_{i}_{j}")
                    if is_checked:
                        ngay_giu.append((d, thu_lb, tuan_so))
                    else:
                        st.session_state[ngay_bo_key].add(d.strftime("%Y-%m-%d"))
                        if is_checked and d.strftime("%Y-%m-%d") in st.session_state[ngay_bo_key]:
                            st.session_state[ngay_bo_key].discard(d.strftime("%Y-%m-%d"))

                # Cập nhật lại nhóm
                st.session_state["nhom_truc_list"][i] = {
                    "nhan_su": nhan_su_chon,
                    "thu_chon": thu_chon,
                    "ngay_giu": ngay_giu,
                }
                st.caption(f"Tổng: {len(ngay_giu)} ngày được chọn cho {len(nhan_su_chon)} nhân viên → {len(ngay_giu)*len(nhan_su_chon)} dòng sẽ được tạo.")
            else:
                st.session_state["nhom_truc_list"][i] = {
                    "nhan_su": nhan_su_chon,
                    "thu_chon": thu_chon,
                    "ngay_giu": [],
                }

            if len(st.session_state["nhom_truc_list"]) > 1:
                if st.button(f"🗑️ Xóa nhóm {i+1}", key=f"xoa_nhom_{i}"):
                    st.session_state["nhom_truc_list"].pop(i)
                    st.rerun()
            st.markdown("---")

    # Nút thêm nhóm
    col_btn1, col_btn2 = st.columns([1, 3])
    with col_btn1:
        if st.button("➕ Thêm nhóm trực"):
            st.session_state["nhom_truc_list"].append({})
            st.rerun()

    with col_btn2:
        if st.button("💾 Lưu lịch trực", type="primary"):
            # Tổng hợp tất cả dòng cần upload
            all_rows = []
            for nhom in st.session_state["nhom_truc_list"]:
                nhan_su_list = nhom.get("nhan_su", [])
                ngay_giu = nhom.get("ngay_giu", [])
                for ten in nhan_su_list:
                    ma = ma_ns_map.get(ten, "")
                    for (d, thu_lb, tuan_so) in ngay_giu:
                        all_rows.append({
                            "NHAN_VIEN": ten,
                            "MA_NHAN_SU": ma,
                            "NGAY_TRUC": d.strftime("%d/%m/%Y"),
                            "THU": thu_lb,
                            "TUAN_THU": tuan_so,
                        })

            if not all_rows:
                st.warning("⚠️ Chưa có dữ liệu nào để lưu. Vui lòng chọn nhân sự và thứ trong tuần.")
            else:
                try:
                    ws_out = get_sheet(st.secrets["sheet_name"]["output_1"], "Trang tính1")
                    stt_start = get_next_stt(ws_out)
                    timestamp_now = datetime.now(VN_TZ).strftime("%d/%m/%Y %H:%M:%S")
                    upload_rows = []
                    for idx, row in enumerate(all_rows):
                        upload_rows.append([
                            stt_start + idx,
                            timestamp_now,
                            row["NHAN_VIEN"],
                            row["MA_NHAN_SU"],
                            row["NGAY_TRUC"],
                            row["THU"],
                            row["TUAN_THU"],
                        ])
                    ws_out.append_rows(upload_rows, value_input_option="USER_ENTERED")
                    # Xóa cache để load lại dữ liệu mới
                    load_output_data.clear()
                    st.success(f"✅ Đã lưu {len(upload_rows)} dòng lịch trực thành công!")
                    # Reset nhóm
                    st.session_state["nhom_truc_list"] = [{}]
                    for key in list(st.session_state.keys()):
                        if key.startswith("ngay_bo_"):
                            del st.session_state[key]
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Lỗi khi lưu dữ liệu: {e}")

# ================================================================
# TAB 2: ĐỔI LỊCH TRỰC
# ================================================================
with tab2:
    st.subheader("Xem và đổi lịch trực")

    with st.form("form_xem_lich"):
        col_a, col_b, col_c = st.columns([1, 1, 1])
        with col_a:
            xem_from = st.date_input("Từ ngày", value=date.today(), key="tab2_from")
        with col_b:
            xem_to = st.date_input("Đến ngày", value=date.today() + timedelta(days=30), key="tab2_to")
        with col_c:
            thu_filter = st.multiselect(
                "Thứ trong tuần",
                options=["2", "3", "4", "5", "6", "7", "CN"],
                key="tab2_thu"
            )
        chon_nhan_vien = st.multiselect("Chọn nhân viên (để dễ tìm kiếm)", options=[""] + danh_sach_ten, key="tab2_nhan_vien")
        submitted = st.form_submit_button("🔍 OK")

    if submitted:
        df_out = load_output_data()
        if df_out.empty:
            st.warning("Chưa có dữ liệu lịch trực.")
            st.session_state["tab2_df"] = None
        else:
            # Parse ngày
            def parse_date_safe(s):
                for fmt in ["%d/%m/%Y", "%Y-%m-%d", "%m/%d/%Y"]:
                    try:
                        return datetime.strptime(str(s).strip(), fmt).date()
                    except:
                        pass
                return None

            df_out["_date"] = df_out["NGAY_TRUC"].apply(parse_date_safe)
            mask = (df_out["_date"] >= xem_from) & (df_out["_date"] <= xem_to)
            df_filtered = df_out[mask].copy()

            if chon_nhan_vien:
                chon_nhan_vien = [nv for nv in chon_nhan_vien if nv.strip()]
                if chon_nhan_vien:
                    df_filtered = df_filtered[df_filtered["NHAN_VIEN"].isin(chon_nhan_vien)]

            if thu_filter:
                df_filtered = df_filtered[df_filtered["THU"].str.strip().isin(thu_filter)]

            df_filtered = df_filtered.reset_index(drop=True)
            st.session_state["tab2_df"] = df_filtered
            st.session_state["selected_rows"] = []
            st.session_state["swap_result"] = None

    # Hiển thị bảng kết quả với checkbox
    if st.session_state["tab2_df"] is not None:
        df_view = st.session_state["tab2_df"]

        if df_view.empty:
            st.info("Không có dữ liệu phù hợp với bộ lọc.")
        else:
            st.markdown(f"**Kết quả: {len(df_view)} dòng**")
            st.caption("Chọn đúng 2 nhân viên để đổi lịch trực.")

            # Render bảng với checkbox tự tạo
            selected = list(st.session_state["selected_rows"])

            header_cols = st.columns([0.5, 2, 2, 1, 1])
            header_cols[0].markdown("**✓**")
            header_cols[1].markdown("**Nhân viên**")
            header_cols[2].markdown("**Ngày trực**")
            header_cols[3].markdown("**Thứ**")
            header_cols[4].markdown("**Tuần thứ**")
            st.markdown("<hr style='margin:4px 0'>", unsafe_allow_html=True)

            for idx, row in df_view.iterrows():
                c0, c1, c2, c3, c4 = st.columns([0.5, 2, 2, 1, 1])
                is_checked = idx in selected
                chk = c0.checkbox("", value=is_checked, key=f"chk_row_{idx}", label_visibility="collapsed")
                c1.write(row["NHAN_VIEN"])
                c2.write(row["NGAY_TRUC"])
                c3.write(row["THU"])
                c4.write(row["TUAN_THU"])

                if chk and idx not in selected:
                    selected.append(idx)
                elif not chk and idx in selected:
                    selected.remove(idx)

            st.session_state["selected_rows"] = selected

            # Nút Đổi lịch trực
            st.markdown("---")
            if st.button("🔄 Đổi lịch trực", type="primary"):
                if len(selected) != 2:
                    st.error("⚠️ Vui lòng chọn đúng 2 nhân viên để đổi lịch.")
                else:
                    idx_a, idx_b = selected[0], selected[1]
                    row_a = df_view.loc[idx_a].copy()
                    row_b = df_view.loc[idx_b].copy()
                    # Lưu kết quả hoán đổi vào session
                    st.session_state["swap_result"] = {
                        "idx_a": idx_a, "idx_b": idx_b,
                        "row_a_orig": row_a.to_dict(),
                        "row_b_orig": row_b.to_dict(),
                    }
                    st.rerun()

    # Hiển thị kết quả hoán đổi
    if st.session_state["swap_result"] is not None:
        swap = st.session_state["swap_result"]
        row_a = swap["row_a_orig"]
        row_b = swap["row_b_orig"]

        st.markdown("---")
        st.subheader("📋 Thông tin hoán đổi")

        col_l, col_r = st.columns(2)
        with col_l:
            st.markdown(f"**{row_a['NHAN_VIEN']}**")
            st.write(f"Ngày trực: `{row_a['NGAY_TRUC']}`")
            st.write(f"Thứ: `{row_a['THU']}`")
            st.write(f"Tuần thứ: `{row_a['TUAN_THU']}`")

        with col_r:
            st.markdown(f"**{row_b['NHAN_VIEN']}**")
            st.write(f"Ngày trực: `{row_b['NGAY_TRUC']}`")
            st.write(f"Thứ: `{row_b['THU']}`")
            st.write(f"Tuần thứ: `{row_b['TUAN_THU']}`")

        col_btn_a, col_btn_b, _ = st.columns([1, 1, 3])

        with col_btn_a:
            if st.button("⇄ Hoán đổi"):
                # Thực hiện hoán đổi (chỉ preview, chưa lưu)
                swap["row_a_new"] = {
                    **row_a,
                    "NGAY_TRUC": row_b["NGAY_TRUC"],
                    "THU": row_b["THU"],
                    "TUAN_THU": row_b["TUAN_THU"],
                }
                swap["row_b_new"] = {
                    **row_b,
                    "NGAY_TRUC": row_a["NGAY_TRUC"],
                    "THU": row_a["THU"],
                    "TUAN_THU": row_a["TUAN_THU"],
                }
                st.session_state["swap_result"] = swap
                st.rerun()

        with col_btn_b:
            can_save = "row_a_new" in swap and "row_b_new" in swap
            if st.button("💾 Lưu thay đổi", disabled=not can_save, type="primary"):
                try:
                    ws_out = get_sheet(st.secrets["sheet_name"]["output_1"], "Trang tính1")
                    all_data = ws_out.get_all_values()
                    headers = all_data[0]

                    # Tìm vị trí cột
                    col_idx = {h: i for i, h in enumerate(headers)}
                    # Mapping tên cột sheet -> key trong dict
                    # Sheet headers theo thứ tự: STT,TIMESTAMP,NHAN VIEN,MA NHAN SU,NGAY TRUC,THU,TUAN THU
                    # Tìm dòng tương ứng với row_a và row_b dựa trên nhân viên + ngày trực gốc
                    def find_sheet_row(nv, ngay_orig, thu_orig, tuan_orig):
                        for r_idx, row in enumerate(all_data[1:], start=2):
                            if (len(row) >= 7 and
                                row[2].strip() == str(nv).strip() and
                                row[4].strip() == str(ngay_orig).strip() and
                                row[5].strip() == str(thu_orig).strip() and
                                row[6].strip() == str(tuan_orig).strip()):
                                return r_idx
                        return None

                    row_a_new = swap["row_a_new"]
                    row_b_new = swap["row_b_new"]
                    row_a_orig = swap["row_a_orig"]
                    row_b_orig = swap["row_b_orig"]

                    sheet_row_a = find_sheet_row(
                        row_a_orig["NHAN_VIEN"], row_a_orig["NGAY_TRUC"],
                        row_a_orig["THU"], row_a_orig["TUAN_THU"]
                    )
                    sheet_row_b = find_sheet_row(
                        row_b_orig["NHAN_VIEN"], row_b_orig["NGAY_TRUC"],
                        row_b_orig["THU"], row_b_orig["TUAN_THU"]
                    )

                    if sheet_row_a is None or sheet_row_b is None:
                        st.error("❌ Không tìm thấy dòng dữ liệu tương ứng trong Google Sheet. Vui lòng thử lại.")
                    else:
                        timestamp_now = datetime.now(VN_TZ).strftime("%d/%m/%Y %H:%M:%S")
                        # Cập nhật dòng A: cột E(5), F(6), G(7) = index 4,5,6 (0-based)
                        ws_out.update_cell(sheet_row_a, 2, timestamp_now)
                        ws_out.update_cell(sheet_row_a, 5, row_a_new["NGAY_TRUC"])
                        ws_out.update_cell(sheet_row_a, 6, row_a_new["THU"])
                        ws_out.update_cell(sheet_row_a, 7, str(row_a_new["TUAN_THU"]))

                        ws_out.update_cell(sheet_row_b, 2, timestamp_now)
                        ws_out.update_cell(sheet_row_b, 5, row_b_new["NGAY_TRUC"])
                        ws_out.update_cell(sheet_row_b, 6, row_b_new["THU"])
                        ws_out.update_cell(sheet_row_b, 7, str(row_b_new["TUAN_THU"]))

                        load_output_data.clear()
                        st.success("✅ Đã lưu hoán đổi lịch trực thành công!")
                        st.session_state["swap_result"] = None
                        st.session_state["tab2_df"] = None
                        st.session_state["selected_rows"] = []
                        st.rerun()
                except Exception as e:
                    st.error(f"❌ Lỗi khi lưu: {e}")

        # Hiển thị preview sau hoán đổi
        if "row_a_new" in swap:
            st.markdown("---")
            st.subheader("👁️ Xem trước sau hoán đổi")
            col_l2, col_r2 = st.columns(2)
            with col_l2:
                st.markdown(f"**{swap['row_a_new']['NHAN_VIEN']}** *(sau đổi)*")
                st.write(f"Ngày trực: `{swap['row_a_new']['NGAY_TRUC']}`")
                st.write(f"Thứ: `{swap['row_a_new']['THU']}`")
                st.write(f"Tuần thứ: `{swap['row_a_new']['TUAN_THU']}`")
            with col_r2:
                st.markdown(f"**{swap['row_b_new']['NHAN_VIEN']}** *(sau đổi)*")
                st.write(f"Ngày trực: `{swap['row_b_new']['NGAY_TRUC']}`")
                st.write(f"Thứ: `{swap['row_b_new']['THU']}`")
                st.write(f"Tuần thứ: `{swap['row_b_new']['TUAN_THU']}`")