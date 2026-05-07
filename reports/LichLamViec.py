"""
XẾP LỊCH LÀM VIỆC TỰ ĐỘNG – Bệnh viện Đa khoa Mỹ Đức

Cấu trúc dữ liệu:
  input_1  / Trang tính1 : Input_NhanSu  – A=MÃ NHÂN SỰ, B=MÃ CK, C=STT NHÓM, D=STT NV, E=HỌ VÀ TÊN
  input_2  / Trang tính1 : Input_ViTri   – A=ID, B=TÊN, C=VỊ TRÍ, D=KHẢ NĂNG(0/1)
  output_1 / Trang tính1 : Lịch trực     – C=NHÂN VIÊN, D=MÃ NHÂN SỰ, E=NGÀY TRỰC
  output_1 / Trang tính2 : Lịch PK       – C=NHÂN VIÊN, D=MÃ NV, E=NGÀY, F=LOẠI PK, G=BUỔI
  output_2 / Trang tính1 : Nghỉ phép     – C=NHÂN VIÊN, D=LOẠI YÊU CẦU, E=NGÀY, F=BUỔI, H=TÌNH TRẠNG DUYỆT
  output_2 / Trang tính2 : Lịch học      – C=NHÂN VIÊN, D=MÃ NV, E=NGÀY, F=BUỔI
  output_2 / Trang tính3 : CT/KH/BT      – C=NHÂN VIÊN, D=LOẠI(CT/KH/BT), F=NGÀY, G=BUỔI
"""

import streamlit as st
import pandas as pd
import gspread
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
import pathlib, base64, re
from google.oauth2.service_account import Credentials

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")

# ═══════════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════════
ANCHOR_DATE = date(2026, 4, 27)

BUOI_COLS = ["Sáng", "Trưa", "Chiều", "Tối"]
THU_VI    = {0:"Thứ Hai", 1:"Thứ Ba", 2:"Thứ Tư",
             3:"Thứ Năm", 4:"Thứ Sáu", 5:"Thứ Bảy", 6:"Chủ Nhật"}

NON_WORK_CODES = {"H","CT","KH","P","BT","VT","RT"}

GROUP_COLOR = {
    "S01": "#dbeafe",
    "S02": "#dcfce7",
    "S03": "#fef9c3",
    "I01": "#fce7f3",
    "A01": "#ede9fe",
}
DEFAULT_GROUP_COLOR = "#f1f5f9"

BUOI_STYLE = {
    "Sáng":  {"bg":"#fffbeb","border":"#fbbf24","hdr":"#f59e0b"},
    "Trưa":  {"bg":"#f0fdf4","border":"#34d399","hdr":"#10b981"},
    "Chiều": {"bg":"#eff6ff","border":"#60a5fa","hdr":"#3b82f6"},
    "Tối":   {"bg":"#fdf4ff","border":"#c084fc","hdr":"#a855f7"},
}

# Bảng decode buổi từ dữ liệu thực tế
BUOI_MAP = {
    "S":"Sáng","SÁNG":"Sáng",
    "T":"Trưa","TRƯA":"Trưa",
    "C":"Chiều","CHIỀU":"Chiều",
    "TO":"Tối","TỐI":"Tối",
}


# ═══════════════════════════════════════════════════════════════════
# UTILS
# ═══════════════════════════════════════════════════════════════════
@st.cache_data(ttl=3600)
def get_img_as_base64(file):
    with open(file,"rb") as f:
        return base64.b64encode(f.read()).decode()

