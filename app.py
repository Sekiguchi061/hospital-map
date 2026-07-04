import streamlit as st
import pandas as pd
import pydeck as pdk
import math

st.title("世田谷 病院・薬局検索マップ（診療科・症状・距離対応）")

# ================================
# CSV読み込み
# ================================
df_hosp = pd.read_csv("hospital.csv")
df_dept = pd.read_csv("department.csv")
df_pharm = pd.read_csv("pharmacy.csv")

# ================================
# 現在地（固定）
# ================================
user_lat = 35.64369547433956
user_lon = 139.64797830490818

st.success(f"現在地（固定）：{user_lat}, {user_lon}")
location = True

# ================================
# 距離計算
# ================================
def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

# ================================
# 列名検出
# ================================
def detect_column(df, candidates):
    for c in candidates:
        if c in df.columns:
            return c
    return None

# ================================
# 病院データ処理
# ================================
name_col = detect_column(df_hosp, ["医療機関名称", "名称"])
address_col = detect_column(df_hosp, ["所在地", "住所"])
lat_col = detect_column(df_hosp, ["緯度"])
lon_col = detect_column(df_hosp, ["経度"])
code_col_hosp = detect_column(df_hosp, ["医療機関コード", "医療機関ID"])

df_hosp = df_hosp[df_hosp[address_col].str.contains("世田谷区", na=False)]

dept_code_col = detect_column(df_dept, ["医療機関コード", "医療機関ID"])
dept_name_col = detect_column(df_dept, ["診療科名", "標榜診療科", "診療科", "標榜科名"])

df_hosp["code_norm"] = df_hosp[code_col_hosp].astype(str).str.zfill(10)
df_dept["code_norm"] = df_dept[dept_code_col].astype(str).str.zfill(10)

df_dept_grouped = df_dept.groupby("code_norm")[dept_name_col].apply(list).reset_index()
df_hosp = pd.merge(df_hosp, df_dept_grouped, on="code_norm", how="left")
df_hosp["カテゴリ"] = "病院"

# ================================
# 薬局データ処理
# ================================
name_col_p = detect_column(df_pharm, ["薬局名称", "名称"])
address_col_p = detect_column(df_pharm, ["所在地", "住所"])
lat_col_p = detect_column(df_pharm, ["緯度"])
lon_col_p = detect_column(df_pharm, ["経度"])

df_pharm = df_pharm[df_pharm[address_col_p].str.contains("世田谷区", na=False)]

df_pharm["診療科"] = None
df_pharm["カテゴリ"] = "薬局"

df_pharm = df_pharm.rename(columns={
    name_col_p: name_col,
    address_col_p: address_col,
    lat_col_p: lat_col,
    lon_col_p: lon_col
})

# ================================
# 統合
# ================================
df_all = pd.concat([df_hosp, df_pharm], ignore_index=True)

# ================================
# 症状マッピング
# ================================
symptom_to_dept = {
    "胸が痛い": ["循環器内科", "呼吸器内科"],
    "胸痛": ["循環器内科", "呼吸器内科"],
    "息苦しい": ["呼吸器内科"],
    "咳が止まらない": ["呼吸器内科"],
    "めまい": ["脳神経内科", "耳鼻咽喉科"],
    "頭痛": ["脳神経内科"],
    "吐き気": ["消化器内科"],
    "腹痛": ["消化器内科"],
    "下痢": ["消化器内科"],
    "便秘": ["消化器内科"],
    "発熱": ["内科", "小児科"],
    "子どもが熱": ["小児科"],
    "皮膚がかゆい": ["皮膚科"],
    "湿疹": ["皮膚科"],
    "骨折": ["整形外科"],
    "転んだ": ["整形外科"],
    "けが": ["整形外科"],
    "目が痛い": ["眼科"],
    "耳が痛い": ["耳鼻咽喉科"],
}

# ================================
# UI
# ================================
keyword = st.text_input("名称で検索")
category = st.selectbox("カテゴリ", ["すべて", "病院", "薬局"])

all_depts = sorted({d for lst in df_hosp[dept_name_col].dropna() for d in lst})
selected_dept = st.selectbox("診療科", ["すべて"] + all_depts)

symptom_input = st.text_input("症状検索")

distance_sort = st.checkbox("距離順")
radius_km = st.selectbox("半径", ["指定なし", "0.5km", "1km", "2km", "5km"])
walk_filter = st.selectbox("徒歩", ["指定なし", "徒歩5分", "徒歩10分", "徒歩15分"])

# ================================
# 症状判定
# ================================
detected_depts = []
if symptom_input:
    for k, v in symptom_to_dept.items():
        if k in symptom_input:
            detected_depts.extend(v)
    detected_depts = list(set(detected_depts))

    if detected_depts:
        st.success("推奨診療科: " + ", ".join(detected_depts))

# ================================
# フィルタ
# ================================
filtered = df_all.copy()

if keyword:
    filtered = filtered[filtered[name_col].str.contains(keyword, na=False)]

if category != "すべて":
    filtered = filtered[filtered["カテゴリ"] == category]

if selected_dept != "すべて":
    filtered = filtered[filtered[dept_name_col].apply(lambda x: selected_dept in x if isinstance(x, list) else False)]

if detected_depts:
    filtered = filtered[filtered[dept_name_col].apply(lambda x: any(d in x for d in detected_depts) if isinstance(x, list) else False)]

# ================================
# 距離計算
# ================================
if location:
    filtered["距離_km"] = filtered.apply(
        lambda r: haversine(user_lat, user_lon, r[lat_col], r[lon_col]),
        axis=1
    )

    if distance_sort:
        filtered = filtered.sort_values("距離_km")

    if radius_km != "指定なし":
        r = float(radius_km.replace("km", ""))
        filtered = filtered[filtered["距離_km"] <= r]

    if walk_filter != "指定なし":
        m = int(walk_filter.replace("徒歩", "").replace("分", ""))
        filtered = filtered[filtered["距離_km"] <= m * (4 / 60)]

# ================================
# 地図
# ================================
layer_hosp = pdk.Layer(
    "ScatterplotLayer",
    filtered[filtered["カテゴリ"] == "病院"],
    get_position=f'[{lon_col}, {lat_col}]',
    get_color=[0, 128, 255, 160],
    get_radius=200,
)

layer_pharm = pdk.Layer(
    "ScatterplotLayer",
    filtered[filtered["カテゴリ"] == "薬局"],
    get_position=f'[{lon_col}, {lat_col}]',
    get_color=[255, 0, 0, 160],
    get_radius=200,
)

layer_user = pdk.Layer(
    "ScatterplotLayer",
    data=pd.DataFrame({"lat": [user_lat], "lon": [user_lon]}),
    get_position='[lon, lat]',
    get_color=[0, 255, 0, 255],
    get_radius=300,
)

view_state = pdk.ViewState(
    latitude=user_lat,
    longitude=user_lon,
    zoom=14
)

st.pydeck_chart(pdk.Deck(
    layers=[layer_hosp, layer_pharm, layer_user],
    initial_view_state=view_state,
    tooltip={"text": "{name_col}\n{address_col}\nカテゴリ: {カテゴリ}\n距離: {距離_km} km"}
))