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

def get_sheet():
    creds = load_credentials()
    client = gspread.authorize(creds)
    spreadsheet_name = st.secrets["sheet_name"]["output_2"]
    spreadsheet = client.open(spreadsheet_name)
    return spreadsheet.worksheet("Trang tính1")

def load_data():
    sheet = get_sheet()
    data = sheet.get_all_values()
    if len(data) <= 1:
        return pd.DataFrame(columns=["STT", "TIMESTAMP", "NHÂN VIÊN", "LOẠI YÊU CẦU", "NGÀY", "BUỔI", "LÍ DO", "TÌNH TRẠNG DUYỆT"])
    df = pd.DataFrame(data[1:], columns=["STT", "TIMESTAMP", "NHÂN VIÊN", "LOẠI YÊU CẦU", "NGÀY", "BUỔI", "LÍ DO", "TÌNH TRẠNG DUYỆT"])
    return df

def get_next_stt(df):
    if df.empty or df["STT"].replace("", pd.NA).dropna().empty:
        return 1
    try:
        return int(df["STT"].replace("", pd.NA).dropna().astype(int).max()) + 1
    except Exception:
        return 1

def daterange(start_date, end_date):
    for n in range(int((end_date - start_date).days) + 1):
        yield start_date + timedelta(n)

def check_duplicate(df, nhan_vien, loai_yc, ngay_str, buoi, exclude_stt=None):
    mask = (
        (df["NHÂN VIÊN"] == nhan_vien) &
        (df["LOẠI YÊU CẦU"] == loai_yc) &
        (df["NGÀY"] == ngay_str) &
        (df["BUỔI"] == buoi)
    )
    if exclude_stt:
        mask = mask & (df["STT"] != str(exclude_stt))
    return df[mask].shape[0] > 0

# ======================== MAIN ========================

css_path = pathlib.Path("asset/style.css")
if css_path.exists():
    load_css(css_path)

try:
    img = get_img_as_base64("pages/img/logo.png")
    logo_html = f'<img src="data:image/png;base64,{img}" alt="logo">'
except Exception:
    logo_html = ""

st.markdown(f"""
    <div class="fixed-header">
        <div class="header-content">
            {logo_html}
            <div class="header-text">
                <h1>BỆNH VIỆN ĐA KHOA MỸ ĐỨC<span style="vertical-align: super; font-size: 0.6em;">&#174;</span></h1>
            </div>
        </div>
        <div class="header-subtext">
            <p>ĐĂNG KÝ NGHỈ PHÉP</p>
        </div>
    </div>
    <div class="header-underline"></div>
""", unsafe_allow_html=True)

nhan_vien = st.session_state.get("username", "Không xác định")
st.html(f'<p class="demuc"><i>Bác sĩ đang thực hiện: {nhan_vien}</i></p>')

# Session state init
for key in ["edit_row_idx", "view_df", "confirm_delete_idx"]:
    if key not in st.session_state:
        st.session_state[key] = None

if "dangky_list" not in st.session_state:
    st.session_state["dangky_list"] = [{"loai": "Đăng ký phép mới", "tu_ngay": date.today(), "den_ngay": date.today(), "single": True, "buoi": "Cả ngày", "ly_do": ""}]

today = date.today()
max_date = today + timedelta(days=90)

tab1, tab2, tab3 = st.tabs(["📋 Đăng ký phép", "👤 Theo dõi phép cá nhân", "🏥 Theo dõi phép hệ thống"])