def load_css(fp):
    try:
        with open(fp,"r",encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>",unsafe_allow_html=True)
    except Exception:
        pass

@st.cache_data(ttl=3600)
def load_credentials():
    s = st.secrets["google_service_account"]
    return Credentials.from_service_account_info(dict(s), scopes=[
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ])

def _gc():
    """Trả về gspread client đã xác thực."""
    return gspread.authorize(load_credentials())

def _sheet_name(key:str)->str:
    """
    Đọc tên spreadsheet từ secrets.toml.
    secrets.toml dùng section [sheet_name]:
      input_1   = "Input_NhanSu"
      input_2   = "Input_ViTri"
      output_1  = "Output_GanLichTruc_PK"
      output_2  = "Output_Phep_Hoc_CongTac_BT"
      output_fn = "Output_LichLamViec"
    """
    return st.secrets.get("sheet_name", {}).get(key, "")

def get_sheet_key(key:str)->str:
    """
    Đọc ID (key) của spreadsheet từ secrets.toml.
    secrets.toml dùng section [sheet_key]:
      output_fn = "1abc...xyz"
    """
    return st.secrets.get("sheet_key", {}).get(key, "")

@st.cache_data(ttl=300)
def read_sheet(spreadsheet_name:str, worksheet_name:str)->pd.DataFrame:
    """
    Mở spreadsheet theo TÊN (open_by_title) rồi đọc worksheet chỉ định.
    Dòng đầu tiên của sheet là header.
    """
    gc   = _gc()
    sh   = gc.open(spreadsheet_name)
    ws   = sh.worksheet(worksheet_name)
    rows = ws.get_all_values()
    if not rows:
        return pd.DataFrame()
    # Lọc header không rỗng
    headers = rows[0]
    return pd.DataFrame(rows[1:], columns=headers)

def to_date(series:pd.Series)->pd.Series:
    return pd.to_datetime(series, dayfirst=True, errors="coerce").dt.date

def week_num(d:date)->int:
    return ((d - ANCHOR_DATE).days // 7 % 4) + 1

def date_range(start:date, end:date):
    return [start+timedelta(days=i) for i in range((end-start).days+1)]

def sort_key(ma:str):
    order={"S01":0,"S02":1,"S03":2,"I01":3,"A01":4}
    return (order.get(ma[:3],99), ma)

def cell_has_work(codes:list)->bool:
    return bool(set(codes)-NON_WORK_CODES-{""})

def find_col(df:pd.DataFrame, candidates:list)->str:
    """Tìm tên cột đầu tiên khớp trong candidates."""
    cols_upper = {c.upper():c for c in df.columns}
    for c in candidates:
        if c in df.columns:
            return c
        if c.upper() in cols_upper:
            return cols_upper[c.upper()]
    return candidates[-1]

def expand_buoi(raw:str)->list:
    """
    Chuyển chuỗi buổi thực tế → list buổi chuẩn.
    "S - C" → ["Sáng","Chiều"], "S" → ["Sáng"], ...
    """
    s = raw.strip().upper()
    # Thử khớp trực tiếp
    if s in BUOI_MAP:
        return [BUOI_MAP[s]]
    # Tách theo dấu "-" / ","
    parts   = [p.strip() for p in re.split(r"[-,]", s) if p.strip()]
    result  = []
    for p in parts:
        if p in BUOI_MAP:
            result.append(BUOI_MAP[p])
    return result if result else []   # trả [] nếu không parse được


# ═══════════════════════════════════════════════════════════════════
# DATA LOADING  –  hoàn toàn từ Google Sheets, không dùng dữ liệu mẫu
# secrets.toml cấu trúc:
#   [sheet_name]
#   input_1   = "Input_NhanSu"
#   input_2   = "Input_ViTri"
#   output_1  = "Output_GanLichTruc_PK"
#   output_2  = "Output_Phep_Hoc_CongTac_BT"
#   output_fn = "Output_LichLamViec"
# ═══════════════════════════════════════════════════════════════════
def load_all_data()->dict:
    """
    Tải toàn bộ dữ liệu từ Google Sheets.
    Mọi lỗi đều được raise lên để UI hiển thị thông báo rõ ràng
    thay vì im lặng dùng dữ liệu mẫu.
    """
    sn = st.secrets.get("sheet_name", {})

    n_input1   = sn.get("input_1",   "Input_NhanSu")
    n_input2   = sn.get("input_2",   "Input_ViTri")
    n_output1  = sn.get("output_1",  "Output_GanLichTruc_PK")
    n_output2  = sn.get("output_2",  "Output_Phep_Hoc_CongTac_BT")

    errors = []
    result = {}

    def safe_read(key:str, spreadsheet:str, worksheet:str)->pd.DataFrame:
        try:
            df = read_sheet(spreadsheet, worksheet)
            # Chuẩn hoá tên cột: bỏ khoảng trắng thừa
            df.columns = [str(c).strip() for c in df.columns]
            # Bỏ dòng hoàn toàn rỗng
            df = df.dropna(how="all").reset_index(drop=True)
            return df
        except Exception as e:
            errors.append(f"❌ [{key}] {spreadsheet}/{worksheet}: {e}")
            return pd.DataFrame()

    result["nhan_su"]   = safe_read("input_1/TT1",   n_input1,  "Trang tính1")
    result["vi_tri"]    = safe_read("input_2/TT1",   n_input2,  "Trang tính1")
    result["lich_truc"] = safe_read("output_1/TT1",  n_output1, "Trang tính1")
    result["lich_pk"]   = safe_read("output_1/TT2",  n_output1, "Trang tính2")
    result["nghi_phep"] = safe_read("output_2/TT1",  n_output2, "Trang tính1")
    result["lich_hoc"]  = safe_read("output_2/TT2",  n_output2, "Trang tính2")
    result["cong_tac"]  = safe_read("output_2/TT3",  n_output2, "Trang tính3")

    # Báo lỗi từng sheet nếu có nhưng vẫn tiếp tục với sheet đọc được
    if errors:
        st.warning("⚠️ Một số sheet không đọc được:\n" + "\n".join(errors))

    # Bắt buộc phải có nhân sự và vị trí
    if result["nhan_su"].empty:
        st.error(f"❌ Không đọc được danh sách nhân sự từ **{n_input1}** / Trang tính1. "
                 "Vui lòng kiểm tra quyền truy cập Google Sheets.")
        st.stop()
    if result["vi_tri"].empty:
        st.error(f"❌ Không đọc được danh sách vị trí từ **{n_input2}** / Trang tính1. "
                 "Vui lòng kiểm tra quyền truy cập Google Sheets.")
        st.stop()

    return result

# ═══════════════════════════════════════════════════════════════════
# NV MAPS & KHẢ NĂNG
# ═══════════════════════════════════════════════════════════════════
def build_nv_maps(nhan_su:pd.DataFrame):
    """
    Trả về (ma_list, ten_of, group_of_ma)
      ma_list     : [mã] đã sắp xếp S01>S02>S03>I01>A01 rồi alphabet
      ten_of      : {mã → Họ và Tên (cột E)}
      group_of_ma : {mã → 3 ký tự đầu}
    """
    df = nhan_su.copy()
    df.columns = df.columns.str.strip()
    # Sử dụng chỉ số cột: 0=mã, 4=tên
    if df.empty or len(df.columns) < 5:
        return [], {}, {}
    df["_s"] = df.iloc[:, 0].astype(str).str.strip().apply(sort_key)
    df = df.sort_values("_s").reset_index(drop=True)
    ma_list     = df.iloc[:, 0].astype(str).str.strip().tolist()
    ten_of      = dict(zip(ma_list, df.iloc[:, 4].astype(str).str.strip()))
    group_of_ma = {ma: ma[:3] for ma in ma_list}
    return ma_list, ten_of, group_of_ma


def build_kha_nang(vi_tri:pd.DataFrame, ten_of:dict)->dict:
    """
    Trả về {mã_NV: set(vị_trí_có_khả_năng)}.
    input_2 cột A = ID dạng "S01.01.01" → map 6 ký tự đầu → mã NV
    input_2 cột B = TÊN → map ngược ten_of
    """
    df = vi_tri.copy()
    df.columns = df.columns.str.strip()
    if df.empty or len(df.columns) < 4:
        return {ma: set() for ma in ten_of}
    ten_to_ma = {v:k for k,v in ten_of.items()}
    result    = {ma: set() for ma in ten_of}

    for _, r in df.iterrows():
        raw = str(r.iloc[0]).strip() if len(r) > 0 else ""
        ten = str(r.iloc[1]).strip() if len(r) > 1 else ""
        pos = str(r.iloc[2]).strip() if len(r) > 2 else ""
        can = str(r.iloc[3]).strip() if len(r) > 3 else "0"

        # Ưu tiên: 6 ký tự đầu ID khớp với mã NV
        short = raw[:6] if len(raw)>=6 else raw
        if short in result:
            target = short
        elif ten in ten_to_ma:
            target = ten_to_ma[ten]
        else:
            # Tìm mờ theo tên
            target = None
            for ma, t in ten_of.items():
                if ten and (ten==t or ten in t or t in ten):
                    target=ma; break

        if target and can=="1" and pos:
            result[target].add(pos)
    return result


# ═══════════════════════════════════════════════════════════════════
# SCHEDULE BUILDER
# ═══════════════════════════════════════════════════════════════════
def build_schedule(start:date, end:date, data:dict):
    """
    Xây dựng ma trận lịch làm việc theo đúng thứ tự ưu tiên.
    Returns: (matrix, truc_map, ma_list, ten_of, group_of_ma, kha_nang_map)
    """
    all_dates = date_range(start, end)

    # ── Nhân sự & khả năng ───────────────────────────────────────────
    ma_list, ten_of, group_of_ma = build_nv_maps(data["nhan_su"])
    kha_nang_map = build_kha_nang(data["vi_tri"], ten_of)
    ten_to_ma    = {v:k for k,v in ten_of.items()}

    # Ma trận rỗng
    matrix:dict = {ma:{(d,b):[] for d in all_dates for b in BUOI_COLS}
                   for ma in ma_list}

    def find_ma(ten_str:str, ma_str:str="")->str|None:
        ma_str  = ma_str.strip()
        ten_str = ten_str.strip()
        # Khớp mã trực tiếp
        if ma_str in matrix: return ma_str
        # Lấy 6 ký tự đầu của ma_str
        short = ma_str[:6] if len(ma_str)>=6 else ma_str
        if short in matrix: return short
        # Khớp tên chính xác
        if ten_str in ten_to_ma: return ten_to_ma[ten_str]
        # Tìm mờ
        for ma, t in ten_of.items():
            if ten_str and (ten_str==t or (len(ten_str)>4 and (ten_str in t or t in ten_str))):
                return ma
        return None

    def set_cell(ma:str, ngay:date, buoi:str, code:str):
        """Thêm code vào cell nếu chưa có, bỏ qua nếu ngày/buổi không hợp lệ."""
        if ma not in matrix: return
        if ngay not in all_dates: return
        if buoi not in BUOI_COLS: return
        k = (ngay, buoi)
        if k in matrix[ma] and code not in matrix[ma][k]:
            matrix[ma][k].append(code)

    # ════════════════════════════════════════════════════════════════
    # ƯU TIÊN 1a – NGHỈ PHÉP (P)
    # output_2 / Trang tính1
    # Cột: C=NHÂN VIÊN, D=LOẠI YÊU CẦU, E=NGÀY, F=BUỔI, H=TÌNH TRẠNG DUYỆT
    # Điều kiện: D="Đăng ký phép mới" & H="Đã duyệt"
    #            Loại trừ nếu cùng người có "Hủy phép đã đăng ký" & H="Đã duyệt"
    # ════════════════════════════════════════════════════════════════
    np_df = data.get("nghi_phep", pd.DataFrame())
    if not np_df.empty:
        np_df = np_df.copy(); np_df.columns = np_df.columns.str.strip()
        cten  = find_col(np_df,["NHÂN VIÊN","C"])
        cloai = find_col(np_df,["LOẠI YÊU CẦU","D"])
        cngay = find_col(np_df,["NGÀY","E"])
        cbuoi = find_col(np_df,["BUỔI","F"])
        ctt   = find_col(np_df,["TÌNH TRẠNG DUYỆT","H"])

        if cloai in np_df.columns and ctt in np_df.columns:
            d_col = np_df[cloai].astype(str).str.strip()
            h_col = np_df[ctt].astype(str).str.strip()

            # Tập người đã bị hủy phép
            huy_idx = np_df[(d_col=="Hủy phép đã đăng ký")&(h_col=="Đã duyệt")].index
            # Mã STT của phép bị hủy (cột A thường là STT đơn)
            # Để an toàn: lấy tên+ngày làm khóa hủy
            huy_keys = set()
            for i in huy_idx:
                huy_keys.add((
                    str(np_df.at[i,cten]).strip(),
                    str(np_df.at[i,cngay]).strip()
                ))

            approved = np_df[(d_col=="Đăng ký phép mới")&(h_col=="Đã duyệt")].copy()
            approved[cngay] = to_date(approved[cngay])
            for _, r in approved.iterrows():
                ten  = str(r.get(cten,"")).strip()
                ngay = r.get(cngay)
                raw  = str(r.get(cngay,""))
                # Bỏ qua nếu bị hủy
                if (ten, raw) in huy_keys: continue
                ma = find_ma(ten)
                if ma is None or ngay not in all_dates: continue
                for b in expand_buoi(str(r.get(cbuoi,""))):
                    set_cell(ma, ngay, b, "P")

    # ════════════════════════════════════════════════════════════════
    # ƯU TIÊN 1b – LỊCH HỌC (H)
    # output_2 / Trang tính2: C=NHÂN VIÊN, D=MÃ NV, E=NGÀY, F=BUỔI
    # ════════════════════════════════════════════════════════════════
    hoc_df = data.get("lich_hoc", pd.DataFrame())
    if not hoc_df.empty:
        hoc_df = hoc_df.copy(); hoc_df.columns = hoc_df.columns.str.strip()
        cten  = find_col(hoc_df,["NHÂN VIÊN","C"])
        cma   = find_col(hoc_df,["MÃ NHÂN VIÊN","D"])
        cngay = find_col(hoc_df,["NGÀY","E"])
        cbuoi = find_col(hoc_df,["BUỔI","F"])
        hoc_df[cngay] = to_date(hoc_df[cngay])
        for _, r in hoc_df.iterrows():
            ma = find_ma(str(r.get(cten,"")), str(r.get(cma,"")))
            ngay = r.get(cngay)
            if ma is None or ngay not in all_dates: continue
            for b in expand_buoi(str(r.get(cbuoi,""))):
                set_cell(ma, ngay, b, "H")

    # ════════════════════════════════════════════════════════════════
    # ƯU TIÊN 1c – CÔNG TÁC / KH / BT
    # output_2 / Trang tính3: C=NHÂN VIÊN, D=LOẠI(CT/KH/BT), F=NGÀY, G=BUỔI
    # ════════════════════════════════════════════════════════════════
    ct_df = data.get("cong_tac", pd.DataFrame())
    if not ct_df.empty:
        ct_df = ct_df.copy(); ct_df.columns = ct_df.columns.str.strip()
        cten  = find_col(ct_df,["NHÂN VIÊN","C"])
        cloai = find_col(ct_df,["LOẠI (CT/BT)","D"])
        cngay = find_col(ct_df,["NGÀY","F"])
        cbuoi = find_col(ct_df,["BUỔI","G"])
        ct_df[cngay] = to_date(ct_df[cngay])
        for _, r in ct_df.iterrows():
            ma   = find_ma(str(r.get(cten,"")))
            ngay = r.get(cngay)
            loai = str(r.get(cloai,"")).strip().upper()
            if loai not in ("CT","KH","BT"): continue
            if ma is None or ngay not in all_dates: continue
            for b in expand_buoi(str(r.get(cbuoi,""))):
                set_cell(ma, ngay, b, loai)

    # ════════════════════════════════════════════════════════════════
    # ƯU TIÊN 2 – LỊCH TRỰC → truc_map
    # output_1 / Trang tính1: C=NHÂN VIÊN, D=MÃ NHÂN SỰ, E=NGÀY TRỰC
    # Mỗi dòng = 1 người trực 1 ngày → tổng hợp theo ngày
    # ════════════════════════════════════════════════════════════════
    truc_map:dict = {}
    lt_df = data.get("lich_truc", pd.DataFrame())
    if not lt_df.empty:
        lt_df = lt_df.copy(); lt_df.columns = lt_df.columns.str.strip()
        cten  = find_col(lt_df,["NHÂN VIÊN","C"])
        cma   = find_col(lt_df,["MÃ NHÂN SỰ","D"])
        cngay = find_col(lt_df,["NGÀY TRỰC","E"])
        lt_df[cngay] = to_date(lt_df[cngay])
        for _, r in lt_df.iterrows():
            ma   = find_ma(str(r.get(cten,"")), str(r.get(cma,"")))
            ngay = r.get(cngay)
            if ma is None or ngay not in all_dates: continue
            truc_map.setdefault(ngay,[])
            if ma not in truc_map[ngay]:
                truc_map[ngay].append(ma)
        # Sắp xếp S01>S02>S03>I01
        for d in truc_map:
            truc_map[d] = sorted(truc_map[d], key=sort_key)

    # ════════════════════════════════════════════════════════════════
    # ƯU TIÊN 3 – VT & RT
    # ════════════════════════════════════════════════════════════════
    for ngay, truc_list in truc_map.items():
        next_d = ngay + timedelta(days=1)
        for ma in truc_list:
            if ma not in matrix: continue
            # Chiều ngày trực → VT
            set_cell(ma, ngay, "Chiều", "VT")
            # RT ngày hôm sau
            if next_d in all_dates:
                if ma[:3]=="S02" and "NL" in kha_nang_map.get(ma,set()):
                    set_cell(ma, next_d, "Sáng", "RT")
                else:
                    set_cell(ma, next_d, "Chiều", "RT")

    # ════════════════════════════════════════════════════════════════
    # ƯU TIÊN 4 – LỊCH PHÒNG KHÁM
    # output_1 / Trang tính2: C=NHÂN VIÊN, D=MÃ NV, E=NGÀY, F=LOẠI PK, G=BUỔI
    # "Phòng khám Tân Bình" → "PK" (không phân biệt S/C, giữ nguyên buổi từ cột G)
    # "Phòng khám Ngọc Lan" → "NL"  (+ áp dụng quy tắc NL)
    # "Phòng khám Quốc Ánh" → "QA"
    # ════════════════════════════════════════════════════════════════
    pk_df = data.get("lich_pk", pd.DataFrame())
    if not pk_df.empty:
        pk_df = pk_df.copy(); pk_df.columns = pk_df.columns.str.strip()
        cten  = find_col(pk_df,["NHÂN VIÊN","C"])
        cma   = find_col(pk_df,["MÃ NHÂN VIÊN","D"])
        cngay = find_col(pk_df,["NGÀY","E"])
        cloai = find_col(pk_df,["LOẠI","F"])
        cbuoi = find_col(pk_df,["BUỔI","G"])
        pk_df[cngay] = to_date(pk_df[cngay])
        for _, r in pk_df.iterrows():
            ma       = find_ma(str(r.get(cten,"")), str(r.get(cma,"")))
            ngay     = r.get(cngay)
            loai_raw = str(r.get(cloai,"")).strip()
            buoi_raw = str(r.get(cbuoi,"")).strip()
            if ma is None or ngay not in all_dates: continue
            if ngay.weekday()==6: continue  # Chủ nhật không xếp PK

            if "Ngọc Lan" in loai_raw:
                # Quy tắc NL đầy đủ
                _apply_nl(matrix, ma, ngay, all_dates, set_cell)
            elif "Quốc Ánh" in loai_raw:
                for b in expand_buoi(buoi_raw) or ["Sáng"]:
                    set_cell(ma, ngay, b, "QA")
            elif "Tân Bình" in loai_raw:
                for b in expand_buoi(buoi_raw) or ["Sáng"]:
                    set_cell(ma, ngay, b, "PK")
            else:
                # Phòng khám khác: điền tên rút gọn nếu cần
                pass

    # ════════════════════════════════════════════════════════════════
    # ƯU TIÊN 5a – NGOÀI GIỜ (NG): 1 người/ngày (trừ T5,CN), luân phiên
    # ════════════════════════════════════════════════════════════════
    ng_pool = [ma for ma in ma_list if "NG" in kha_nang_map.get(ma,set())]
    ng_rot  = 0
    for d in all_dates:
        if d.weekday() in (3,6): continue
        for i in range(max(len(ng_pool),1)):
            ma = ng_pool[(ng_rot+i)%max(len(ng_pool),1)]
            for b in BUOI_COLS:
                if matrix[ma].get((d,b),[]) == []:
                    matrix[ma][(d,b)].append("NG")
                    ng_rot = (ng_rot+i+1)%max(len(ng_pool),1)
                    break
            else: continue
            break

    # ════════════════════════════════════════════════════════════════
    # ƯU TIÊN 5b – NỘI SOI (NS) buổi Tối: 1 người/ngày, không trùng VT/RT
    # ════════════════════════════════════════════════════════════════
    ns_pool = [ma for ma in ma_list if "NS" in kha_nang_map.get(ma,set())]
    ns_rot  = 0
    for d in all_dates:
        if d.weekday()==6: continue
        for i in range(max(len(ns_pool),1)):
            ma   = ns_pool[(ns_rot+i)%max(len(ns_pool),1)]
            cell = matrix[ma].get((d,"Tối"),[])
            if "VT" not in cell and "RT" not in cell and cell==[]:
                matrix[ma][(d,"Tối")].append("NS")
                ns_rot=(ns_rot+i+1)%max(len(ns_pool),1); break

    # ════════════════════════════════════════════════════════════════
    # ƯU TIÊN 5c – NHẬN BỆNH (NB): 2 người/ngày, ≥1 S03, luân phiên
    # ════════════════════════════════════════════════════════════════
    nb_pool  = [ma for ma in ma_list if "NB" in kha_nang_map.get(ma,set())]
    nb_s03   = [ma for ma in nb_pool if ma[:3]=="S03"]
    nb_other = [ma for ma in nb_pool if ma[:3]!="S03"]
    nb_s03r  = 0; nb_othr = 0
    for d in all_dates:
        if d.weekday()==6: continue
        assigned=[]
        for i in range(max(len(nb_s03),1)):
            ma=nb_s03[(nb_s03r+i)%max(len(nb_s03),1)]
            if ma not in assigned: assigned.append(ma); nb_s03r+=i+1; break
        for i in range(max(len(nb_other),1)):
            ma=nb_other[(nb_othr+i)%max(len(nb_other),1)]
            if ma not in assigned: assigned.append(ma); nb_othr+=i+1; break
        for ma in assigned[:2]:
            for b in BUOI_COLS:
                if matrix[ma].get((d,b),[])==[]:
                    matrix[ma][(d,b)].append("NB"); break

    # ════════════════════════════════════════════════════════════════
    # ƯU TIÊN 5d – C+
    # Slots: Chiều T3, Sáng T4, Chiều T5, Sáng+Chiều T7
    # ════════════════════════════════════════════════════════════════
    cp_pool  = [ma for ma in ma_list if "C+" in kha_nang_map.get(ma,set())]
    cp_slots = {1:["Chiều"],2:["Sáng"],3:["Chiều"],5:["Sáng","Chiều"]}
    cp_rot   = 0
    for d in all_dates:
        wd=d.weekday()
        if wd not in cp_slots: continue
        for b in cp_slots[wd]:
            for i in range(max(len(cp_pool),1)):
                ma=cp_pool[(cp_rot+i)%max(len(cp_pool),1)]
                if "C+" not in matrix[ma].get((d,b),[]):
                    matrix[ma][(d,b)].append("C+"); cp_rot+=i+1; break

    # ════════════════════════════════════════════════════════════════
    # ƯU TIÊN 6 – COMBO PS–S–M
    # 4 người/buổi (≥1 S02 luân phiên; thiếu S02 thay S01)
    # Nếu <4 người rảnh: xếp lẻ PS(2), M(4), S(4)
    # ════════════════════════════════════════════════════════════════
    combo_pool = [ma for ma in ma_list
                  if {"PS","S","M"}.issubset(kha_nang_map.get(ma,set()))]
    c_s02  = [ma for ma in combo_pool if ma[:3]=="S02"]
    c_oth  = [ma for ma in combo_pool if ma[:3] not in ("S01","S02")]
    cs02_r = 0; coth_r = 0
    for d in all_dates:
        if d.weekday()==6: continue
        for b in ["Sáng","Chiều"]:
            free     = [ma for ma in combo_pool if matrix[ma].get((d,b),[])==[]]
            free_s02 = [ma for ma in free if ma[:3]=="S02"]
            free_oth = [ma for ma in free if ma[:3] not in ("S01","S02")]
            if len(free)>=4:
                chosen=[]
                if free_s02:
                    chosen.append(free_s02[cs02_r%len(free_s02)]); cs02_r+=1
                else:
                    s01f=[ma for ma in ma_list if ma[:3]=="S01"
                          and matrix[ma].get((d,b),[])==[]]
                    if s01f: chosen.append(s01f[0])
                for i in range(len(free_oth)*3):
                    if len(chosen)>=4 or not free_oth: break
                    ma=free_oth[coth_r%len(free_oth)]; coth_r+=1
                    if ma not in chosen: chosen.append(ma)
                for ma in chosen[:4]:
                    if (d,b) in matrix[ma]:
                        matrix[ma][(d,b)]=["PS","S","M"]
            else:
                for pos,need in [("PS",2),("M",4),("S",4)]:
                    pf=[ma for ma in combo_pool
                        if pos in kha_nang_map.get(ma,set())
                        and matrix[ma].get((d,b),[])==[]]
                    for ma in pf[:need]:
                        matrix[ma][(d,b)].append(pos)

    return matrix, truc_map, ma_list, ten_of, group_of_ma, kha_nang_map


def _apply_nl(matrix, ma, ngay_truc, all_dates, set_cell_fn):
    """Quy tắc 7 – Ngọc Lan đầy đủ."""
    next_d = ngay_truc + timedelta(days=1)
    bu_d   = ngay_truc + timedelta(days=2)
    # Sáng ngày trực
    set_cell_fn(ma, ngay_truc, "Sáng", "NL")
    # Chiều + Tối ngày kế
    if next_d in all_dates:
        set_cell_fn(ma, next_d, "Chiều", "NL")
        set_cell_fn(ma, next_d, "Tối",   "NL")
    # Bù NL: Sáng + Chiều ngày kia
    if bu_d in all_dates:
        set_cell_fn(ma, bu_d, "Sáng",  "NL")
        set_cell_fn(ma, bu_d, "Chiều", "Bù NL")
    # Thứ Tư ↔ Thứ Bảy
    wd         = ngay_truc.weekday()
    week_start = ngay_truc - timedelta(days=wd)
    extra = None
    if wd==2:   extra = week_start+timedelta(days=5)
    elif wd==5: extra = week_start+timedelta(days=2)
    if extra and extra in all_dates:
        set_cell_fn(ma, extra, "Sáng", "NL")

# ═══════════════════════════════════════════════════════════════════
# RENDER TABLE
# ═══════════════════════════════════════════════════════════════════
_CSS = """
<style>
/* Wrapper cuộn */
.sch-wrap{
  overflow:auto; border-radius:10px;
  box-shadow:0 4px 22px rgba(0,0,0,.16);
  border:1px solid #b8c9de;
  max-height:80vh;
}
.sch-tbl{
  border-collapse:collapse;
  font-family:'Segoe UI',Tahoma,sans-serif;
  font-size:11px; width:max-content; min-width:100%;
}

/* ── HEADER ────────────────────────────── */
.sch-tbl thead th{
  position:sticky; top:0; z-index:14;
  background:#1e3a5f; color:#fff;
  padding:5px 6px; border:1px solid #2d5089;
  white-space:nowrap; text-align:center; font-weight:700;
}
.sch-tbl thead tr:nth-child(2) th{
  top:34px; z-index:13; font-size:10px; font-weight:600; padding:3px 4px;
}

/* ── CỘT HỌ TÊN CỐ ĐỊNH ────────────────── */
.sch-tbl th.nc,.sch-tbl td.nc{
  position:sticky; left:0; z-index:12;
  min-width:160px; max-width:200px;
  border-right:2px solid #90aacb;
  text-align:left; padding-left:8px;
  white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
  font-weight:600; background:#f8fafc;
}
.sch-tbl thead th.nc{ z-index:22; background:#0f2540; }

/* ── Ô DỮ LIỆU ─────────────────────────── */
.sch-tbl td{
  border:1px solid #e0e7f0; padding:2px 4px;
  text-align:center; min-width:52px; max-width:84px;
  font-size:10px; vertical-align:middle;
  white-space:pre-wrap; word-break:break-word; line-height:1.3;
}

/* ── DÒNG ĐẾM ──────────────────────────── */
.sch-tbl tr.cnt td{ background:#e8f0fe!important; font-weight:700; color:#1a56db; }
.sch-tbl tr.cnt td.nc{ background:#cfe2ff!important; font-style:italic; font-size:10px; color:#1e40af; }

/* ── DÒNG TUA TRỰC ─────────────────────── */
.sch-tbl tr.dty td{ background:#fff8e1!important; color:#78350f; font-weight:600; font-size:10px; }
.sch-tbl tr.dty td.nc{ background:#fef3c7!important; font-weight:700; }

/* ── TRẠNG THÁI Ô ──────────────────────── */
.cf{ font-weight:700; color:#1e3a5f; }
.ce{ color:#ced4da; font-size:9px; }
.snd{ background:#f2f4f7!important; color:#c0c7d0!important; font-style:italic; }

/* ── NÚT MỞ RỘNG ───────────────────────── */
.expand-btn button{ font-size:11px!important; padding:2px 8px!important; }
</style>
"""

def render_table(matrix, truc_map, ma_list, ten_of, group_of_ma,
                 dates, kha_nang_map, is_editing, is_finalized):
    st.markdown(_CSS, unsafe_allow_html=True)

    # ── Header ngày ─────────────────────────────────────────────────
    h1=""; h2=""
    for d in dates:
        thu = THU_VI.get(d.weekday(),"")
        ns  = d.strftime("%d/%m")
        h1 += (f'<th colspan="4" style="background:#1e3a5f;'
               f'border-bottom:2px solid #60a5fa;font-size:11px">'
               f'{thu}<br><small style="font-weight:400;font-size:10px">{ns}</small></th>')
        for b in BUOI_COLS:
            bg  = BUOI_STYLE[b]["bg"]
            brd = BUOI_STYLE[b]["border"]
            h2 += (f'<th style="background:{bg};color:#374151;'
                   f'border-bottom:2px solid {brd}">'
                   f'{b[0]}</th>')

    # ── Dòng đếm NV có việc ─────────────────────────────────────────
    cnt_cells=""
    for d in dates:
        for b in BUOI_COLS:
            cnt = sum(1 for ma in ma_list
                      if cell_has_work(matrix.get(ma,{}).get((d,b),[])))
            bg  = BUOI_STYLE[b]["bg"]
            cnt_cells += (f'<td style="background:{bg};font-size:11px">'
                          f'{"<b>"+str(cnt)+"</b>" if cnt else ""}</td>')

    # ── Dòng nhân viên ──────────────────────────────────────────────
    rows_html=""
    for ma in ma_list:
        grp    = group_of_ma.get(ma,"")
        row_bg = GROUP_COLOR.get(grp, DEFAULT_GROUP_COLOR)
        ten    = ten_of.get(ma,ma)
        row    = (f'<tr style="background:{row_bg}">'
                  f'<td class="nc" style="background:{row_bg}" title="{ten}">{ten}</td>')
        for d in dates:
            if d.weekday()==6:          # Chủ Nhật
                for _ in BUOI_COLS:
                    row += '<td class="snd">—</td>'
                continue
            for b in BUOI_COLS:
                codes   = matrix.get(ma,{}).get((d,b),[])
                display = " - ".join(codes) if codes else ""
                cls     = "cf" if display else "ce"
                txt     = display if display else "·"
                bg      = BUOI_STYLE[b]["bg"]
                row    += f'<td style="background:{bg}"><span class="{cls}">{txt}</span></td>'
        row += "</tr>"
        rows_html += row

    # ── Dòng tua trực ────────────────────────────────────────────────
    duty_cells=""
    for d in dates:
        tl  = truc_map.get(d,[])
        val = " - ".join([ten_of.get(m,m) for m in tl])
        # Colspan 4 cho mỗi ngày
        duty_cells += (f'<td colspan="4" style="text-align:center;'
                       f'font-size:10px;padding:3px 2px;line-height:1.4">'
                       f'{val if val else "&nbsp;"}</td>')

    html = f"""
    <div class="sch-wrap">
    <table class="sch-tbl">
    <thead>
      <tr><th class="nc" rowspan="2">Họ và Tên</th>{h1}</tr>
      <tr>{h2}</tr>
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

    # ── Chỉnh sửa inline ─────────────────────────────────────────────
    if is_editing and not is_finalized:
        st.markdown("---")
        st.markdown("**✏️ Chỉnh sửa ô lịch**")
        st.caption(
            "Chỉ hiển thị vị trí mà nhân viên đó có **Khả năng = 1** trong Input_ViTri. "
            "Sau khi chọn xong bấm **Cập nhật ô**."
        )
        workdays = [d for d in dates if d.weekday()!=6]
        dlbls    = [THU_VI[d.weekday()]+" "+d.strftime("%d/%m") for d in workdays]
        nvlbls   = [ten_of.get(ma,ma) for ma in ma_list]

        c1,c2,c3 = st.columns([2,2,1])
        with c1:
            nv_i = st.selectbox("Nhân viên", range(len(ma_list)),
                                format_func=lambda i:nvlbls[i], key="es_nv")
        with c2:
            d_i  = st.selectbox("Ngày", range(len(workdays)),
                                format_func=lambda i:dlbls[i], key="es_day")
        with c3:
            b_s  = st.selectbox("Buổi", BUOI_COLS, key="es_buoi")

        sel_ma   = ma_list[nv_i]
        sel_date = workdays[d_i]
        current  = matrix[sel_ma].get((sel_date,b_s),[])
        # Chỉ liệt kê vị trí nhân sự có khả năng = 1
        eligible = sorted(kha_nang_map.get(sel_ma,set()))

        st.markdown(f"**Hiện tại:** `{' - '.join(current) if current else '( trống )'}`")
        new_vals = st.multiselect(
            "Vị trí mới (chỉ vị trí NV có khả năng):",
            options=eligible,
            default=[c for c in current if c in eligible],
            key="es_multi"
        )
        ua,ub = st.columns(2)
        with ua:
            if st.button("💾 Cập nhật ô", type="primary", use_container_width=True):
                matrix[sel_ma][(sel_date,b_s)] = new_vals
                st.session_state["matrix"] = matrix
                st.toast(f"✅ {nvlbls[nv_i]} – {dlbls[d_i]} – {b_s}")
                st.rerun()
        with ub:
            if st.button("🗑️ Xóa ô", use_container_width=True):
                matrix[sel_ma][(sel_date,b_s)] = []
                st.session_state["matrix"] = matrix
                st.toast("🗑️ Đã xóa ô")
                st.rerun()


# ═══════════════════════════════════════════════════════════════════
# SAVE TO GOOGLE SHEETS
# ═══════════════════════════════════════════════════════════════════
def save_to_sheets(matrix, ma_list, ten_of, dates, truc_map, wn, sd, ed)->tuple:
    """
    Upload bảng xếp lịch lên Google Sheets (output_fn).
    Mỗi tuần = 1 tab. Cùng tab → replace (clear rồi ghi lại).
    Giữ nguyên cấu trúc bảng: dòng 1=ngày, dòng 2=buổi, sau đó NV, cuối=tua trực.
    """
    try:
        creds = load_credentials()
        gc    = gspread.authorize(creds)
        key   = get_sheet_key("output_fn")
        if not key:
            return False, "Chưa cấu hình output_fn trong secrets.toml"

        sh  = gc.open_by_key(key)
        tab = f"Tuần {wn} ({sd.strftime('%d/%m')}-{ed.strftime('%d/%m/%Y')})"

        # Tạo hoặc xóa tab cũ
        existing = {ws.title: ws for ws in sh.worksheets()}
        if tab in existing:
            ws = existing[tab]
            ws.clear()
        else:
            n_rows = len(ma_list) + 5
            n_cols = 1 + len(dates)*4
            ws = sh.add_worksheet(title=tab,
                                  rows=max(n_rows,50),
                                  cols=max(n_cols,30))

        # ── Xây dữ liệu ───────────────────────────────────────────
        # Dòng 1: tên ngày (mỗi ngày chiếm 4 cột)
        row1 = ["Họ và Tên"]
        for d in dates:
            row1.append(f"{THU_VI[d.weekday()]} {d.strftime('%d/%m/%Y')}")
            row1.extend(["","",""])

        # Dòng 2: buổi
        row2 = [""]
        for _ in dates:
            row2.extend(BUOI_COLS)

        # Dòng nhân viên
        nv_rows = []
        for ma in ma_list:
            row = [ten_of.get(ma,ma)]
            for d in dates:
                for b in BUOI_COLS:
                    codes = matrix.get(ma,{}).get((d,b),[])
                    row.append(" - ".join(codes) if codes else "")
            nv_rows.append(row)

        # Dòng tua trực
        duty_row = ["Tua trực"]
        for d in dates:
            tl = truc_map.get(d,[])
            duty_row.append(" - ".join([ten_of.get(m,m) for m in tl]))
            duty_row.extend(["","",""])

        all_rows = [row1, row2] + nv_rows + [duty_row]

        # ── Ghi lên Sheets bằng batch update ──────────────────────
        # Dùng ws.update() trực tiếp (đơn giản, ít lỗi nhất)
        ws.update(values=all_rows, range_name="A1",
                  value_input_option="RAW")

        return True, tab

    except Exception as e:
        import traceback
        return False, f"{e}\n{traceback.format_exc()}"


# ═══════════════════════════════════════════════════════════════════
# MAIN APPLICATION
# ═══════════════════════════════════════════════════════════════════
load_css(pathlib.Path("asset/style.css"))

try:
    img = get_img_as_base64("pages/img/logo.png")
    st.markdown(f"""
    <div class="fixed-header">
      <div class="header-content">
        <img src="data:image/png;base64,{img}" alt="logo">
        <div class="header-text">
          <h1>BỆNH VIỆN ĐA KHOA MỸ ĐỨC
            <span style="vertical-align:super;font-size:.6em">&#174;</span></h1>
        </div>
      </div>
      <div class="header-subtext"><p>XẾP LỊCH LÀM VIỆC</p></div>
    </div>
    <div class="header-underline"></div>
    """, unsafe_allow_html=True)
except Exception:
    st.title("BỆNH VIỆN ĐA KHOA MỸ ĐỨC – XẾP LỊCH LÀM VIỆC")

nhan_vien = st.session_state.get("username","Không xác định")
st.html(f'<p class="demuc"><i>Bác sĩ đang thực hiện: {nhan_vien}</i></p>')

# Session state defaults
_DEF = dict(
    schedule_built=False, matrix=None, truc_map=None,
    ma_list=None, ten_of=None, group_of_ma=None, kha_nang_map=None,
    dates=None, week_num=None, start_date=None, end_date=None,
    is_editing=False, is_finalized=False,
    edit_row_idx=None, view_df=None, confirm_delete_idx=None,
)
for k,v in _DEF.items():
    if k not in st.session_state: st.session_state[k]=v

# ════════════════════════════════════════════════════════════════════
# SECTION 1 – Chọn khoảng thời gian
# ════════════════════════════════════════════════════════════════════
st.markdown("---")
st.markdown("### 📅 Chọn khoảng thời gian xếp lịch")

today = date.today()
def_s = today - timedelta(days=today.weekday())
def_e = def_s + timedelta(days=6)

c1,c2 = st.columns(2)
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

    wn = week_num(start_input)
    st.info(
        f"📌 **{start_input.strftime('%d/%m/%Y')} — {end_input.strftime('%d/%m/%Y')}** "
        f"· Tuần thứ **{wn}** (chu kỳ 4 tuần · mốc 27/04/2026 = Tuần 1)"
    )

    if st.button("🗓️ Bắt đầu xếp lịch", type="primary"):
        with st.spinner("Đang tải dữ liệu và xây dựng lịch tự động…"):
            raw = load_all_data()
            mx, tm, ml, tof, gom, knm = build_schedule(start_input, end_input, raw)
            st.session_state.update(
                schedule_built=True,
                matrix=mx, truc_map=tm, ma_list=ml,
                ten_of=tof, group_of_ma=gom, kha_nang_map=knm,
                dates=date_range(start_input, end_input),
                week_num=wn, start_date=start_input, end_date=end_input,
                is_editing=False, is_finalized=False,
            )
        st.success("✅ Lịch đã được xây dựng!")
        st.rerun()

# ════════════════════════════════════════════════════════════════════
# SECTION 2 – Bảng xếp lịch
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
a1,a2,a3,a4 = st.columns([1.4,1.4,1.4,1.4])
with a1:
    if not is_finalized:
        lbl = "🔒 Đang chỉnh sửa…" if is_editing else "✏️ Chỉnh sửa"
        if st.button(lbl, use_container_width=True):
            st.session_state["is_editing"] = not is_editing
            st.rerun()
with a2:
    if not is_finalized:
        if st.button("✅ Chốt danh sách", type="primary", use_container_width=True):
            st.session_state.update(is_editing=False, is_finalized=True)
            st.rerun()
    else:
        st.success("🔒 Đã chốt danh sách")
with a3:
    if is_finalized:
        if st.button("💾 Lưu danh sách", type="primary", use_container_width=True):
            with st.spinner("Đang upload lên Google Sheets…"):
                ok, msg = save_to_sheets(
                    matrix, ma_list, ten_of, dates_range,
                    truc_map, wn_s, sd, ed
                )
            if ok:
                st.success(f"✅ Đã lưu lên tab: **{msg}**")
            else:
                st.error(f"❌ Lỗi upload:\n{msg}")
with a4:
    if st.button("🔄 Xây dựng lại", use_container_width=True,
                 help="Xây lại từ đầu — mọi chỉnh sửa thủ công sẽ mất"):
        st.session_state["schedule_built"] = False
        st.rerun()

# ── Bảng ──────────────────────────────────────────────────────────
st.markdown("#### 📊 Bảng xếp lịch làm việc")
render_table(
    matrix=matrix, truc_map=truc_map,
    ma_list=ma_list, ten_of=ten_of, group_of_ma=group_of_ma,
    dates=dates_range, kha_nang_map=kha_nang_map,
    is_editing=is_editing, is_finalized=is_finalized,
)

# ── Chú thích ──────────────────────────────────────────────────────
st.markdown("---")
lc,rc = st.columns(2)
with lc:
    st.markdown("**🎨 Màu nhóm (3 ký tự đầu mã NV):**")
    gh='<div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:4px">'
    for grp,clr in GROUP_COLOR.items():
        gh+=(f'<span style="background:{clr};padding:3px 12px;'
             f'border-radius:4px;border:1px solid #ccc;font-size:12px">{grp}</span>')
    gh+="</div>"
    st.markdown(gh, unsafe_allow_html=True)

with rc:
    st.markdown("**🕐 Màu buổi:**")
    sh2='<div style="display:flex;gap:6px;margin-top:4px">'
    for b in BUOI_COLS:
        bg=BUOI_STYLE[b]["bg"]; brd=BUOI_STYLE[b]["border"]
        sh2+=(f'<span style="background:{bg};padding:3px 12px;'
              f'border-radius:4px;border:2px solid {brd};font-size:12px">{b}</span>')
    sh2+="</div>"
    st.markdown(sh2, unsafe_allow_html=True)

st.markdown("""
**Ký hiệu:**
`P` Nghỉ phép &nbsp;·&nbsp; `H` Học &nbsp;·&nbsp; `CT` Công tác &nbsp;·&nbsp;
`KH` Kế hoạch &nbsp;·&nbsp; `BT` Bù trực &nbsp;·&nbsp;
`VT` Vào trực &nbsp;·&nbsp; `RT` Ra trực  
`NL` Ngọc Lan &nbsp;·&nbsp; `Bù NL` Bù Ngọc Lan &nbsp;·&nbsp;
`PK` Tân Bình &nbsp;·&nbsp; `QA` Quốc Ánh &nbsp;·&nbsp;
`NG` Ngoài giờ &nbsp;·&nbsp; `NS` Nội soi &nbsp;·&nbsp; `NB` Nhận bệnh  
`PS / S / M` (combo hoặc lẻ) &nbsp;·&nbsp; `C+`
""")