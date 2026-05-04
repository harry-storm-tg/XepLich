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

def get_sheet3():
    """Trả về worksheet thứ 3 (index 2) của file output_2 từ secrets. Tạo nếu không tồn tại."""
    credentials = load_credentials()
    gc = gspread.authorize(credentials)
    sheet_name = st.secrets["sheet_name"]["output_2"]
    try:
        sh = gc.open(sheet_name)
    except gspread.exceptions.SpreadsheetNotFound:
        # Sheet chưa tồn tại → tạo mới
        sh = gc.create(sheet_name)
        # Thêm 3 worksheet (mặc định có 1)
        sh.add_worksheet("Sheet2", 1000, 7)
        sh.add_worksheet("Sheet3", 1000, 7)
    
    # Lấy worksheet thứ 3 (index 2)
    ws = sh.get_worksheet(2)
    if ws is None:
        # Nếu không có worksheet thứ 3, tạo mới
        ws = sh.add_worksheet("Sheet3", 1000, 7)
    
    return ws

def load_sheet3_df():
    """Đọc toàn bộ dữ liệu sheet 3, trả về DataFrame."""
    try:
        ws = get_sheet3()
        data = ws.get_all_values()
        if len(data) <= 1:
            return pd.DataFrame(columns=["STT", "TIMESTAMP", "NHÂN VIÊN",
                                         "LOẠI (CT/BT)", "NỘI DUNG", "NGÀY", "BUỔI"])
        header = data[0]
        rows = data[1:]
        df = pd.DataFrame(rows, columns=header)
        # Loại bỏ dòng hoàn toàn trống
        df = df[df["STT"].str.strip() != ""]
        return df
    except Exception as e:
        st.error(f"Lỗi khi đọc dữ liệu từ Google Sheets: {e}")
        # Trả về DataFrame trống để app không crash
        return pd.DataFrame(columns=["STT", "TIMESTAMP", "NHÂN VIÊN",
                                     "LOẠI (CT/BT)", "NỘI DUNG", "NGÀY", "BUỔI"])

def is_duplicate(df: pd.DataFrame, nhan_vien: str, loai: str,
                 ngay_str: str, buoi: str) -> bool:
    """
    Kiểm tra trùng lặp theo: nhân viên + loại + ngày + buổi.
    Quy tắc buổi: "S - C" đã bao gồm "S" và "C".
    """
    mask = (
        (df["NHÂN VIÊN"].str.strip() == nhan_vien) &
        (df["LOẠI (CT/BT)"].str.strip() == loai) &
        (df["NGÀY"].str.strip() == ngay_str)
    )
    existing = df[mask]["BUỔI"].str.strip().tolist()
    for ex in existing:
        if ex == "S - C":
            return True          # đã đăng ký cả ngày → bất kỳ buổi nào cũng trùng
        if buoi == "S - C" and ex in ("S", "C"):
            return True          # người dùng chọn cả ngày, ngày đó đã có S hoặc C
        if ex == buoi:
            return True
    return False

def upload_rows(rows: list[dict]):
    """
    Thêm các dòng mới vào cuối sheet 3.
    rows: list of dict với keys STT, TIMESTAMP, NHÂN VIÊN, LOẠI (CT/BT), NỘI DUNG, NGÀY, BUỔI
    """
    ws = get_sheet3()
    existing = ws.get_all_values()
    next_stt = len(existing)  # dòng header là 1, nên số dòng = STT tiếp theo

    values_to_append = []
    for r in rows:
        values_to_append.append([
            str(next_stt),
            r["TIMESTAMP"],
            r["NHÂN VIÊN"],
            r["LOẠI (CT/BT)"],
            r["NỘI DUNG"],
            r["NGÀY"],
            r["BUỔI"],
        ])
        next_stt += 1

    ws.append_rows(values_to_append, value_input_option="USER_ENTERED")

