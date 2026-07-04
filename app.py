import streamlit as st
import pandas as pd
import pydeck as pdk
import math

st.title("世田谷 病院・薬局検索マップ")

# ================================
# CSV読み込み
# ================================
df_hosp = pd.read_csv("hospital.csv")
df_dept = pd.read_csv("department.csv")
df_pharm = pd.read_csv("pharmacy.csv")

# ================================
# 固定位置（世田谷）
# ================================
user_lat = 35.64369547433956
user_lon = 139.64797830490818

st.success(f"現在地: {user_lat}, {user_lon}")

# ================================
# 距離計算
# ================================
def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

# ================================
# 列検出
# ================================
def col(df, candidates):
    for c in candidates:
        if c in df.columns:
            return c
    return None

# ================================
# 病院整形
# ================================
h_name = col(df_hosp, ["医療機関名称", "名称"])
h_addr = col(df_hosp, ["所在地", "住所"])
h_lat = col(df_hosp, ["緯度"])
h_lon = col(df_hosp, ["経度"])
h_code = col(df_hosp, ["医療機関コード", "医療機関ID"])

df_hosp = df_hosp[df_hosp[h_addr].str.contains("世田谷区", na=False)]

dept_code = col(df_dept, ["医療機関コード", "医療機関ID"])
dept_name = col(df_dept, ["診療科名", "標榜診療科", "診療科", "標榜科名"])

df_hosp["code"] = df_hosp[h_code].astype(str).str.zfill(10)
df_dept["code"] = df_dept[dept_code].astype(str).str.zfill(10)

dept_group = df_dept.groupby("code")[dept_name].apply(list).reset_index()

df_hosp = df_hosp.merge(dept_group, on="code", how="left")
df_hosp["カテゴリ"] = "病院"

# ================================
# 薬局整形（重要修正）
# ================================
p_name = col(df_pharm, ["薬局名称", "名称"])
p_addr = col(df_pharm, ["所在地", "住所"])
p_lat = col(df_pharm, ["緯度"])
p_lon = col(df_pharm, ["経度"])

df_pharm = df_pharm[df_pharm[p_addr].str.contains("世田谷区", na=False)]

df_pharm["カテゴリ"] = "薬局"
df_pharm["診療科"] = [[] for _ in range(len(df_pharm))]  # ←重要

df_pharm = df_pharm.rename(columns={
    p_name: h_name,
    p_addr: h_addr,
    p_lat: h_lat,
    p_lon: h_lon
})

# ================================
# 統合
# ================================
df_all = pd.concat([df_hosp, df_pharm], ignore_index=True)

# 診療科統一（重要）
df_all[dept_name] = df_all[dept_name].apply(
    lambda x: x if isinstance(x, list) else []
)

# ================================
# 症状マップ
# ================================
symptom_map = {
    "胸が痛い": ["循環器内科", "呼吸器内科"],
    "息苦しい": ["呼吸器内科"],
    "咳": ["呼吸器内科"],
    "めまい": ["脳神経内科", "耳鼻咽喉科"],
    "頭痛": ["脳神経内科"],
    "吐き気": ["消化器内科"],
    "腹痛": ["消化器内科"],
    "発熱": ["内科", "小児科"],
    "皮膚": ["皮膚科"],
    "骨折": ["整形外科"],
    "目": ["眼科"],
    "耳": ["耳鼻咽喉科"]
}

# ================================
# UI
# ================================
keyword = st.text_input("名称検索")
category = st.selectbox("カテゴリ", ["すべて", "病院", "薬局"])
symptom = st.text_input("症状検索")

# ================================
# 症状判定
# ================================
detected = []
if symptom:
    for k, v in symptom_map.items():
        if k in symptom:
            detected.extend(v)
    detected = list(set(detected))

    if detected:
        st.success("推奨診療科: " + ", ".join(detected))

# ================================
# フィルタ
# ================================
filtered = df_all.copy()

if keyword:
    filtered = filtered[filtered[h_name].str.contains(keyword, na=False)]

if category != "すべて":
    filtered = filtered[filtered["カテゴリ"] == category]

if detected:
    filtered = filtered[filtered[dept_name].apply(
        lambda x: any(d in x for d in detected)
    )]

# ================================
# 距離計算
# ================================
filtered["距離"] = filtered.apply(
    lambda r: haversine(user_lat, user_lon, r[h_lat], r[h_lon]),
    axis=1
)

# ================================
# tooltip（完全修正版）
# ================================
tooltip = {
    "text": "{名称}\n{所在地}\nカテゴリ: {カテゴリ}\n距離: {距離} km"
}

# ================================
# MAP LAYER
# ================================
layer_hosp = pdk.Layer(
    "ScatterplotLayer",
    filtered[filtered["カテゴリ"] == "病院"],
    get_position=f'[{h_lon}, {h_lat}]',
    get_color='[0, 120, 255, 180]',
    get_radius=180,
    pickable=True,
)

layer_pharm = pdk.Layer(
    "ScatterplotLayer",
    filtered[filtered["カテゴリ"] == "薬局"],
    get_position=f'[{h_lon}, {h_lat}]',
    get_color='[255, 80, 80, 180]',
    get_radius=180,
    pickable=True,
)

layer_user = pdk.Layer(
    "ScatterplotLayer",
    data=pd.DataFrame({"lat":[user_lat], "lon":[user_lon]}),
    get_position='[lon, lat]',
    get_color='[0,255,0,255]',
    get_radius=300
)

# ================================
# MAP表示
# ================================
st.pydeck_chart(pdk.Deck(
    layers=[layer_hosp, layer_pharm, layer_user],
    initial_view_state=pdk.ViewState(
        latitude=user_lat,
        longitude=user_lon,
        zoom=14
    ),
    tooltip=tooltip
))