# ===================== TAB 1 =====================
with tab1:
    st.subheader("Đăng ký nghỉ phép")

    for i, entry in enumerate(st.session_state["dangky_list"]):
        with st.expander(f"📌 Gói đăng ký #{i+1}", expanded=True):
            col1, col2 = st.columns([1, 1])
            with col1:
                loai = st.selectbox(
                    "Loại yêu cầu",
                    ["Đăng ký phép mới", "Hủy phép đã đăng ký"],
                    index=0 if entry["loai"] == "Đăng ký phép mới" else 1,
                    key=f"loai_{i}"
                )
                st.session_state["dangky_list"][i]["loai"] = loai

            with col2:
                buoi = st.selectbox(
                    "Buổi",
                    ["Sáng", "Chiều", "Cả ngày"],
                    index=["Sáng", "Chiều", "Cả ngày"].index(entry.get("buoi", "Cả ngày")),
                    key=f"buoi_{i}"
                )
                st.session_state["dangky_list"][i]["buoi"] = buoi

            single_mode = st.checkbox("Chọn 1 ngày", value=entry.get("single", True), key=f"single_{i}")
            st.session_state["dangky_list"][i]["single"] = single_mode

            if single_mode:
                ngay_chon = st.date_input(
                    "Chọn ngày nghỉ",
                    value=entry.get("tu_ngay", today),
                    min_value=today,
                    max_value=max_date,
                    key=f"ngay_{i}"
                )
                st.session_state["dangky_list"][i]["tu_ngay"] = ngay_chon
                st.session_state["dangky_list"][i]["den_ngay"] = ngay_chon
            else:
                col_a, col_b = st.columns(2)
                with col_a:
                    tu_ngay = st.date_input(
                        "Từ ngày",
                        value=entry.get("tu_ngay", today),
                        min_value=today,
                        max_value=max_date,
                        key=f"tu_{i}"
                    )
                with col_b:
                    den_ngay = st.date_input(
                        "Đến ngày",
                        value=entry.get("den_ngay", today),
                        min_value=today,
                        max_value=max_date,
                        key=f"den_{i}"
                    )
                if den_ngay < tu_ngay:
                    st.error("Ngày kết thúc phải sau hoặc bằng ngày bắt đầu.")
                st.session_state["dangky_list"][i]["tu_ngay"] = tu_ngay
                st.session_state["dangky_list"][i]["den_ngay"] = den_ngay

            ly_do = st.text_input("Lí do", value=entry.get("ly_do", ""), key=f"lydo_{i}")
            st.session_state["dangky_list"][i]["ly_do"] = ly_do

            if len(st.session_state["dangky_list"]) > 1:
                if st.button(f"🗑️ Xóa gói #{i+1}", key=f"del_{i}"):
                    st.session_state["dangky_list"].pop(i)
                    st.rerun()

    col_add, col_send = st.columns([1, 2])
    with col_add:
        if st.button("➕ Thêm gói đăng ký"):
            st.session_state["dangky_list"].append({
                "loai": "Đăng ký phép mới",
                "tu_ngay": today,
                "den_ngay": today,
                "single": True,
                "buoi": "Cả ngày",
                "ly_do": ""
            })
            st.rerun()

    with col_send:
        if st.button("📨 Gửi đăng ký", type="primary"):
            # Build rows to upload
            rows_to_upload = []
            has_error = False

            try:
                df_existing = load_data()
            except Exception as e:
                st.error(f"Không thể kết nối Google Sheet: {e}")
                st.stop()

            timestamp_now = datetime.now(VN_TZ).strftime("%d/%m/%Y %H:%M:%S")
            next_stt = get_next_stt(df_existing)

            for entry in st.session_state["dangky_list"]:
                tu_ngay = entry["tu_ngay"]
                den_ngay = entry["den_ngay"]
                loai = entry["loai"]
                buoi_sel = entry["buoi"]
                ly_do = entry["ly_do"]

                if den_ngay < tu_ngay:
                    st.error(f"Gói đăng ký có ngày không hợp lệ (đến ngày < từ ngày).")
                    has_error = True
                    break

                # Map buoi
                buoi_map = {"Sáng": ["S"], "Chiều": ["C"], "Cả ngày": ["S", "C"]}
                buoi_list = buoi_map[buoi_sel]

                # Đếm số dòng sẽ được thêm cho gói này
                rows_count_this_package = 0
                for single_date in daterange(tu_ngay, den_ngay):
                    rows_count_this_package += len(buoi_list)

                for single_date in daterange(tu_ngay, den_ngay):
                    ngay_str = single_date.strftime("%d/%m/%Y")
                    for b in buoi_list:
                        # Check duplicate
                        dup = check_duplicate(df_existing, nhan_vien, loai, ngay_str, b)
                        # Also check in pending rows_to_upload
                        for pending in rows_to_upload:
                            if (pending[2] == nhan_vien and pending[3] == loai and
                                    pending[4] == ngay_str and pending[5] == b):
                                dup = True
                                break
                        if dup:
                            st.error(f"❌ Trùng lặp: {loai} - {ngay_str} - {'Sáng' if b == 'S' else 'Chiều'} đã được đăng ký trước đó!")
                            has_error = True
                            break
                        rows_to_upload.append([str(next_stt), timestamp_now, nhan_vien, loai, ngay_str, b, ly_do, ""])
                    if has_error:
                        break
                
                # Tăng STT cho gói tiếp theo
                if not has_error:
                    next_stt += rows_count_this_package
                
                if has_error:
                    break

            if not has_error and rows_to_upload:
                try:
                    sheet = get_sheet()
                    sheet.append_rows(rows_to_upload, value_input_option="USER_ENTERED")
                    st.success(f"✅ Đăng ký thành công!")
                    st.session_state["dangky_list"] = [{"loai": "Đăng ký phép mới", "tu_ngay": today, "den_ngay": today, "single": True, "buoi": "Cả ngày", "ly_do": ""}]
                    st.rerun()
                except Exception as e:
                    st.error(f"Lỗi khi ghi dữ liệu: {e}")
            elif not has_error:
                st.warning("Không có dữ liệu để gửi.")

