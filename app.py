import streamlit as st
import pandas as pd
import pydeck as pdk
import math

st.set_page_config(page_title="世田谷 病院・薬局マップ", layout="wide")

st.title("世田谷 病院・薬局検索マップ（診療科・症状・距離対応）")

# ================================
# データ読み込み
# ================================
df_hosp = pd.read_csv("hospital.csv")
df_dept = pd.read_csv("department.csv")
df_pharm = pd.read_csv("pharmacy.csv")

# ================================
# 固定現在地
# ================================
user_lat = 35.64369547433956
user_lon = 139.64797830490818

st.success(f"現在地（固定）: {user_lat}, {user_lon}")

# ================================
# 距離計算
# ================================
def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

# ================================
# 列検出
# ================================
def detect_column(df, candidates):
    for c in candidates:
        if c in df.columns:
            return c
    return None

# ================================
# 病院整形
# ================================
name_h = detect_column(df_hosp, ["医療機関名称", "名称"])
addr_h = detect_column(df_hosp, ["所在地", "住所"])
lat_h = detect_column(df_hosp, ["緯度"])
lon_h = detect_column(df_hosp, ["経度"])
code_h = detect_column(df_hosp, ["医療機関コード", "医療機関ID"])

df_hosp = df_hosp[df_hosp[addr_h].str.contains("世田谷区", na=False)]

dept_code = detect_column(df_dept, ["医療機関コード", "医療機関ID"])
dept_name = detect_column(df_dept, ["診療科名", "標榜診療科", "診療科", "標榜科名"])

df_hosp["code"] = df_hosp[code_h].astype(str).str.zfill(10)
df_dept["code"] = df_dept[dept_code].astype(str).str.zfill(10)

dept_group = df_dept.groupby("code")[dept_name].apply(list).reset_index()
df_hosp = df_hosp.merge(dept_group, on="code", how="left")
df_hosp["カテゴリ"] = "病院"

# ================================
# 薬局整形
# ================================
name_p = detect_column(df_pharm, ["薬局名称", "名称"])
addr_p = detect_column(df_pharm, ["所在地", "住所"])
lat_p = detect_column(df_pharm, ["緯度"])
lon_p = detect_column(df_pharm, ["経度"])

df_pharm = df_pharm[df_pharm[addr_p].str.contains("世田谷区", na=False)]
df_pharm["診療科名"] = None
df_pharm["カテゴリ"] = "薬局"

df_pharm = df_pharm.rename(columns={
    name_p: name_h,
    addr_p: addr_h,
    lat_p: lat_h,
    lon_p: lon_h
})

# ================================
# 統合
# ================================
df_all = pd.concat([df_hosp, df_pharm], ignore_index=True)

# ================================
# 症状マップ
# ================================
symptom_map = {
    "風邪": ["内科", "小児科"],
    "発熱": ["内科", "小児科"],
    "腹痛": ["消化器内科"],
    "頭痛": ["脳神経内科"],
    "胸痛": ["循環器内科"],
    "息苦しい": ["呼吸器内科"],
    "皮膚": ["皮膚科"],
    "目": ["眼科"],
    "耳": ["耳鼻咽喉科"],
}

# ================================
# UI
# ================================
keyword = st.text_input("名称検索")

symptom = st.text_input(
    "症状で検索",
    placeholder="例：風邪、腹痛、頭痛など"
)

category = st.selectbox("カテゴリ", ["すべて", "病院", "薬局"])

all_dept = []
if dept_name in df_hosp.columns:
    for x in df_hosp[dept_name].dropna():
        if isinstance(x, list):
            all_dept.extend(x)
all_dept = sorted(set(all_dept))

selected_dept = st.selectbox("診療科", ["すべて"] + all_dept)

distance_sort = st.checkbox("距離順")
radius = st.selectbox("半径", ["指定なし", "1km", "2km", "5km"])
walk = st.selectbox("徒歩", ["指定なし", "5分", "10分", "15分"])

# ================================
# 症状判定
# ================================
detected = []
if symptom:
    for k, v in symptom_map.items():
        if k in symptom:
            detected.extend(v)
    detected = list(set(detected))

# ================================
# フィルタ
# ================================
filtered = df_all.copy()

if keyword:
    filtered = filtered[filtered[name_h].str.contains(keyword, na=False)]

if category != "すべて":
    filtered = filtered[filtered["カテゴリ"] == category]

if selected_dept != "すべて":
    filtered = filtered[filtered[dept_name].apply(
        lambda x: selected_dept in x if isinstance(x, list) else False
    )]

if detected:
    filtered = filtered[filtered[dept_name].apply(
        lambda x: any(d in x for d in detected) if isinstance(x, list) else False
    )]

# ================================
# 距離計算
# ================================
filtered["距離"] = filtered.apply(
    lambda r: haversine(user_lat, user_lon, r[lat_h], r[lon_h]),
    axis=1
)

if distance_sort:
    filtered = filtered.sort_values("距離")

if radius != "指定なし":
    r = float(radius.replace("km", ""))
    filtered = filtered[filtered["距離"] <= r]

if walk != "指定なし":
    m = int(walk.replace("分", ""))
    filtered = filtered[filtered["距離"] <= m * 4 / 60]

# ================================
# MAP
# ================================
layer_h = pdk.Layer(
    "ScatterplotLayer",
    filtered[filtered["カテゴリ"] == "病院"],
    get_position=f'[{lon_h}, {lat_h}]',
    get_color=[0, 120, 255],
    get_radius=200,
    pickable=True,
)

layer_p = pdk.Layer(
    "ScatterplotLayer",
    filtered[filtered["カテゴリ"] == "薬局"],
    get_position=f'[{lon_h}, {lat_h}]',
    get_color=[255, 0, 0],
    get_radius=200,
    pickable=True,
)

layer_u = pdk.Layer(
    "ScatterplotLayer",
    data=pd.DataFrame({"lat": [user_lat], "lon": [user_lon]}),
    get_position='[lon, lat]',
    get_color=[0, 255, 0],
    get_radius=300,
)

view = pdk.ViewState(latitude=user_lat, longitude=user_lon, zoom=14)

st.pydeck_chart(pdk.Deck(
    layers=[layer_h, layer_p, layer_u],
    initial_view_state=view,
    tooltip={
        "text": "{カテゴリ}\n{名称}\n{住所}\n距離: {距離} km"
    }
))