def update_row(sheet_row_index: int, timestamp: str, loai: str,
               noi_dung: str, ngay: str, buoi: str):
    """
    Cập nhật dòng tại vị trí sheet_row_index (1-based, tính cả header).
    Chỉ cập nhật cột B(2) đến G(7).
    """
    ws = get_sheet3()
    ws.update(f"B{sheet_row_index}:G{sheet_row_index}",
              [[timestamp, None, loai, noi_dung, ngay, buoi]],
              value_input_option="USER_ENTERED")

# ======================== HELPER UI ========================

LOAI_OPTIONS = ["Công tác", "Bù trực"]
BUOI_OPTIONS  = ["Buổi sáng", "Buổi chiều", "Cả ngày"]
BUOI_MAP      = {"Buổi sáng": "S", "Buổi chiều": "C", "Cả ngày": "S - C"}
LOAI_MAP      = {"Công tác": "CT", "Bù trực": "BT"}

def render_block(idx: int, default: dict | None = None):
    """
    Render 1 block đăng ký. Trả về dict dữ liệu hoặc None nếu chưa đủ.
    default: dùng khi chỉnh sửa (prefill giá trị).
    """
    d = default or {}
    today = date.today()
    max_date = today + timedelta(days=183)  # ~6 tháng

    with st.container(border=True):
        st.markdown(f"**Đăng ký #{idx + 1}**")

        col1, col2 = st.columns(2)
        with col1:
            loai_default_idx = 0
            if d.get("loai"):
                inv = {v: k for k, v in LOAI_MAP.items()}
                loai_default_idx = LOAI_OPTIONS.index(inv.get(d["loai"], "Công tác"))
            loai_label = st.selectbox("Loại đăng ký", LOAI_OPTIONS,
                                      index=loai_default_idx,
                                      key=f"loai_{idx}")
        with col2:
            if loai_label == "Công tác":
                noi_dung = st.text_input("Diễn giải",
                                         value=d.get("noi_dung", ""),
                                         key=f"noidung_{idx}")
            else:
                noi_dung = ""
                st.markdown(" ")  # placeholder spacing

        nhieu_ngay_default = False
        if d.get("ngay_end"):
            nhieu_ngay_default = True

        che_do = st.radio("Chế độ đăng ký",
                          ["Đăng ký 1 ngày", "Đăng ký nhiều ngày"],
                          index=1 if nhieu_ngay_default else 0,
                          horizontal=True,
                          key=f"cheodo_{idx}")

        col3, col4 = st.columns(2)
        with col3:
            if che_do == "Đăng ký 1 ngày":
                ngay_val = d.get("ngay_start") or today
                if isinstance(ngay_val, str):
                    try:
                        ngay_val = datetime.strptime(ngay_val, "%d/%m/%Y").date()
                    except Exception:
                        ngay_val = today
                ngay_single = st.date_input("Chọn ngày",
                                             value=ngay_val,
                                             min_value=today,
                                             max_value=max_date,
                                             key=f"ngay_{idx}",
                                             format="DD/MM/YYYY")
                ngay_list = [ngay_single]
            else:
                start_val = d.get("ngay_start") or today
                end_val   = d.get("ngay_end") or today
                if isinstance(start_val, str):
                    try:
                        start_val = datetime.strptime(start_val, "%d/%m/%Y").date()
                    except Exception:
                        start_val = today
                if isinstance(end_val, str):
                    try:
                        end_val = datetime.strptime(end_val, "%d/%m/%Y").date()
                    except Exception:
                        end_val = today

                ngay_range = st.date_input("Từ ngày → Đến ngày",
                                            value=(start_val, end_val),
                                            min_value=today,
                                            max_value=max_date,
                                            key=f"ngayrange_{idx}",
                                            format="DD/MM/YYYY")
                if isinstance(ngay_range, (list, tuple)) and len(ngay_range) == 2:
                    start_d, end_d = ngay_range
                    if start_d > end_d:
                        st.warning("Ngày bắt đầu phải nhỏ hơn hoặc bằng ngày kết thúc.")
                        ngay_list = []
                    else:
                        delta = (end_d - start_d).days + 1
                        ngay_list = [start_d + timedelta(days=i) for i in range(delta)]
                else:
                    ngay_list = []

        with col4:
            buoi_default_idx = 0
            if d.get("buoi"):
                inv_buoi = {v: k for k, v in BUOI_MAP.items()}
                buoi_label_default = inv_buoi.get(d["buoi"], "Buổi sáng")
                buoi_default_idx = BUOI_OPTIONS.index(buoi_label_default)
            buoi_label = st.selectbox("Chọn buổi", BUOI_OPTIONS,
                                      index=buoi_default_idx,
                                      key=f"buoi_{idx}")

    return {
        "loai_label": loai_label,
        "loai": LOAI_MAP[loai_label],
        "noi_dung": noi_dung,
        "ngay_list": ngay_list,
        "buoi_label": buoi_label,
        "buoi": BUOI_MAP[buoi_label],
    }