# ===================== TAB 2 =====================
with tab2:
    st.subheader("Theo dõi phép cá nhân")

    with st.form("form_ca_nhan"):
        col1, col2 = st.columns(2)
        with col1:
            tu_ngay_cn = st.date_input("Từ ngày", value=today - timedelta(days=30), key="cn_tu")
        with col2:
            den_ngay_cn = st.date_input("Đến ngày", value=today + timedelta(days=30), key="cn_den")
        
        loai_cn = st.selectbox("Loại đăng ký", ["Tất cả", "Đăng ký phép mới", "Hủy phép đã đăng ký"], key="cn_loai")
        submitted_cn = st.form_submit_button("🔍 OK")

    if submitted_cn:
        try:
            df = load_data()
        except Exception as e:
            st.error(f"Không thể tải dữ liệu: {e}")
            st.stop()

        # Filter by user
        df_user = df[df["NHÂN VIÊN"] == nhan_vien].copy()

        # Parse dates
        def parse_date_safe(d):
            try:
                return datetime.strptime(d, "%d/%m/%Y").date()
            except Exception:
                return None

        df_user["_date"] = df_user["NGÀY"].apply(parse_date_safe)
        df_user = df_user[df_user["_date"].notna()]
        df_user = df_user[(df_user["_date"] >= tu_ngay_cn) & (df_user["_date"] <= den_ngay_cn)]

        if loai_cn != "Tất cả":
            df_user = df_user[df_user["LOẠI YÊU CẦU"] == loai_cn]

        if df_user.empty:
            st.info("Không có dữ liệu trong khoảng thời gian đã chọn.")
        else:
            # Group by STT (same registration batch)
            def group_registrations(group):
                dates = sorted(group["_date"].tolist())
                if len(dates) == 1:
                    date_display = dates[0].strftime("%d/%m/%Y")
                else:
                    date_display = f"{dates[0].strftime('%d/%m/%Y')} - {dates[-1].strftime('%d/%m/%Y')}"

                buoi_vals = group["BUỔI"].tolist()
                # Convert S/C back to readable
                buoi_map_rev = {"S": "Sáng", "C": "Chiều", "S - C": "Cả ngày"}
                buoi_display = ", ".join([buoi_map_rev.get(b, b) for b in sorted(set(buoi_vals))])

                loai_yc = group["LOẠI YÊU CẦU"].iloc[0]
                ly_do = group["LÍ DO"].iloc[0]
                timestamp = group["TIMESTAMP"].iloc[0]
                tinh_trang_vals = group["TÌNH TRẠNG DUYỆT"].tolist()
                # Use most "final" status
                if "Không duyệt" in tinh_trang_vals:
                    tinh_trang = "Không duyệt"
                elif "Đã duyệt" in tinh_trang_vals:
                    tinh_trang = "Đã duyệt"
                else:
                    tinh_trang = ""

                return pd.Series({
                    "Nhân viên": group["NHÂN VIÊN"].iloc[0],
                    "Loại đăng ký": loai_yc,
                    "Ngày": date_display,
                    "Buổi": buoi_display,
                    "Lí do": ly_do,
                    "Thời gian đăng ký": timestamp,
                    "Tình trạng duyệt": tinh_trang,
                    "_min_date": dates[0]
                })

            df_grouped = df_user.groupby("STT").apply(group_registrations).reset_index(drop=True)
            df_grouped = df_grouped.sort_values("_min_date", ascending=False).drop(columns=["_min_date"])

            def color_tinh_trang(val):
                if val == "Đã duyệt":
                    return '<span style="color:green; font-weight:bold;">Đã duyệt</span>'
                elif val == "Không duyệt":
                    return '<span style="color:red; font-weight:bold;">Không duyệt</span>'
                else:
                    return '<span style="color:gray;">Đợi duyệt</span>'

            df_display = df_grouped.copy()
            df_display["Tình trạng duyệt"] = df_display["Tình trạng duyệt"].apply(color_tinh_trang)

            st.markdown(
                df_display.to_html(escape=False, index=False),
                unsafe_allow_html=True
            )

