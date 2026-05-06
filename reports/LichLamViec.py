"""
XẾP LỊCH LÀM VIỆC TỰ ĐỘNG
Bệnh viện Đa khoa Mỹ Đức

Cấu trúc dữ liệu thực tế:
  input_1  / Trang tính1  : Input_NhanSu   – cột A=MÃ NHÂN SỰ, B=MÃ CHUYÊN KHOA,
                                              C=STT NHÓM, D=STT NHÂN VIÊN, E=HỌ VÀ TÊN
  input_2  / Trang tính1  : Input_ViTri    – cột A=ID, B=TÊN, C=VỊ TRÍ, D=KHẢ NĂNG(0/1)
  output_1 / Trang tính1  : Lịch trực      – cột C=NHÂN VIÊN, D=MÃ NHÂN SỰ, E=NGÀY TRỰC, F=THỨ, G=TUẦN THỨ
  output_1 / Trang tính2  : Lịch PK        – cột C=NHÂN VIÊN, D=MÃ NV, E=NGÀY, F=LOẠI PK, G=BUỔI, H=TUẦN THỨ
  output_2 / Trang tính1  : Nghỉ phép      – cột C=NHÂN VIÊN, D=LOẠI YÊU CẦU, E=NGÀY, F=BUỔI, H=TÌNH TRẠNG DUYỆT
  output_2 / Trang tính2  : Lịch học       – cột C=NHÂN VIÊN, D=MÃ NV, E=NGÀY, F=BUỔI
  output_2 / Trang tính3  : CT/KH/BT       – cột C=NHÂN VIÊN, D=LOẠI(CT/KH/BT), F=NGÀY, G=BUỔI
"""

import streamlit as st
import pandas as pd
import gspread
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
import pathlib
import base64
from google.oauth2.service_account import Credentials

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")

# ═══════════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════════
ANCHOR_DATE = date(2026, 4, 27)          # Tuần 1

BUOI_COLS   = ["Sáng", "Trưa", "Chiều", "Tối"]
THU_VI      = {0:"Thứ Hai", 1:"Thứ Ba", 2:"Thứ Tư",
               3:"Thứ Năm", 4:"Thứ Sáu", 5:"Thứ Bảy", 6:"Chủ Nhật"}

# Mã không tính là "có việc" khi thống kê nhân sự
NON_WORK_CODES = {"H","CT","KH","P","BT","VT","RT"}

# Màu nhóm (theo 3 ký tự đầu mã NV: S01/S02/S03/I01/A01)
GROUP_COLOR = {
    "S01": "#dbeafe",   # xanh nhạt
    "S02": "#dcfce7",   # xanh lá
    "S03": "#fef9c3",   # vàng nhạt
    "I01": "#fce7f3",   # hồng nhạt
    "A01": "#ede9fe",   # tím nhạt
}
DEFAULT_GROUP_COLOR = "#f1f5f9"

# Màu buổi
BUOI_STYLE = {
    "Sáng":  {"bg":"#fffbeb", "border":"#fbbf24"},
    "Trưa":  {"bg":"#f0fdf4", "border":"#34d399"},
    "Chiều": {"bg":"#eff6ff", "border":"#60a5fa"},
    "Tối":   {"bg":"#fdf4ff", "border":"#c084fc"},
}

# Decode buổi từ ký tự viết tắt trong dữ liệu
BUOI_DECODE = {
    "S":"Sáng","SÁNG":"Sáng",
    "T":"Trưa","TRƯA":"Trưa",
    "C":"Chiều","CHIỀU":"Chiều",
    "TO":"Tối","TỐI":"Tối",
    "S - C":"Sáng",          # khi có cả S và C thì xử lý từng entry
    "S-C":"Sáng",
}


# ═══════════════════════════════════════════════════════════════════
# UTILS
# ═══════════════════════════════════════════════════════════════════
@st.cache_data(ttl=3600)
def get_img_as_base64(file):
    with open(file, "rb") as f:
        return base64.b64encode(f.read()).decode()

def load_css(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except Exception:
        pass

@st.cache_data(ttl=3600)
def load_credentials():
    s = st.secrets["google_service_account"]
    return Credentials.from_service_account_info(dict(s), scopes=[
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ])

def get_key(secret_name: str) -> str:
    url = st.secrets.get(secret_name, "")
    if "spreadsheets/d/" in url:
        return url.split("spreadsheets/d/")[1].split("/")[0]
    return url

@st.cache_data(ttl=300)
def read_sheet(spreadsheet_key: str, sheet_name: str) -> pd.DataFrame:
    creds = load_credentials()
    gc    = gspread.authorize(creds)
    ws    = gc.open_by_key(spreadsheet_key).worksheet(sheet_name)
    rows  = ws.get_all_values()
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows[1:], columns=rows[0])

def parse_ngay(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, dayfirst=True, errors="coerce").dt.date