# ======================== TABS ========================

def tab_dang_ky(nhan_vien: str):
    st.subheader("📝 Đăng ký lịch công tác / bù trực")

    # Khởi tạo session state
    if "blocks" not in st.session_state:
        st.session_state.blocks = [{}]
    if "submitted" not in st.session_state:
        st.session_state.submitted = False

    block_data = []
    for i, default in enumerate(st.session_state.blocks):
        data = render_block(i, default)
        block_data.append(data)

    col_add, col_send = st.columns([1, 1])

    with col_add:
        if st.button("➕ Thêm khác", use_container_width=True):
            st.session_state.blocks.append({})
            st.rerun()

    with col_send:
        if st.button("✅ Gửi đăng ký", type="primary", use_container_width=True):
            # Validate & chuẩn bị dữ liệu
            df_existing = load_sheet3_df()
            rows_to_upload = []
            has_error = False

            for bd in block_data:
                if not bd["ngay_list"]:
                    st.error("Vui lòng chọn khoảng ngày hợp lệ.")
                    has_error = True
                    break
                if bd["loai"] == "CT" and not bd["noi_dung"].strip():
                    st.error("Vui lòng nhập Diễn giải cho loại Công tác.")
                    has_error = True
                    break

                for ngay in bd["ngay_list"]:
                    ngay_str = ngay.strftime("%d/%m/%Y")
                    loai_full = "Công tác" if bd["loai"] == "CT" else "Bù trực"
                    if is_duplicate(df_existing, nhan_vien,
                                    bd["loai"], ngay_str, bd["buoi"]):
                        st.error(
                            f"⚠️ Bạn đã đăng ký lịch {loai_full} vào ngày {ngay_str} rồi !"
                        )
                        has_error = True
                        break

                    rows_to_upload.append({
                        "TIMESTAMP": datetime.now(VN_TZ).strftime("%d/%m/%Y %H:%M:%S"),
                        "NHÂN VIÊN": nhan_vien,
                        "LOẠI (CT/BT)": bd["loai"],
                        "NỘI DUNG": bd["noi_dung"],
                        "NGÀY": ngay_str,
                        "BUỔI": bd["buoi"],
                    })
                if has_error:
                    break

            if not has_error and rows_to_upload:
                try:
                    upload_rows(rows_to_upload)
                    st.session_state.submitted = True
                    st.session_state.blocks = [{}]
                    st.success(f"✅ Đã gửi {len(rows_to_upload)} dòng đăng ký thành công!")
                    st.balloons()
                except Exception as e:
                    st.error(f"Lỗi khi ghi dữ liệu: {e}")