# ===================== TAB 3 =====================
with tab3:
    st.subheader("Theo dõi phép hệ thống")

    with st.form("form_he_thong"):
        col1, col2 = st.columns(2)
        with col1:
            tu_ngay_ht = st.date_input("Từ ngày", value=today - timedelta(days=7), key="ht_tu")
        with col2:
            den_ngay_ht = st.date_input("Đến ngày", value=today + timedelta(days=30), key="ht_den")
        
        loai_ht = st.selectbox("Loại đăng ký", ["Tất cả", "Đăng ký phép mới", "Hủy phép đã đăng ký"], key="ht_loai")
        submitted_ht = st.form_submit_button("🔍 OK")

    if submitted_ht:
        try:
            df = load_data()
        except Exception as e:
            st.error(f"Không thể tải dữ liệu: {e}")
            st.stop()

        def parse_date_safe(d):
            try:
                return datetime.strptime(d, "%d/%m/%Y").date()
            except Exception:
                return None

        df["_date"] = df["NGÀY"].apply(parse_date_safe)
        df_f = df[df["_date"].notna()].copy()
        df_f = df_f[(df_f["_date"] >= tu_ngay_ht) & (df_f["_date"] <= den_ngay_ht)]

        if loai_ht != "Tất cả":
            df_f = df_f[df_f["LOẠI YÊU CẦU"] == loai_ht]

        if df_f.empty:
            st.info("Không có dữ liệu trong khoảng thời gian đã chọn.")
        else:
            # Expand "S - C" into two rows S and C
            expanded_rows = []
            for _, row in df_f.iterrows():
                buoi = row["BUỔI"]
                if buoi == "S - C":
                    for b in ["S", "C"]:
                        r = row.copy()
                        r["BUỔI"] = b
                        expanded_rows.append(r)
                else:
                    expanded_rows.append(row)
            df_exp = pd.DataFrame(expanded_rows)

            # Group by date + buoi
            thu_map = {0: "Thứ 2", 1: "Thứ 3", 2: "Thứ 4", 3: "Thứ 5", 4: "Thứ 6", 5: "Thứ 7", 6: "Chủ nhật"}

            results = []
            for (ngay, buoi), grp in df_exp.groupby(["_date", "BUỔI"]):
                so_dang_ky = (
                    (grp["LOẠI YÊU CẦU"] == "Đăng ký phép mới").sum() -
                    (grp["LOẠI YÊU CẦU"] == "Hủy phép đã đăng ký").sum()
                )
                approved = grp[grp["TÌNH TRẠNG DUYỆT"] == "Đã duyệt"]
                so_duyet = (
                    (approved["LOẠI YÊU CẦU"] == "Đăng ký phép mới").sum() -
                    (approved["LOẠI YÊU CẦU"] == "Hủy phép đã đăng ký").sum()
                )
                ten_duyet = ", ".join(sorted(
                    approved[approved["LOẠI YÊU CẦU"] == "Đăng ký phép mới"]["NHÂN VIÊN"].unique().tolist()
                ))

                results.append({
                    "Thứ": thu_map[ngay.weekday()],
                    "Ngày": ngay.strftime("%d/%m/%Y"),
                    "Buổi": "Sáng" if buoi == "S" else "Chiều",
                    "Số phép đã đăng ký": max(so_dang_ky, 0),
                    "Số phép đã duyệt": max(so_duyet, 0),
                    "Nhân viên được duyệt": ten_duyet,
                    "_date": ngay,
                    "_buoi_sort": 0 if buoi == "S" else 1
                })

            df_result = pd.DataFrame(results)
            df_result = df_result.sort_values(["_date", "_buoi_sort"]).drop(columns=["_date", "_buoi_sort"])
            st.dataframe(df_result, use_container_width=True, hide_index=True)