def get_week_num(d: date) -> int:
    """Trả về tuần 1-4 theo chu kỳ, mốc 27/04/2026 = Tuần 1."""
    delta = (d - ANCHOR_DATE).days
    return (delta // 7 % 4) + 1

def dates_in_range(start: date, end: date):
    return [start + timedelta(days=i) for i in range((end-start).days+1)]

def sort_ma(ma: str):
    order = {"S01":0,"S02":1,"S03":2,"I01":3,"A01":4}
    return (order.get(ma[:3], 99), ma)

def group_of(ma: str) -> str:
    return ma[:3] if len(ma) >= 3 else ma

def cell_has_work(codes: list) -> bool:
    return bool(set(codes) - NON_WORK_CODES - {""})


# ═══════════════════════════════════════════════════════════════════
# DATA LOADING
# ═══════════════════════════════════════════════════════════════════
def load_all_data() -> dict:
    try:
        k1  = get_key("input_1_fn")
        k2  = get_key("input_2_fn")
        ko1 = get_key("output_1_fn")
        ko2 = get_key("output_2_fn")
        return {
            "nhan_su"  : read_sheet(k1,  "Trang tính1"),
            "vi_tri"   : read_sheet(k2,  "Trang tính1"),
            "lich_truc": read_sheet(ko1, "Trang tính1"),
            "lich_pk"  : read_sheet(ko1, "Trang tính2"),
            "nghi_phep": read_sheet(ko2, "Trang tính1"),
            "lich_hoc" : read_sheet(ko2, "Trang tính2"),
            "cong_tac" : read_sheet(ko2, "Trang tính3"),
        }
    except Exception as e:
        st.warning(f"⚠️ Dùng dữ liệu mẫu (lỗi kết nối: {e})")
        return _make_sample_data()


def _make_sample_data() -> dict:
    """Dữ liệu demo khớp đúng cấu trúc thực tế."""
    nhan_su = pd.DataFrame([
        ["S01.01","S","1","1","Bùi Đỗ Hiếu"],
        ["S02.01","S","2","1","Vương Tú Như"],
        ["S02.02","S","2","2","Bùi Quang Trung"],
        ["S02.03","S","2","3","Nguyễn Mai An"],
        ["S02.04","S","2","4","Nguyễn Minh Nhật"],
        ["S03.01","S","3","1","Võ Thị Thành"],
        ["S03.02","S","3","2","Tô Mỹ Anh"],
        ["S03.03","S","3","3","Nguyễn Đức Tài"],
        ["S03.04","S","3","4","Đào Thị Hải Yến"],
        ["S03.05","S","3","5","Dương Thành Tá"],
        ["S03.06","S","3","6","Nguyễn Cao Vân"],
        ["S03.07","S","3","7","Lương Nữ Hoài Thương"],
        ["S03.08","S","3","8","Triệu Thị Thanh Tuyền"],
        ["S03.09","S","3","9","Nguyễn Thái Bình Minh"],
        ["S03.10","S","3","10","Trần Tuyết Bình"],
        ["I01.01","I","1","1","Đào Thục Hiền"],
        ["I01.02","I","1","2","Cái Trọng Viễn"],
        ["I01.03","I","1","3","Trương Nguyệt Quế"],
        ["A01.01","A","1","1","Tăng Đạt Phong"],
    ], columns=["A","B","C","D","E"])

    positions = ["BLĐ khoa","PK - S","PK - C","NG","NL","NS - Đêm","MK","C+",
                 "HN","Soi CTC","PK - Phụ 1","PK - Phụ 2","QA","NB","M","S",
                 "VT","RT","BT","SA","TS","KH","PS","NS"]
    rows = []
    idx  = 1
    for _, r in nhan_su.iterrows():
        ma = r["A"]; ten = r["E"]
        for pos in positions:
            can = 0
            if pos in ("PK - S","PK - C","M","S","PS","NB","C+","KH"):
                can = 1
            if pos == "NL" and ma[:3] == "S02":
                can = 1
            if pos == "NS" and ma[:3] in ("S02","S03"):
                can = 1
            if pos == "NG" and ma[:3] in ("S02","S03"):
                can = 1
            if pos == "QA" and ma[:3] == "S03":
                can = 1
            rows.append([f"{ma}.{idx:02d}", ten, pos, str(can)])
            idx += 1
    vi_tri = pd.DataFrame(rows, columns=["A","B","C","D"])

    today = date.today()
    mon   = today - timedelta(days=today.weekday())

    # Lịch trực mẫu: S02.04, S03.09, I01.01 trực Thứ Hai tuần này
    lich_truc = pd.DataFrame([
        ["1","","Nguyễn Minh Nhật","S02.04",mon.strftime("%d/%m/%Y"),"2","1"],
        ["2","","Nguyễn Thái Bình Minh","S03.09",mon.strftime("%d/%m/%Y"),"2","1"],
        ["3","","Đào Thục Hiền","I01.01",mon.strftime("%d/%m/%Y"),"2","1"],
    ], columns=["STT","TIMESTAMP","NHÂN VIÊN","MÃ NHÂN SỰ","NGÀY TRỰC","THỨ","TUẦN THỨ"])

    # Lịch PK mẫu: Phòng khám Tân Bình
    lich_pk = pd.DataFrame([
        ["1","","Vương Tú Như","S02.01",mon.strftime("%d/%m/%Y"),"Phòng khám Tân Bình","S","1"],
        ["2","","Đào Thị Hải Yến","S03.04",mon.strftime("%d/%m/%Y"),"Phòng khám Tân Bình","S","1"],
        ["3","","Nguyễn Minh Nhật","S02.04",mon.strftime("%d/%m/%Y"),"Phòng khám Tân Bình","C","1"],
        ["4","","Lương Nữ Hoài Thương","S03.07",mon.strftime("%d/%m/%Y"),"Phòng khám Tân Bình","C","1"],
    ], columns=["STT","TIMESTAMP","NHÂN VIÊN","MÃ NHÂN VIÊN","NGÀY","LOẠI","BUỔI","TUẦN THỨ"])

    # Nghỉ phép mẫu
    tue = (mon + timedelta(days=1)).strftime("%d/%m/%Y")
    nghi_phep = pd.DataFrame([
        ["1","","Bùi Quang Trung","Đăng ký phép mới",tue,"S","","Đã duyệt"],
        ["2","","Vương Tú Như","Đăng ký phép mới",tue,"C","","Đã duyệt"],
    ], columns=["STT","TIMESTAMP","NHÂN VIÊN","LOẠI YÊU CẦU","NGÀY","BUỔI","LÍ DO","TÌNH TRẠNG DUYỆT"])

    # Lịch học mẫu
    wed = (mon + timedelta(days=2)).strftime("%d/%m/%Y")
    lich_hoc = pd.DataFrame([
        ["1","","Cái Trọng Viễn","I01.02",wed,"S - C",""],
    ], columns=["STT","TIMESTAMP","NHÂN VIÊN","MÃ NHÂN VIÊN","NGÀY","BUỔI","GHI CHÚ"])

    # Công tác mẫu
    sat = (mon + timedelta(days=5)).strftime("%d/%m/%Y")
    cong_tac = pd.DataFrame([
        ["1","","Trương Nguyệt Quế","BT","","09/05/2026","S"],
        ["2","","Lương Nữ Hoài Thương","CT","công tác","09/05/2026","S"],
        ["3","","Đào Thục Hiền","KH","kế hoạch","09/05/2026","C"],
    ], columns=["STT","TIMESTAMP","NHÂN VIÊN","LOẠI (CT/BT)","NỘI DUNG","NGÀY","BUỔI"])

    return dict(nhan_su=nhan_su, vi_tri=vi_tri, lich_truc=lich_truc,
                lich_pk=lich_pk, nghi_phep=nghi_phep,
                lich_hoc=lich_hoc, cong_tac=cong_tac)


# ═══════════════════════════════════════════════════════════════════
# PARSE HELPERS  (map tên NV → mã và ngược lại)
# ═══════════════════════════════════════════════════════════════════
def build_nv_maps(nhan_su: pd.DataFrame):
    """
    Trả về:
      ma_list  : [mã NV đã sắp xếp]
      ten_of   : {mã → họ tên (cột E)}
      ma_of    : {họ tên → mã}  (dùng khi tra từ output dùng tên)
      group_of_ma: {mã → 3 ký tự đầu}
    """
    df = nhan_su.copy()
    df.columns = df.columns.str.strip()
    df["_sort"] = df["A"].apply(sort_ma)
    df = df.sort_values("_sort").reset_index(drop=True)
    ma_list     = df["A"].tolist()
    ten_of      = dict(zip(df["A"], df["E"]))
    ma_of       = dict(zip(df["E"], df["A"]))
    group_of_ma = {ma: ma[:3] for ma in ma_list}
    return ma_list, ten_of, ma_of, group_of_ma


def build_kha_nang(vi_tri: pd.DataFrame, ma_list: list) -> dict:
    """
    Trả về {mã_NV: set(vị trí có thể làm)}.
    input_2 cột A = ID dạng S01.01.01 (mã NV là 6 ký tự đầu: S01.01)
    hoặc cột B = TÊN (dùng để map ngược).
    """
    df = vi_tri.copy()
    df.columns = df.columns.str.strip()
    # Mã NV trong input_2 có thể dài hơn (S01.01.01), cần map lại
    # Chiến lược: lấy 6 ký tự đầu cột A nếu khớp với ma_list
    result: dict = {ma: set() for ma in ma_list}
    for _, r in df.iterrows():
        raw_id = str(r.get("A","")).strip()
        # Thử lấy 6 ký tự đầu (S01.01)
        short  = raw_id[:6] if len(raw_id) >= 6 else raw_id
        # Nếu không khớp thử tra theo tên cột B
        ten    = str(r.get("B","")).strip()
        pos    = str(r.get("C","")).strip()
        can    = str(r.get("D","0")).strip()
        # Tìm mã NV
        target_ma = None
        if short in result:
            target_ma = short
        else:
            # Tìm mã có tên khớp (map ngược qua ten_of)
            for ma in ma_list:
                pass   # sẽ map sau khi build ten_of
            target_ma = None   # để xử lý sau khi có ten_of

        if target_ma and can == "1" and pos:
            result[target_ma].add(pos)
    return result


def build_kha_nang_v2(vi_tri: pd.DataFrame, ten_of: dict) -> dict:
    """
    Phiên bản chính xác: map qua cột B (TÊN) của input_2 → tìm mã NV từ ten_of ngược.
    """
    df = vi_tri.copy()
    df.columns = df.columns.str.strip()
    # Tạo map ngược: tên → mã
    ten_to_ma: dict = {v: k for k, v in ten_of.items()}
    result: dict = {ma: set() for ma in ten_of}

    for _, r in df.iterrows():
        raw_id = str(r.get("A","")).strip()
        ten    = str(r.get("B","")).strip()
        pos    = str(r.get("C","")).strip()
        can    = str(r.get("D","0")).strip()

        # Ưu tiên map theo 6 ký tự đầu ID
        short = raw_id[:6] if len(raw_id) >= 6 else raw_id
        if short in result:
            target = short
        elif ten in ten_to_ma:
            target = ten_to_ma[ten]
        else:
            continue

        if can == "1" and pos:
            result[target].add(pos)
    return result


def expand_buoi(buoi_str: str) -> list:
    """
    Chuyển chuỗi buổi từ dữ liệu thực tế sang list buổi chuẩn.
    VD: "S - C" → ["Sáng","Chiều"], "S" → ["Sáng"]
    """
    s = buoi_str.strip().upper()
    mapping = {
        "S": ["Sáng"], "SÁNG": ["Sáng"],
        "T": ["Trưa"],  "TRƯA": ["Trưa"],
        "C": ["Chiều"], "CHIỀU": ["Chiều"],
        "TO": ["Tối"],  "TỐI": ["Tối"],
        "S - C": ["Sáng","Chiều"],
        "S-C":   ["Sáng","Chiều"],
        "S - C - T": ["Sáng","Chiều","Trưa"],
        "ALL": ["Sáng","Trưa","Chiều","Tối"],
    }
    if s in mapping:
        return mapping[s]
    # Thử split "-"
    parts = [p.strip() for p in s.split("-")]
    result = []
    for p in parts:
        r = mapping.get(p)
        if r:
            result.extend(r)
    return result if result else ["Sáng"]


# ═══════════════════════════════════════════════════════════════════
# SCHEDULE BUILDER
# ═══════════════════════════════════════════════════════════════════
def build_schedule(start: date, end: date, data: dict):
    """
    Xây dựng ma trận lịch làm việc.
    Trả về (matrix, truc_map, ma_list, ten_of, group_of_ma, kha_nang_map)
      matrix   : { ma: { (date, buoi): [codes] } }
      truc_map : { date: [ma] }
    """
    all_dates = dates_in_range(start, end)

    # ── Nhân sự ──────────────────────────────────────────────────────
    ma_list, ten_of, ma_of, group_of_ma = build_nv_maps(data["nhan_su"])
    kha_nang_map = build_kha_nang_v2(data["vi_tri"], ten_of)

    # Ma trận rỗng
    matrix: dict = {ma: {(d, b): [] for d in all_dates for b in BUOI_COLS}
                    for ma in ma_list}

    ten_to_ma = {v: k for k, v in ten_of.items()}

    def find_ma(ten_str: str, ma_str: str = "") -> str | None:
        """Tìm mã NV từ tên hoặc mã."""
        ma_str = ma_str.strip()
        ten_str = ten_str.strip()
        if ma_str in matrix:
            return ma_str
        # Thử tra tên
        if ten_str in ten_to_ma:
            return ten_to_ma[ten_str]
        # Tìm mờ theo tên
        for ma, ten in ten_of.items():
            if ten_str and (ten_str in ten or ten in ten_str):
                return ma
        return None

    # ════════════════════════════════════════════════════════════════
    # ƯU TIÊN 1a: NGHỈ PHÉP
    # output_2 / Trang tính1:  cột C=NHÂN VIÊN, D=LOẠI YÊU CẦU,
    #                           E=NGÀY, F=BUỔI, H=TÌNH TRẠNG DUYỆT
    # ════════════════════════════════════════════════════════════════
    np_df = data.get("nghi_phep", pd.DataFrame())
    if not np_df.empty:
        np_df = np_df.copy()
        np_df.columns = np_df.columns.str.strip()
        # Tìm cột đúng theo header thực tế
        col_ten  = _find_col(np_df, ["NHÂN VIÊN","C"])
        col_loai = _find_col(np_df, ["LOẠI YÊU CẦU","D"])
        col_ngay = _find_col(np_df, ["NGÀY","E"])
        col_buoi = _find_col(np_df, ["BUỔI","F"])
        col_tt   = _find_col(np_df, ["TÌNH TRẠNG DUYỆT","H"])

        approved  = np_df[
            (np_df.get(col_loai, pd.Series(dtype=str)).astype(str).str.strip()
             == "Đăng ký phép mới") &
            (np_df.get(col_tt, pd.Series(dtype=str)).astype(str).str.strip()
             == "Đã duyệt")
        ].copy()
        cancel_ids = set(
            np_df[
                (np_df.get(col_loai, pd.Series(dtype=str)).astype(str).str.strip()
                 == "Hủy phép đã đăng ký") &
                (np_df.get(col_tt, pd.Series(dtype=str)).astype(str).str.strip()
                 == "Đã duyệt")
            ].index.tolist()
        )
        # Lọc theo mã STT phép (giả sử cột A là STT)
        approved = approved.drop(index=[i for i in cancel_ids if i in approved.index],
                                 errors="ignore")
        approved[col_ngay] = parse_ngay(approved[col_ngay])

        for _, r in approved.iterrows():
            ma  = find_ma(str(r.get(col_ten,"")))
            ngay = r.get(col_ngay)
            if ma is None or ngay not in all_dates:
                continue
            for b in expand_buoi(str(r.get(col_buoi,""))):
                if (ngay, b) in matrix[ma] and "P" not in matrix[ma][(ngay, b)]:
                    matrix[ma][(ngay, b)].append("P")

    # ════════════════════════════════════════════════════════════════
    # ƯU TIÊN 1b: LỊCH HỌC
    # output_2 / Trang tính2: cột C=NHÂN VIÊN, D=MÃ NV, E=NGÀY, F=BUỔI
    # ════════════════════════════════════════════════════════════════
    hoc_df = data.get("lich_hoc", pd.DataFrame())
    if not hoc_df.empty:
        hoc_df = hoc_df.copy()
        hoc_df.columns = hoc_df.columns.str.strip()
        col_ten  = _find_col(hoc_df, ["NHÂN VIÊN","C"])
        col_ma   = _find_col(hoc_df, ["MÃ NHÂN VIÊN","D"])
        col_ngay = _find_col(hoc_df, ["NGÀY","E"])
        col_buoi = _find_col(hoc_df, ["BUỔI","F"])
        hoc_df[col_ngay] = parse_ngay(hoc_df[col_ngay])

        for _, r in hoc_df.iterrows():
            ma  = find_ma(str(r.get(col_ten,"")), str(r.get(col_ma,"")))
            ngay = r.get(col_ngay)
            if ma is None or ngay not in all_dates:
                continue
            for b in expand_buoi(str(r.get(col_buoi,""))):
                if (ngay, b) in matrix[ma] and "H" not in matrix[ma][(ngay, b)]:
                    matrix[ma][(ngay, b)].append("H")

    # ════════════════════════════════════════════════════════════════
    # ƯU TIÊN 1c: CÔNG TÁC / KH / BT
    # output_2 / Trang tính3: cột C=NHÂN VIÊN, D=LOẠI(CT/KH/BT),
    #                          F=NGÀY, G=BUỔI
    # ════════════════════════════════════════════════════════════════
    ct_df = data.get("cong_tac", pd.DataFrame())
    if not ct_df.empty:
        ct_df = ct_df.copy()
        ct_df.columns = ct_df.columns.str.strip()
        col_ten  = _find_col(ct_df, ["NHÂN VIÊN","C"])
        col_loai = _find_col(ct_df, ["LOẠI (CT/BT)","D"])
        col_ngay = _find_col(ct_df, ["NGÀY","F"])
        col_buoi = _find_col(ct_df, ["BUỔI","G"])
        ct_df[col_ngay] = parse_ngay(ct_df[col_ngay])

        for _, r in ct_df.iterrows():
            ma   = find_ma(str(r.get(col_ten,"")))
            ngay = r.get(col_ngay)
            loai = str(r.get(col_loai,"")).strip().upper()
            if loai not in ("CT","KH","BT"):
                continue
            if ma is None or ngay not in all_dates:
                continue
            for b in expand_buoi(str(r.get(col_buoi,""))):
                if (ngay, b) in matrix[ma] and loai not in matrix[ma][(ngay, b)]:
                    matrix[ma][(ngay, b)].append(loai)

    # ════════════════════════════════════════════════════════════════
    # ƯU TIÊN 2: LỊCH TRỰC (truc_map)
    # output_1 / Trang tính1: cột C=NHÂN VIÊN, D=MÃ NHÂN SỰ,
    #                          E=NGÀY TRỰC, F=THỨ, G=TUẦN THỨ
    # Chủ nhật chỉ có tên trực, không xếp việc
    # ════════════════════════════════════════════════════════════════
    truc_map: dict = {}
    lt_df = data.get("lich_truc", pd.DataFrame())
    if not lt_df.empty:
        lt_df = lt_df.copy()
        lt_df.columns = lt_df.columns.str.strip()
        col_ten  = _find_col(lt_df, ["NHÂN VIÊN","C"])
        col_ma   = _find_col(lt_df, ["MÃ NHÂN SỰ","D"])
        col_ngay = _find_col(lt_df, ["NGÀY TRỰC","E"])
        lt_df[col_ngay] = parse_ngay(lt_df[col_ngay])
        for _, r in lt_df.iterrows():
            ma   = find_ma(str(r.get(col_ten,"")), str(r.get(col_ma,"")))
            ngay = r.get(col_ngay)
            if ma is None or ngay not in all_dates:
                continue
            truc_map.setdefault(ngay, [])
            if ma not in truc_map[ngay]:
                truc_map[ngay].append(ma)
        # Sắp xếp tua trực theo thứ tự mã
        for ngay in truc_map:
            truc_map[ngay] = sorted(truc_map[ngay], key=sort_ma)

    # ════════════════════════════════════════════════════════════════
    # ƯU TIÊN 3: VT & RT
    # ════════════════════════════════════════════════════════════════
    for ngay, truc_list in truc_map.items():
        next_d = ngay + timedelta(days=1)
        for ma in truc_list:
            if ma not in matrix:
                continue
            # Chiều ngày trực → VT
            if (ngay, "Chiều") in matrix[ma]:
                if "VT" not in matrix[ma][(ngay, "Chiều")]:
                    matrix[ma][(ngay, "Chiều")].append("VT")
            # RT
            if next_d in all_dates:
                if ma[:3] == "S02" and "NL" in kha_nang_map.get(ma, set()):
                    # S02 & có NL → RT Sáng ngày sau
                    k = (next_d, "Sáng")
                    if k in matrix[ma] and "RT" not in matrix[ma][k]:
                        matrix[ma][k].append("RT")
                else:
                    # Còn lại → RT Chiều ngày sau
                    k = (next_d, "Chiều")
                    if k in matrix[ma] and "RT" not in matrix[ma][k]:
                        matrix[ma][k].append("RT")

    # ════════════════════════════════════════════════════════════════
    # ƯU TIÊN 4: LỊCH PHÒNG KHÁM
    # output_1 / Trang tính2: cột C=NHÂN VIÊN, D=MÃ NV,
    #                          E=NGÀY, F=LOẠI, G=BUỔI
    # LOẠI: "Phòng khám Tân Bình" → PK-S(G=S) / PK-C(G=C)
    #        có "Ngọc Lan"         → NL
    #        có "Quốc Ánh"         → QA
    # ════════════════════════════════════════════════════════════════
    pk_df = data.get("lich_pk", pd.DataFrame())
    if not pk_df.empty:
        pk_df = pk_df.copy()
        pk_df.columns = pk_df.columns.str.strip()
        col_ten  = _find_col(pk_df, ["NHÂN VIÊN","C"])
        col_ma   = _find_col(pk_df, ["MÃ NHÂN VIÊN","D"])
        col_ngay = _find_col(pk_df, ["NGÀY","E"])
        col_loai = _find_col(pk_df, ["LOẠI","F"])
        col_buoi = _find_col(pk_df, ["BUỔI","G"])
        pk_df[col_ngay] = parse_ngay(pk_df[col_ngay])

        for _, r in pk_df.iterrows():
            ma   = find_ma(str(r.get(col_ten,"")), str(r.get(col_ma,"")))
            ngay = r.get(col_ngay)
            loai = str(r.get(col_loai,"")).strip()
            buoi_raw = str(r.get(col_buoi,"")).strip().upper()
            if ma is None or ngay not in all_dates:
                continue
            if ngay.weekday() == 6:   # Chủ nhật không xếp
                continue

            # Xác định mã vị trí
            if "Ngọc Lan" in loai:
                code = "NL"
                # NL: Sáng ngày đó (xây dựng đầy đủ theo quy tắc 7)
                _apply_nl_schedule(matrix, ma, ngay, all_dates)
                continue
            elif "Quốc Ánh" in loai:
                code = "QA"
            elif "Tân Bình" in loai:
                code = "PK - S" if buoi_raw == "S" else "PK - C"
            else:
                continue

            for b in expand_buoi(buoi_raw if buoi_raw else "S"):
                if (ngay, b) in matrix[ma] and code not in matrix[ma][(ngay, b)]:
                    matrix[ma][(ngay, b)].append(code)

    # ════════════════════════════════════════════════════════════════
    # ƯU TIÊN 5a: NGOÀI GIỜ (NG)
    # Mỗi ngày 1 người (trừ Thứ 5 & CN), luân phiên theo khả năng NG
    # ════════════════════════════════════════════════════════════════
    ng_pool = [ma for ma in ma_list if "NG" in kha_nang_map.get(ma, set())]
    ng_rot  = 0
    for d in all_dates:
        if d.weekday() in (3, 6):   # Thứ Năm = 3, CN = 6
            continue
        for i in range(len(ng_pool)):
            ma = ng_pool[(ng_rot + i) % len(ng_pool)]
            # Tìm buổi còn trống
            for b in BUOI_COLS:
                if (d, b) in matrix[ma] and not matrix[ma][(d, b)]:
                    matrix[ma][(d, b)].append("NG")
                    ng_rot = (ng_rot + i + 1) % max(len(ng_pool),1)
                    break
            else:
                continue
            break

    # ════════════════════════════════════════════════════════════════
    # ƯU TIÊN 5b: NỘI SOI (NS) – buổi Tối
    # 1 người/ngày, luân phiên, không trùng VT/RT
    # ════════════════════════════════════════════════════════════════
    ns_pool = [ma for ma in ma_list if "NS" in kha_nang_map.get(ma, set())]
    ns_rot  = 0
    for d in all_dates:
        if d.weekday() == 6:
            continue
        for i in range(len(ns_pool)):
            ma   = ns_pool[(ns_rot + i) % max(len(ns_pool),1)]
            cell = matrix[ma].get((d, "Tối"), [])
            if "VT" not in cell and "RT" not in cell and not cell:
                matrix[ma][(d, "Tối")].append("NS")
                ns_rot = (ns_rot + i + 1) % max(len(ns_pool),1)
                break

    # ════════════════════════════════════════════════════════════════
    # ƯU TIÊN 5c: NHẬN BỆNH (NB)
    # 2 người/ngày, ít nhất 1 mã S03, luân phiên
    # ════════════════════════════════════════════════════════════════
    nb_pool   = [ma for ma in ma_list if "NB" in kha_nang_map.get(ma, set())]
    nb_s03    = [ma for ma in nb_pool if ma[:3] == "S03"]
    nb_other  = [ma for ma in nb_pool if ma[:3] != "S03"]
    nb_s03_r  = 0; nb_oth_r = 0
    for d in all_dates:
        if d.weekday() == 6:
            continue
        assigned = []
        # Chọn 1 S03
        for i in range(len(nb_s03)):
            ma = nb_s03[(nb_s03_r + i) % max(len(nb_s03),1)]
            if ma not in assigned:
                assigned.append(ma); nb_s03_r += i+1; break
        # Chọn 1 người khác
        for i in range(len(nb_other)):
            ma = nb_other[(nb_oth_r + i) % max(len(nb_other),1)]
            if ma not in assigned:
                assigned.append(ma); nb_oth_r += i+1; break
        for ma in assigned[:2]:
            for b in BUOI_COLS:
                if (d, b) in matrix[ma] and not matrix[ma][(d, b)]:
                    matrix[ma][(d, b)].append("NB"); break

    # ════════════════════════════════════════════════════════════════
    # ƯU TIÊN 5d: C+
    # Slots: Chiều T3(1), Sáng T4(2), Chiều T5(3), Sáng+Chiều T7(5)
    # Đi kèm 1 vị trí khác (M/PS/NS)
    # ════════════════════════════════════════════════════════════════
    cp_pool  = [ma for ma in ma_list if "C+" in kha_nang_map.get(ma, set())]
    cp_slots = {1: ["Chiều"], 2: ["Sáng"], 3: ["Chiều"], 5: ["Sáng","Chiều"]}
    cp_rot   = 0
    for d in all_dates:
        wd = d.weekday()
        if wd not in cp_slots:
            continue
        for b in cp_slots[wd]:
            for i in range(len(cp_pool)):
                ma   = cp_pool[(cp_rot + i) % max(len(cp_pool),1)]
                cell = matrix[ma].get((d, b), [])
                if "C+" not in cell:
                    matrix[ma][(d, b)].append("C+")
                    cp_rot += i+1; break

    # ════════════════════════════════════════════════════════════════
    # ƯU TIÊN 6: COMBO PS – S – M
    # 4 người/buổi combo (≥1 S02), nếu không đủ thì lẻ PS(2),M(4),S(4)
    # ════════════════════════════════════════════════════════════════
    combo_pool  = [ma for ma in ma_list
                   if {"PS","S","M"}.issubset(kha_nang_map.get(ma, set()))]
    c_s02 = [ma for ma in combo_pool if ma[:3] == "S02"]
    c_oth = [ma for ma in combo_pool if ma[:3] not in ("S01","S02")]
    cs02_r = 0; coth_r = 0

    for d in all_dates:
        if d.weekday() == 6:
            continue
        for b in ["Sáng", "Chiều"]:
            free      = [ma for ma in combo_pool
                         if not matrix[ma].get((d,b),[])]
            free_s02  = [ma for ma in free if ma[:3] == "S02"]
            free_oth  = [ma for ma in free if ma[:3] not in ("S01","S02")]

            if len(free) >= 4:
                chosen = []
                # Đảm bảo ≥1 S02
                if free_s02:
                    pick = free_s02[cs02_r % len(free_s02)]; cs02_r += 1
                    chosen.append(pick)
                else:
                    # Dùng S01 thay thế
                    s01_free = [ma for ma in ma_list
                                if ma[:3]=="S01" and not matrix[ma].get((d,b),[])]
                    if s01_free:
                        chosen.append(s01_free[0])
                # Thêm đủ 4
                for i in range(len(free_oth)*2):
                    if len(chosen) >= 4 or not free_oth:
                        break
                    ma = free_oth[coth_r % len(free_oth)]; coth_r += 1
                    if ma not in chosen:
                        chosen.append(ma)
                for ma in chosen[:4]:
                    if (d, b) in matrix[ma]:
                        matrix[ma][(d, b)] = ["PS","S","M"]
            else:
                # Xếp lẻ
                for pos, need in [("PS",2),("M",4),("S",4)]:
                    p_free = [ma for ma in combo_pool
                              if pos in kha_nang_map.get(ma,set())
                              and not matrix[ma].get((d,b),[])]
                    for j, ma in enumerate(p_free[:need]):
                        matrix[ma][(d, b)].append(pos)

    return matrix, truc_map, ma_list, ten_of, group_of_ma, kha_nang_map


def _apply_nl_schedule(matrix, ma, ngay_truc, all_dates):
    """
    Quy tắc 7 – Ngọc Lan (NL) cho S02 có khả năng NL:
    - Sáng ngày trực: NL
    - Chiều + Tối ngày kế: NL
    - Sáng ngày kế: RT (đã có từ quy tắc VT/RT)
    - Bù NL: Sáng ngày sau RT, Chiều cùng ngày: Bù NL
    - Thứ Tư → NL thêm Sáng T7 / Thứ Bảy → NL thêm Sáng T4
    """
    next_d  = ngay_truc + timedelta(days=1)
    bu_d    = ngay_truc + timedelta(days=2)

    if (ngay_truc, "Sáng") in matrix[ma]:
        if "NL" not in matrix[ma][(ngay_truc, "Sáng")]:
            matrix[ma][(ngay_truc, "Sáng")].append("NL")
    if next_d in [k[0] for k in matrix[ma]]:
        for b in ("Chiều","Tối"):
            if (next_d, b) in matrix[ma] and "NL" not in matrix[ma][(next_d, b)]:
                matrix[ma][(next_d, b)].append("NL")
    if bu_d in [k[0] for k in matrix[ma]]:
        if (bu_d, "Sáng") in matrix[ma] and "NL" not in matrix[ma][(bu_d, "Sáng")]:
            matrix[ma][(bu_d, "Sáng")].append("NL")
        if (bu_d, "Chiều") in matrix[ma] and "Bù NL" not in matrix[ma][(bu_d, "Chiều")]:
            matrix[ma][(bu_d, "Chiều")].append("Bù NL")
    # Thứ Tư ↔ Thứ Bảy
    wd         = ngay_truc.weekday()
    week_start = ngay_truc - timedelta(days=wd)
    extra = None
    if wd == 2:   extra = week_start + timedelta(days=5)
    elif wd == 5: extra = week_start + timedelta(days=2)
    if extra:
        if (extra, "Sáng") in matrix[ma] and "NL" not in matrix[ma][(extra, "Sáng")]:
            matrix[ma][(extra, "Sáng")].append("NL")


def _find_col(df: pd.DataFrame, candidates: list) -> str:
    """Tìm cột đầu tiên khớp trong candidates, fallback về candidates[-1]."""
    for c in candidates:
        if c in df.columns:
            return c
    return candidates[-1]


# ═══════════════════════════════════════════════════════════════════
# RENDER TABLE
# ═══════════════════════════════════════════════════════════════════
_TABLE_CSS = """
<style>
.sch-wrap{overflow:auto;border-radius:10px;
  box-shadow:0 4px 20px rgba(0,0,0,.14);
  border:1px solid #c0cfe0;max-height:82vh;}
.sch-wrap.fullscreen{max-height:95vh !important;width:100% !important;}
.sch-tbl{border-collapse:collapse;font-family:'Segoe UI',sans-serif;
  font-size:11px;width:max-content;min-width:100%;}

/* HEADER */
.sch-tbl thead th{
  position:sticky;top:0;z-index:14;
  background:#1e3a5f;color:#fff;
  padding:5px 6px;border:1px solid #2d5089;
  white-space:nowrap;text-align:center;font-weight:700;}
.sch-tbl thead tr:nth-child(2) th{top:33px;z-index:13;font-size:10px;font-weight:600;}

/* CỘT HỌ TÊN */
.sch-tbl th.nc,.sch-tbl td.nc{
  position:sticky;left:0;z-index:12;
  min-width:220px;max-width:280px;
  background:#f8fafc;border-right:2px solid #90aacb;
  text-align:left;padding-left:8px;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-weight:600;}
.sch-tbl thead th.nc{z-index:20;background:#0f2540;}

/* Ô dữ liệu */
.sch-tbl td{border:1px solid #dde3ec;padding:2px 3px;
  text-align:center;min-width:54px;max-width:80px;
  font-size:10px;vertical-align:middle;
  white-space:pre-wrap;word-break:break-word;}

/* Dòng đặc biệt */
.sch-tbl tr.cnt td{background:#e8f0fe!important;font-weight:700;color:#1a56db;}
.sch-tbl tr.cnt td.nc{background:#d0e0ff!important;font-style:italic;color:#1e40af;font-size:10px;}
.sch-tbl tr.dty td{background:#fffbeb!important;color:#92400e;font-weight:700;font-size:10px;}
.sch-tbl tr.dty td.nc{background:#fef3c7!important;}

/* Trạng thái ô */
.cf{font-weight:700;color:#1e3a5f;}
.ce{color:#d0d5dd;font-size:9px;}
.snd{background:#f5f5f5!important;color:#c8cdd5!important;}
</style>
"""

def render_table(matrix, truc_map, ma_list, ten_of, group_of_ma, dates,
                 kha_nang_map, is_editing, is_finalized):
    st.markdown(_TABLE_CSS, unsafe_allow_html=True)

    # ── Build header ────────────────────────────────────────────────
    d1 = ""; d2 = ""
    for d in dates:
        thu = THU_VI.get(d.weekday(), "")
        ns  = d.strftime("%d/%m")
        d1 += (f'<th colspan="4" style="background:#1e3a5f;'
               f'border-bottom:2px solid #60a5fa">'
               f'{thu}<br><small style="font-weight:400">{ns}</small></th>')
        for b in BUOI_COLS:
            bg  = BUOI_STYLE[b]["bg"]
            brd = BUOI_STYLE[b]["border"]
            d2 += (f'<th style="background:{bg};color:#374151;'
                   f'border-bottom:2px solid {brd};font-size:10px">'
                   f'{b[0]}</th>')

    # ── Dòng đếm ────────────────────────────────────────────────────
    cnt_cells = ""
    for d in dates:
        for b in BUOI_COLS:
            cnt = sum(1 for ma in ma_list
                      if cell_has_work(matrix.get(ma,{}).get((d,b),[])))
            bg  = BUOI_STYLE[b]["bg"]
            cnt_cells += (f'<td style="background:{bg}">'
                          f'{"<b>"+str(cnt)+"</b>" if cnt else ""}</td>')

    # ── Các dòng NV ─────────────────────────────────────────────────
    rows_html = ""
    for ma in ma_list:
        grp    = group_of_ma.get(ma,"")
        row_bg = GROUP_COLOR.get(grp, DEFAULT_GROUP_COLOR)
        ten    = ten_of.get(ma, ma)
        row    = (f'<tr style="background:{row_bg}">'
                  f'<td class="nc" style="background:{row_bg}" title="{ten}">'
                  f'{ten}</td>')
        for d in dates:
            # Chủ Nhật: không xếp lịch, chỉ hiện "—"
            if d.weekday() == 6:
                for _ in BUOI_COLS:
                    row += '<td class="snd">—</td>'
                continue
            for b in BUOI_COLS:
                codes   = matrix.get(ma,{}).get((d,b),[])
                display = " - ".join(codes) if codes else ""
                cls     = "cf" if display else "ce"
                txt     = display if display else "·"
                bg      = BUOI_STYLE[b]["bg"]
                row    += (f'<td style="background:{bg}">'
                           f'<span class="{cls}">{txt}</span></td>')
        row += "</tr>"
        rows_html += row

    # ── Dòng tua trực ────────────────────────────────────────────────
    duty_cells = ""
    for d in dates:
        tl  = truc_map.get(d,[])
        val = " - ".join([ten_of.get(m,m) for m in tl])
        duty_cells += f'<td colspan="4" style="text-align:center;font-size:9px;padding:3px;">{val}</td>'

    # ── Kiểm tra chế độ xem toàn màn hình ─────────────────────────────
    fullscreen_class = " fullscreen" if st.session_state.get("table_fullscreen", False) else ""
    
    html = f"""
    <div class="sch-wrap{fullscreen_class}" id="sch-table-wrap">
    <table class="sch-tbl">
    <thead>
      <tr><th class="nc" rowspan="2">Họ và Tên</th>{d1}</tr>
      <tr>{d2}</tr>
    </thead>
    <tbody>
      <tr class="cnt"><td class="nc">Số NV có việc</td>{cnt_cells}</tr>
      {rows_html}
      <tr class="dty"><td class="nc">Tua trực</td>{duty_cells}</tr>
    </tbody>
    </table>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)
    
    # ── Nút mở rộng toàn màn hình ────────────────────────────────────
    col1, col2 = st.columns([1, 9])
    with col1:
        btn_label = "📱 Bình thường" if st.session_state.get("table_fullscreen", False) else "🖥️ Toàn màn hình"
        if st.button(btn_label, help="Chuyển đổi chế độ xem", use_container_width=True):
            st.session_state["table_fullscreen"] = not st.session_state.get("table_fullscreen", False)
            st.rerun()

    # ── Chỉnh sửa inline ─────────────────────────────────────────────
    if is_editing and not is_finalized:
        st.markdown("---")
        st.markdown("**✏️ Chỉnh sửa ô lịch**")
        st.caption("Chọn Nhân viên → Ngày → Buổi → cập nhật vị trị. "
                   "Chỉ hiển thị vị trí NV đó có khả năng thực hiện (Khả năng = 1).")

        workdays  = [d for d in dates if d.weekday() != 6]
        day_lbls  = [THU_VI[d.weekday()] + " " + d.strftime("%d/%m") for d in workdays]
        nv_lbls   = [ten_of.get(ma, ma) for ma in ma_list]

        cc1, cc2, cc3, cc4 = st.columns([2, 2, 1.2, 1.2])
        with cc1:
            nv_idx = st.selectbox("Nhân viên", range(len(ma_list)),
                                  format_func=lambda i: nv_lbls[i], key="es_nv")
        with cc2:
            d_idx  = st.selectbox("Ngày", range(len(workdays)),
                                  format_func=lambda i: day_lbls[i], key="es_day")
        with cc3:
            b_sel  = st.selectbox("Buổi", BUOI_COLS, key="es_buoi")

        sel_ma   = ma_list[nv_idx]
        sel_date = workdays[d_idx]
        current  = matrix[sel_ma].get((sel_date, b_sel), [])
        # Chỉ hiển thị vị trí mà NV có khả năng làm (Khả năng = 1)
        eligible = sorted(kha_nang_map.get(sel_ma, set()))

        st.markdown(f"**Hiện tại:** `{' - '.join(current) if current else '( trống )'}`")

        new_vals = st.multiselect(
            "Chọn vị trí (chỉ hiển thị vị trị NV có khả năng):",
            options=eligible,
            default=[c for c in current if c in eligible],
            key="es_multi"
        )

        ua, ub = st.columns(2)
        with ua:
            if st.button("💾 Cập nhật ô", type="primary", use_container_width=True):
                matrix[sel_ma][(sel_date, b_sel)] = new_vals
                st.session_state["matrix"] = matrix
                st.toast(f"✅ {nv_lbls[nv_idx]} – {day_lbls[d_idx]} – {b_sel}")
                st.rerun()
        with ub:
            if st.button("🗑️ Xóa ô", use_container_width=True):
                matrix[sel_ma][(sel_date, b_sel)] = []
                st.session_state["matrix"] = matrix
                st.toast("🗑️ Đã xóa ô")
                st.rerun()


# ═══════════════════════════════════════════════════════════════════
# UPLOAD TO GOOGLE SHEETS
# ═══════════════════════════════════════════════════════════════════
def save_to_sheets(matrix, ma_list, ten_of, dates, truc_map, week_num, sd, ed):
    """
    Lưu ma trận lịch lên Google Sheets.
    - Cùng khoảng thời gian: upload lên cùng 1 trang tính (replace nếu đã tồn tại)
    - Khác khoảng thời gian: upload lên trang tính khác
    """
    try:
        creds = load_credentials()
        gc    = gspread.authorize(creds)
        key   = get_key("output_fn")
        
        if not key:
            return False, "Không tìm thấy khóa output_fn trong secrets"
        
        sh    = gc.open_by_key(key)
        tab   = (f"Tuần {week_num} "
                 f"({sd.strftime('%d/%m')}-{ed.strftime('%d/%m/%Y')})")
        
        # Kiểm tra xem trang tính đã tồn tại chưa
        existing = [ws.title for ws in sh.worksheets()]
        if tab in existing:
            ws = sh.worksheet(tab)
            ws.clear()
        else:
            # Tạo trang tính mới với kích thước phù hợp
            num_rows = len(ma_list) + 3  # +2 cho header + 1 cho dòng trực
            num_cols = 1 + (len(dates) * 4)  # 1 cột tên + 4 buổi mỗi ngày
            ws = sh.add_worksheet(title=tab, rows=max(num_rows + 10, 100), cols=max(num_cols + 5, 50))
        
        # Xây dựng dữ liệu
        # Header dòng 1: Ngày
        h1 = ["Họ và Tên"]
        for d in dates:
            day_label = f"{THU_VI[d.weekday()]} {d.strftime('%d/%m')}"
            h1.append(day_label)
            h1.extend(["", "", ""])  # 3 cột trống cho buổi tiếp theo
        
        # Header dòng 2: Buổi
        h2 = [""]
        for d in dates:
            h2.extend(BUOI_COLS)
        
        data_rows = [h1, h2]
        
        # Dòng dữ liệu nhân viên
        for ma in ma_list:
            row = [ten_of.get(ma, ma)]
            for d in dates:
                for b in BUOI_COLS:
                    codes = matrix.get(ma, {}).get((d, b), [])
                    row.append(" - ".join(codes) if codes else "")
            data_rows.append(row)
        
        # Dòng tua trực
        tr = ["Tua trực"]
        for d in dates:
            tl = truc_map.get(d, [])
            duty_names = " - ".join([ten_of.get(m, m) for m in tl])
            tr.append(duty_names)
            tr.extend(["", "", ""])  # 3 cột trống
        data_rows.append(tr)
        
        # Update dữ liệu lên worksheet
        # Tính toán số cột tối đa từ dữ liệu
        max_cols = max(len(row) for row in data_rows)
        
        # Sử dụng batch_update để ghi dữ liệu
        # Chuyển đổi dữ liệu sang định dạng cho update
        cell_list = []
        for row_idx, row in enumerate(data_rows, start=1):
            for col_idx, value in enumerate(row, start=1):
                cell_list.append(gspread.Cell(row_idx, col_idx, value))
        
        if cell_list:
            ws.update_cells(cell_list, value_input_option='RAW')
        
        return True, tab
    except Exception as e:
        import traceback
        error_msg = f"{str(e)}"
        # Log traceback để debug
        st.write(f"Traceback: {traceback.format_exc()}")
        return False, error_msg


# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════
css_path = pathlib.Path("asset/style.css")
load_css(css_path)

try:
    img = get_img_as_base64("pages/img/logo.png")
    st.markdown(f"""
    <div class="fixed-header">
      <div class="header-content">
        <img src="data:image/png;base64,{img}" alt="logo">
        <div class="header-text">
          <h1>BỆNH VIỆN ĐA KHOA MỸ ĐỨC
            <span style="vertical-align:super;font-size:.6em">&#174;</span>
          </h1>
        </div>
      </div>
      <div class="header-subtext"><p>XẾP LỊCH LÀM VIỆC</p></div>
    </div>
    <div class="header-underline"></div>
    """, unsafe_allow_html=True)
except Exception:
    st.title("BỆNH VIỆN ĐA KHOA MỸ ĐỨC – XẾP LỊCH LÀM VIỆC")

nhan_vien = st.session_state.get("username", "Không xác định")
st.html(f'<p class="demuc"><i>Bác sĩ đang thực hiện: {nhan_vien}</i></p>')

# ── Session state defaults ──────────────────────────────────────────
_DEF = dict(
    schedule_built=False, matrix=None, truc_map=None,
    ma_list=None, ten_of=None, group_of_ma=None, kha_nang_map=None,
    dates=None, week_num=None, start_date=None, end_date=None,
    is_editing=False, is_finalized=False,
    edit_row_idx=None, view_df=None, confirm_delete_idx=None,
    table_fullscreen=False,
)
for k, v in _DEF.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ════════════════════════════════════════════════════════════════════
# UI SECTION 1 – Chọn khoảng thời gian
# ════════════════════════════════════════════════════════════════════
st.markdown("---")
st.markdown("### 📅 Chọn khoảng thời gian xếp lịch")

today  = date.today()
def_s  = today - timedelta(days=today.weekday())   # Đầu tuần hiện tại
def_e  = def_s + timedelta(days=6)

c1, c2 = st.columns(2)
with c1:
    start_input = st.date_input("Từ ngày", value=def_s,
                                format="DD/MM/YYYY", key="inp_start")
with c2:
    end_input = st.date_input("Đến ngày", value=def_e,
                              format="DD/MM/YYYY", key="inp_end")

if start_input and end_input:
    if end_input < start_input:
        st.error("⚠️ Ngày kết thúc phải lớn hơn ngày bắt đầu.")
        st.stop()

    wn = get_week_num(start_input)
    st.info(
        f"📌 Khoảng **{start_input.strftime('%d/%m/%Y')} — "
        f"{end_input.strftime('%d/%m/%Y')}** thuộc "
        f"**Tuần thứ {wn}** (chu kỳ 4 tuần · mốc 27/04/2026 = Tuần 1)"
    )

    # ── Nút bắt đầu ────────────────────────────────────────────────
    if st.button("🗓️ Bắt đầu xếp lịch", type="primary"):
        with st.spinner("Đang tải dữ liệu và xây dựng lịch tự động..."):
            raw = load_all_data()
            result = build_schedule(start_input, end_input, raw)
            matrix, truc_map, ma_list, ten_of, group_of_ma, kha_nang_map = result
            st.session_state.update(
                schedule_built=True,
                matrix=matrix, truc_map=truc_map,
                ma_list=ma_list, ten_of=ten_of,
                group_of_ma=group_of_ma, kha_nang_map=kha_nang_map,
                dates=dates_in_range(start_input, end_input),
                week_num=wn, start_date=start_input, end_date=end_input,
                is_editing=False, is_finalized=False,
            )
        st.success("✅ Lịch đã được xây dựng!")
        st.rerun()

# ════════════════════════════════════════════════════════════════════
# UI SECTION 2 – Hiển thị bảng
# ════════════════════════════════════════════════════════════════════
if not st.session_state.get("schedule_built"):
    st.stop()

matrix       = st.session_state["matrix"]
truc_map     = st.session_state["truc_map"]
ma_list      = st.session_state["ma_list"]
ten_of       = st.session_state["ten_of"]
group_of_ma  = st.session_state["group_of_ma"]
kha_nang_map = st.session_state["kha_nang_map"]
dates_range  = st.session_state["dates"]
wn_s         = st.session_state["week_num"]
sd           = st.session_state["start_date"]
ed           = st.session_state["end_date"]
is_editing   = st.session_state["is_editing"]
is_finalized = st.session_state["is_finalized"]

st.markdown("---")
st.markdown(
    f"### 📋 Tuần thứ {wn_s} &nbsp;·&nbsp; "
    f"{sd.strftime('%d/%m/%Y')} — {ed.strftime('%d/%m/%Y')}"
)

# ── Thanh hành động ────────────────────────────────────────────────
a1, a2, a3, a4 = st.columns([1.4,1.4,1.4,1.4])
with a1:
    if not is_finalized:
        lbl_edit = "🔒 Đang chỉnh sửa…" if is_editing else "✏️ Chỉnh sửa"
        if st.button(lbl_edit, use_container_width=True):
            st.session_state["is_editing"] = not is_editing
            st.rerun()
with a2:
    if not is_finalized:
        if st.button("✅ Chốt danh sách", type="primary", use_container_width=True):
            st.session_state.update(is_editing=False, is_finalized=True)
            st.rerun()
    else:
        st.success("🔒 Đã chốt")
with a3:
    if is_finalized:
        if st.button("💾 Lưu danh sách", type="primary", use_container_width=True):
            with st.spinner("Đang upload lên Google Sheets…"):
                ok, result_msg = save_to_sheets(
                    matrix, ma_list, ten_of, dates_range,
                    truc_map, wn_s, sd, ed
                )
            if ok:
                st.success(f"✅ Đã lưu → tab **{result_msg}**")
            else:
                st.error(f"❌ Lỗi: {result_msg}")
with a4:
    if st.button("🔄 Xây dựng lại", use_container_width=True,
                 help="Xây dựng lại từ đầu, mọi chỉnh sửa thủ công sẽ mất"):
        st.session_state["schedule_built"] = False
        st.rerun()

# ── Bảng xếp lịch ──────────────────────────────────────────────────
st.markdown("#### 📊 Bảng xếp lịch làm việc")
render_table(
    matrix=matrix, truc_map=truc_map,
    ma_list=ma_list, ten_of=ten_of, group_of_ma=group_of_ma,
    dates=dates_range, kha_nang_map=kha_nang_map,
    is_editing=is_editing, is_finalized=is_finalized,
)

# ── Chú thích ──────────────────────────────────────────────────────
st.markdown("---")
lc, rc = st.columns(2)
with lc:
    st.markdown("**🎨 Màu nhóm bác sĩ (3 ký tự đầu mã NV):**")
    gh = '<div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:4px">'
    for grp, clr in GROUP_COLOR.items():
        gh += (f'<span style="background:{clr};padding:3px 12px;'
               f'border-radius:4px;border:1px solid #ccc;font-size:12px">'
               f'{grp}</span>')
    gh += "</div>"
    st.markdown(gh, unsafe_allow_html=True)

with rc:
    st.markdown("**🕐 Màu buổi:**")
    sh2 = '<div style="display:flex;gap:6px;margin-top:4px">'
    for b in BUOI_COLS:
        bg  = BUOI_STYLE[b]["bg"]
        brd = BUOI_STYLE[b]["border"]
        sh2 += (f'<span style="background:{bg};padding:3px 12px;'
                f'border-radius:4px;border:2px solid {brd};font-size:12px">'
                f'{b}</span>')
    sh2 += "</div>"
    st.markdown(sh2, unsafe_allow_html=True)

st.markdown("""
**Ký hiệu vị trí:**  
`P` Nghỉ phép &nbsp;·&nbsp; `H` Học &nbsp;·&nbsp; `CT` Công tác &nbsp;·&nbsp;
`KH` Kế hoạch &nbsp;·&nbsp; `BT` Bù trực &nbsp;·&nbsp;
`VT` Vào trực &nbsp;·&nbsp; `RT` Ra trực &nbsp;·&nbsp;
`NL` Ngọc Lan &nbsp;·&nbsp; `Bù NL` Bù Ngọc Lan  
`PK - S` Tân Bình Sáng &nbsp;·&nbsp; `PK - C` Tân Bình Chiều &nbsp;·&nbsp;
`QA` Quốc Ánh &nbsp;·&nbsp; `NG` Ngoài giờ  
`NS` Nội soi &nbsp;·&nbsp; `NB` Nhận bệnh &nbsp;·&nbsp;
`PS / S / M` (combo hoặc lẻ) &nbsp;·&nbsp; `C+`
""")