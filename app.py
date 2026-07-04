import streamlit as st
import pandas as pd
import pydeck as pdk
import math

st.set_page_config(page_title="世田谷 医療マップ", layout="wide")
st.title("世田谷 病院・薬局検索マップ")

# ================================
# CSV読み込み
# ================================
df_hosp = pd.read_csv("hospital.csv")
df_dept = pd.read_csv("department.csv")
df_pharm = pd.read_csv("pharmacy.csv")

# ================================
# 現在地
# ================================
user_lat = 35.64369547433956
user_lon = 139.64797830490818

# ================================
# 距離関数
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
def detect_column(df, candidates):
    for c in candidates:
        if c in df.columns:
            return c
    return None

# ================================
# 病院
# ================================
name_col = detect_column(df_hosp, ["医療機関名称", "名称"])
address_col = detect_column(df_hosp, ["所在地", "住所"])
lat_col = detect_column(df_hosp, ["緯度"])
lon_col = detect_column(df_hosp, ["経度"])
code_col = detect_column(df_hosp, ["医療機関コード", "医療機関ID"])

df_hosp = df_hosp.dropna(subset=[lat_col, lon_col])
df_hosp = df_hosp[df_hosp[address_col].str.contains("世田谷区", na=False)]

# 診療科
dept_code_col = detect_column(df_dept, ["医療機関コード", "医療機関ID"])
dept_name_col = detect_column(df_dept, ["診療科名", "標榜診療科", "診療科"])

df_hosp["code"] = df_hosp[code_col].astype(str).str.zfill(10)
df_dept["code"] = df_dept[dept_code_col].astype(str).str.zfill(10)

df_dept_grouped = df_dept.groupby("code")[dept_name_col].apply(list).reset_index()
df_hosp = df_hosp.merge(df_dept_grouped, on="code", how="left")

df_hosp["カテゴリ"] = "病院"

# ★ tooltip用列を必ず作る（超重要）
df_hosp["名称"] = df_hosp[name_col]
df_hosp["住所"] = df_hosp[address_col]

# ================================
# 薬局
# ================================
name_col_p = detect_column(df_pharm, ["薬局名称", "名称"])
address_col_p = detect_column(df_pharm, ["所在地", "住所"])
lat_col_p = detect_column(df_pharm, ["緯度"])
lon_col_p = detect_column(df_pharm, ["経度"])

df_pharm = df_pharm.dropna(subset=[lat_col_p, lon_col_p])
df_pharm = df_pharm[df_pharm[address_col_p].str.contains("世田谷区", na=False)]

df_pharm = df_pharm.rename(columns={
    name_col_p: "名称",
    address_col_p: "住所",
    lat_col_p: lat_col,
    lon_col_p: lon_col
})

df_pharm["カテゴリ"] = "薬局"

# ================================
# 統合
# ================================
df_all = pd.concat([df_hosp, df_pharm], ignore_index=True)

# ================================
# フィルタ
# ================================
keyword = st.text_input("名称検索")
category = st.selectbox("カテゴリ", ["すべて", "病院", "薬局"])

filtered = df_all.copy()

if keyword:
    filtered = filtered[filtered["名称"].str.contains(keyword, na=False)]

if category != "すべて":
    filtered = filtered[filtered["カテゴリ"] == category]

# ================================
# 距離計算
# ================================
filtered["距離_km"] = filtered.apply(
    lambda r: haversine(user_lat, user_lon, r[lat_col], r[lon_col]),
    axis=1
)

filtered = filtered.sort_values("距離_km")

# ================================
# レイヤー
# ================================
layer_hosp = pdk.Layer(
    "ScatterplotLayer",
    filtered[filtered["カテゴリ"] == "病院"],
    get_position=f'[{lon_col}, {lat_col}]',
    get_color='[0, 120, 255, 180]',
    get_radius=200,
    pickable=True
)

layer_pharm = pdk.Layer(
    "ScatterplotLayer",
    filtered[filtered["カテゴリ"] == "薬局"],
    get_position=f'[{lon_col}, {lat_col}]',
    get_color='[255, 80, 80, 180]',
    get_radius=200,
    pickable=True
)

layer_user = pdk.Layer(
    "ScatterplotLayer",
    data=pd.DataFrame({"lat": [user_lat], "lon": [user_lon]}),
    get_position='[lon, lat]',
    get_color='[0,255,0,255]',
    get_radius=300
)

# ================================
# ★ ここが重要：tooltip（100%表示される形）
# ================================
tooltip = {
    "html": """
    <b>名称:</b> {名称}<br/>
    <b>住所:</b> {住所}<br/>
    <b>カテゴリ:</b> {カテゴリ}<br/>
    <b>距離:</b> {距離_km:.2f} km
    """,
    "style": {
        "backgroundColor": "white",
        "color": "black"
    }
}

# ================================
# 表示
# ================================
view_state = pdk.ViewState(
    latitude=user_lat,
    longitude=user_lon,
    zoom=13
)

st.pydeck_chart(pdk.Deck(
    layers=[layer_hosp, layer_pharm, layer_user],
    initial_view_state=view_state,
    tooltip=tooltip
))

# ================================
# デバッグ表示
# ================================
st.write(filtered[["名称", "住所", "カテゴリ", "距離_km"]].head())