def tab_xem_lich(nhan_vien: str):
    st.subheader("📅 Xem lịch đã đăng ký")

    today = date.today()
    min_date_view = today - timedelta(days=90)   # 3 tháng trước
    max_date_view = today + timedelta(days=183)  # 6 tháng sau

    col1, col2, col3 = st.columns(3)
    with col1:
        from_date = st.date_input("Từ ngày",
                                   value=today,
                                   min_value=min_date_view,
                                   max_value=max_date_view,
                                   key="view_from",
                                   format="DD/MM/YYYY")
    with col2:
        to_date = st.date_input("Đến ngày",
                                 value=today + timedelta(days=30),
                                 min_value=min_date_view,
                                 max_value=max_date_view,
                                 key="view_to",
                                 format="DD/MM/YYYY")
    with col3:
        loai_xem = st.selectbox("Loại đăng ký",
                                 ["Tất cả", "Công tác (CT)", "Bù trực (BT)"],
                                 key="view_loai")

    if st.button("🔍 OK", type="primary"):
        if from_date > to_date:
            st.error("Ngày bắt đầu phải nhỏ hơn hoặc bằng ngày kết thúc.")
            return

        df = load_sheet3_df()
        if df.empty:
            st.info("Không có dữ liệu theo yêu cầu.")
            return

        # Lọc theo nhân viên
        df = df[df["NHÂN VIÊN"].str.strip() == nhan_vien]

        # Lọc theo loại
        if loai_xem == "Công tác (CT)":
            df = df[df["LOẠI (CT/BT)"].str.strip() == "CT"]
        elif loai_xem == "Bù trực (BT)":
            df = df[df["LOẠI (CT/BT)"].str.strip() == "BT"]

        # Parse ngày để lọc khoảng
        def parse_ngay(s):
            try:
                return datetime.strptime(s.strip(), "%d/%m/%Y").date()
            except Exception:
                return None

        df["_ngay_dt"] = df["NGÀY"].apply(parse_ngay)
        df = df[df["_ngay_dt"].notna()]
        df = df[(df["_ngay_dt"] >= from_date) & (df["_ngay_dt"] <= to_date)]

        if df.empty:
            st.info("Không có dữ liệu theo yêu cầu.")
            return

        # Lưu vào session state để render bảng
        st.session_state["view_df"] = df.reset_index(drop=True)
        st.session_state["edit_row_idx"] = None

    # Render bảng kết quả
    if "view_df" in st.session_state and st.session_state["view_df"] is not None:
        df_show = st.session_state["view_df"]

        st.markdown(f"**Tìm thấy {len(df_show)} kết quả:**")
        
        cutoff_edit = date.today() - timedelta(days=7)

        # Header bảng
        hcols = st.columns([2, 2, 1.5, 2.5, 1.8, 1.2, 1.5])
        headers = ["Thời gian ĐK", "Tên nhân viên", "Loại ĐK",
                   "Nội dung", "Ngày ĐK", "Buổi", ""]
        for hc, ht in zip(hcols, headers):
            hc.markdown(f"**{ht}**")
        st.divider()

        for i, row in df_show.iterrows():
            rcols = st.columns([2, 2, 1.5, 2.5, 1.8, 1.2, 1.5])
            rcols[0].write(row.get("TIMESTAMP", ""))
            rcols[1].write(row.get("NHÂN VIÊN", ""))
            loai_val = row.get("LOẠI (CT/BT)", "")
            rcols[2].write("Công tác" if loai_val == "CT" else "Bù trực")
            rcols[3].write(row.get("NỘI DUNG", ""))
            rcols[4].write(row.get("NGÀY", ""))
            rcols[5].write(row.get("BUỔI", ""))

            # Xác định nút chỉnh sửa có hoạt động không
            ngay_dk = row.get("_ngay_dt")
            can_edit = (ngay_dk is not None) and (ngay_dk > cutoff_edit)

            if rcols[6].button("✏️ Sửa", key=f"edit_btn_{i}",
                               disabled=not can_edit,
                               use_container_width=True):
                st.session_state["edit_row_idx"] = i
                st.session_state["edit_row_data"] = row.to_dict()
                st.rerun()

        st.divider()

        # Form chỉnh sửa
        if st.session_state.get("edit_row_idx") is not None:
            edit_idx = st.session_state["edit_row_idx"]
            edit_row = st.session_state["edit_row_data"]

            st.markdown(f"### ✏️ Chỉnh sửa dòng #{edit_idx + 1}")

            # Chuẩn bị default cho render_block
            inv_loai = {"CT": "Công tác", "BT": "Bù trực"}
            inv_buoi = {"S": "Buổi sáng", "C": "Buổi chiều", "S - C": "Cả ngày"}
            try:
                ngay_dt = datetime.strptime(edit_row.get("NGÀY", ""), "%d/%m/%Y").date()
            except Exception:
                ngay_dt = date.today()

            default_edit = {
                "loai": edit_row.get("LOẠI (CT/BT)", "CT"),
                "noi_dung": edit_row.get("NỘI DUNG", ""),
                "ngay_start": ngay_dt,
                "ngay_end": None,
                "buoi": edit_row.get("BUỔI", "S"),
            }

            edit_data = render_block(9999, default=default_edit)

            col_save, col_cancel = st.columns(2)
            with col_save:
                if st.button("💾 Lưu thay đổi", type="primary", use_container_width=True):
                    if not edit_data["ngay_list"]:
                        st.error("Vui lòng chọn ngày hợp lệ.")
                    elif edit_data["loai"] == "CT" and not edit_data["noi_dung"].strip():
                        st.error("Vui lòng nhập Diễn giải.")
                    else:
                        # Tìm dòng thực trên sheet (STT + 2 vì header ở row 1, data từ row 2)
                        try:
                            stt_val = int(edit_row.get("STT", 0))
                            sheet_row = stt_val + 1  # STT bắt đầu từ 1 → row index = STT + 1
                        except Exception:
                            sheet_row = None

                        if sheet_row:
                            new_ts = datetime.now(VN_TZ).strftime("%d/%m/%Y %H:%M:%S")
                            new_ngay = edit_data["ngay_list"][0].strftime("%d/%m/%Y")
                            try:
                                update_row(
                                    sheet_row_index=sheet_row,
                                    timestamp=new_ts,
                                    loai=edit_data["loai"],
                                    noi_dung=edit_data["noi_dung"],
                                    ngay=new_ngay,
                                    buoi=edit_data["buoi"],
                                )
                                st.success("✅ Đã lưu thay đổi thành công!")
                                st.session_state["edit_row_idx"] = None
                                st.session_state["view_df"] = None
                                st.rerun()
                            except Exception as e:
                                st.error(f"Lỗi khi cập nhật: {e}")
                        else:
                            st.error("Không xác định được dòng cần cập nhật.")

            with col_cancel:
                if st.button("❌ Hủy", use_container_width=True):
                    st.session_state["edit_row_idx"] = None
                    st.rerun()


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
            <p>ĐĂNG KÝ LỊCH CÔNG TÁC</p>
        </div>
    </div>
    <div class="header-underline"></div>
""", unsafe_allow_html=True)

nhan_vien = st.session_state.get("username", "Không xác định")
st.html(f'<p class="demuc"><i>Bác sĩ đang thực hiện: {nhan_vien}</i></p>')

# Khởi tạo các session state cần thiết
if "edit_row_idx" not in st.session_state:
    st.session_state["edit_row_idx"] = None
if "view_df" not in st.session_state:
    st.session_state["view_df"] = None

tab1, tab2 = st.tabs(["📝 Đăng ký lịch công tác / bù trực", "📅 Xem lịch đã đăng ký"])

with tab1:
    tab_dang_ky(nhan_vien)

with tab2:
    tab_xem_lich(nhan_vien)
