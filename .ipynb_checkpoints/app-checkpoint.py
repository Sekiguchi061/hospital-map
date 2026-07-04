import streamlit as st
import pandas as pd
import pydeck as pdk
import math

st.title("世田谷 病院・薬局検索マップ（診療科・症状・距離対応）")

# --- CSV アップロード ---
facility_hosp_file = st.file_uploader("病院（施設票）CSVをアップロード", type="csv")
dept_file = st.file_uploader("病院（診療科・診療時間票）CSVをアップロード", type="csv")
facility_pharm_file = st.file_uploader("薬局（施設票）CSVをアップロード", type="csv")

# ================================
# 現在地を固定（世田谷）
# ================================
user_lat = 35.64369547433956
user_lon = 139.64797830490818

st.success(f"現在地（固定値）：{user_lat}, {user_lon}")
location = True  # 距離計算を有効にするためのダミー

# ================================
# 距離計算（Haversine）
# ================================
def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


if facility_hosp_file and dept_file and facility_pharm_file:

    # ================================
    # 共通：列名検出関数
    # ================================
    def detect_column(df, candidates):
        for c in candidates:
            if c in df.columns:
                return c
        return None

    # ================================
    # 病院（施設票）
    # ================================
    df_hosp = pd.read_csv(facility_hosp_file)

    name_col = detect_column(df_hosp, ["医療機関名称", "名称"])
    address_col = detect_column(df_hosp, ["所在地", "住所"])
    lat_col = detect_column(df_hosp, ["緯度"])
    lon_col = detect_column(df_hosp, ["経度"])
    code_col_hosp = detect_column(df_hosp, ["医療機関コード", "医療機関ID"])

    df_hosp = df_hosp[df_hosp[address_col].str.contains("世田谷区", na=False)]

    # ================================
    # 病院（診療科票）
    # ================================
    df_dept = pd.read_csv(dept_file)

    dept_code_col = detect_column(df_dept, ["医療機関コード", "医療機関ID"])
    dept_name_col = detect_column(df_dept, ["診療科名", "標榜診療科", "診療科", "標榜科名"])

    df_hosp["code_norm"] = df_hosp[code_col_hosp].astype(str).str.zfill(10)
    df_dept["code_norm"] = df_dept[dept_code_col].astype(str).str.zfill(10)

    df_dept_grouped = df_dept.groupby("code_norm")[dept_name_col].apply(list).reset_index()
    df_hosp = pd.merge(df_hosp, df_dept_grouped, on="code_norm", how="left")
    df_hosp["カテゴリ"] = "病院"

    # ================================
    # 薬局（施設票）
    # ================================
    df_pharm = pd.read_csv(facility_pharm_file)

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
    # 病院 + 薬局 を統合
    # ================================
    df_all = pd.concat([df_hosp, df_pharm], ignore_index=True)

    # ================================
    # 症状 → 診療科 マッピング
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
        "視界がぼやける": ["眼科"],
        "耳が痛い": ["耳鼻咽喉科"],
        "聞こえにくい": ["耳鼻咽喉科"],
    }

    # ================================
    # 検索フォーム
    # ================================
    keyword = st.text_input("名称で検索")
    category = st.selectbox("カテゴリ選択", ["すべて", "病院", "薬局"])

    all_depts = sorted({d for lst in df_hosp[dept_name_col].dropna() for d in lst})
    selected_dept = st.selectbox("診療科で絞り込み（病院のみ）", ["すべて"] + all_depts)

    symptom_input = st.text_input("症状で検索（例：胸が痛い、めまい、子どもが熱 など）")

    distance_sort = st.checkbox("現在地から近い順に並べる")
    radius_km = st.selectbox("半径で絞り込み", ["指定なし", "0.5km", "1km", "2km", "5km"])
    walk_filter = st.selectbox("徒歩圏内で絞り込み", ["指定なし", "徒歩5分", "徒歩10分", "徒歩15分"])

    # ================================
    # 症状 → 診療科 推定
    # ================================
    detected_depts = []
    if symptom_input:
        for key, depts in symptom_to_dept.items():
            if key in symptom_input:
                detected_depts.extend(depts)

        detected_depts = list(set(detected_depts))

        if detected_depts:
            st.success(f"推奨される診療科: {', '.join(detected_depts)}")
        else:
            st.warning("該当する診療科が見つかりませんでした。")

    # ================================
    # フィルタリング
    # ================================
    filtered = df_all.copy()

    if keyword:
        filtered = filtered[filtered[name_col].str.contains(keyword, na=False)]

    if category != "すべて":
        filtered = filtered[filtered["カテゴリ"] == category]

    if selected_dept != "すべて":
        filtered = filtered[filtered[dept_name_col].apply(
            lambda x: selected_dept in x if isinstance(x, list) else False
        )]

    if detected_depts:
        filtered = filtered[filtered[dept_name_col].apply(
            lambda x: any(d in x for d in detected_depts) if isinstance(x, list) else False
        )]

    # ================================
    # 距離計算
    # ================================
    if location:
        filtered["距離_km"] = filtered.apply(
            lambda row: haversine(user_lat, user_lon, row[lat_col], row[lon_col]),
            axis=1
        )

        if distance_sort:
            filtered = filtered.sort_values("距離_km")

        if radius_km != "指定なし":
            r = float(radius_km.replace("km", ""))
            filtered = filtered[filtered["距離_km"] <= r]

        if walk_filter != "指定なし":
            minutes = int(walk_filter.replace("徒歩", "").replace("分", ""))
            walk_km = minutes * (4 / 60)
            filtered = filtered[filtered["距離_km"] <= walk_km]

    # ================================
    # 地図レイヤー（病院＝青、薬局＝赤）
    # ================================
    layer_hosp = pdk.Layer(
        "ScatterplotLayer",
        filtered[filtered["カテゴリ"] == "病院"],
        get_position=f'[{lon_col}, {lat_col}]',
        get_color='[0, 128, 255, 160]',
        get_radius=200,
        pickable=True,
    )

    layer_pharm = pdk.Layer(
        "ScatterplotLayer",
        filtered[filtered["カテゴリ"] == "薬局"],
        get_position=f'[{lon_col}, {lat_col}]',
        get_color='[255, 0, 0, 160]',
        get_radius=200,
        pickable=True,
    )

    # ================================
    # 現在地ピン（緑）
    # ================================
    layer_user = pdk.Layer(
        "ScatterplotLayer",
        data=pd.DataFrame({
            "lat": [user_lat],
            "lon": [user_lon]
        }),
        get_position='[lon, lat]',
        get_color='[0, 255, 0, 255]',  # 緑
        get_radius=300,
        pickable=False
    )

    # ================================
    # 初期座標も固定（世田谷）
    # ================================
    view_state = pdk.ViewState(
        latitude=user_lat,
        longitude=user_lon,
        zoom=14,
        pitch=0
    )

    st.pydeck_chart(pdk.Deck(
        layers=[layer_hosp, layer_pharm, layer_user],
        initial_view_state=view_state,
        tooltip={"text": f"{{{name_col}}}\n{{{address_col}}}\nカテゴリ: {{カテゴリ}}\n診療科: {{{dept_name_col}}}\n距離: {{距離_km}} km"}
    ))

else:
    st.info("病院（施設票）CSV・診療科CSV・薬局（施設票）CSV の3つをアップロードしてください。")
