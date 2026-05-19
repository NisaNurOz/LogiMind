import math
import os
from typing import Any

import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="LogiMind",
    page_icon="🚚",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Opsiyonel: yerel test için API anahtarı (boş bırakılırsa panelden girilir)
GEMINI_API_KEY_DEFAULT = ""
GEMINI_MODEL = "gemini-2.5-flash"

DEPOT_INDEX = 0


def get_default_customers_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "id": [0, 1, 2, 3, 4, 5, 6],
            "name": [
                "Depo (Merkez)",
                "Müşteri A",
                "Müşteri B",
                "Müşteri C",
                "Müşteri D",
                "Müşteri E",
                "Müşteri F",
            ],
            "x": [0.0, 12.0, 5.0, 18.0, 8.0, 22.0, 3.0],
            "y": [0.0, 8.0, 15.0, 4.0, 20.0, 12.0, 6.0],
            "demand": [0, 4, 3, 5, 2, 6, 3],
        }
    )


def ensure_depot_first(df: pd.DataFrame) -> pd.DataFrame:
    depot = df[df["id"] == DEPOT_INDEX]
    others = df[df["id"] != DEPOT_INDEX].sort_values("id")
    return pd.concat([depot, others], ignore_index=True)


def init_customers_state() -> pd.DataFrame:
    if "customers_df" not in st.session_state:
        st.session_state.customers_df = get_default_customers_df()
    if "map_ui_ready" not in st.session_state:
        st.session_state.map_ui_ready = False
    return st.session_state.customers_df


def normalize_customers_df(df: pd.DataFrame) -> pd.DataFrame:
    cleaned = df.copy()
    cleaned["id"] = cleaned["id"].astype(int)
    cleaned["name"] = cleaned["name"].astype(str)
    cleaned["x"] = cleaned["x"].astype(float)
    cleaned["y"] = cleaned["y"].astype(float)
    cleaned["demand"] = cleaned["demand"].astype(int)
    cleaned.loc[cleaned["id"] == DEPOT_INDEX, "demand"] = 0
    cleaned.loc[cleaned["id"] == DEPOT_INDEX, "name"] = "Depo (Merkez)"
    return ensure_depot_first(cleaned)


def parse_uploaded_csv(uploaded_file) -> pd.DataFrame:
    raw = pd.read_csv(uploaded_file)
    renamed: dict[str, str] = {}
    for col in raw.columns:
        key = col.strip().lower().replace(" ", "_")
        if key in ("x", "x_koordinat", "x_koordinatı"):
            renamed[col] = "x"
        elif key in ("y", "y_koordinat", "y_koordinatı"):
            renamed[col] = "y"
        elif key in ("demand", "talep", "paket", "paket_talebi"):
            renamed[col] = "demand"
        elif key in ("name", "ad", "musteri", "müşteri", "customer"):
            renamed[col] = "name"
    raw = raw.rename(columns=renamed)

    missing = {"x", "y", "demand"} - set(raw.columns)
    if missing:
        raise ValueError(
            f"CSV dosyasında şu sütunlar eksik: {', '.join(sorted(missing))}. "
            "Gerekli sütunlar: X, Y, Demand"
        )

    depot = pd.DataFrame(
        [{"id": 0, "name": "Depo (Merkez)", "x": 0.0, "y": 0.0, "demand": 0}]
    )
    rows: list[dict[str, Any]] = []
    for i, (_, row) in enumerate(raw.iterrows(), start=1):
        x_val = float(row["x"])
        y_val = float(row["y"])
        demand_val = int(row["demand"])
        if "name" in raw.columns and pd.notna(row["name"]):
            name_val = str(row["name"])
        else:
            name_val = f"Müşteri {i}"
        rows.append(
            {"id": i, "name": name_val, "x": x_val, "y": y_val, "demand": demand_val}
        )

    if not rows:
        raise ValueError("CSV dosyasında en az bir müşteri satırı olmalıdır.")

    return normalize_customers_df(pd.concat([depot, pd.DataFrame(rows)], ignore_index=True))


def clear_map_cache() -> None:
    for key in ("map_click_sig", "folium_cache_sig", "folium_cache_map"):
        st.session_state.pop(key, None)


def build_export_report(
    result: dict[str, Any],
    num_vehicles: int,
    vehicle_capacity: int,
    traffic_multiplier: float,
    ai_report: str | None,
) -> str:
    lines = [
        "LOGIMIND — ROTA OPTİMİZASYON RAPORU",
        "=" * 52,
        "",
        "ÖZET METRİKLER",
        "-" * 52,
        f"Toplam Mesafe (km)      : {result['total_distance_km']:.2f}",
        f"Trafik / Maliyet Çarpanı: {traffic_multiplier:.1f}",
        f"Tasarruf Oranı (%)      : {result['savings_pct']:.1f}",
        f"Naif Plan Mesafesi (km) : {result['naive_distance_km']:.2f}",
        f"Araç Sayısı             : {num_vehicles}",
        f"Araç Kapasitesi         : {vehicle_capacity}",
        "",
        "ARAÇ ROTALARI",
        "-" * 52,
    ]
    for route in result["routes"]:
        sequence = " → ".join(["Depo"] + route["names"] + ["Depo"])
        lines.append(f"Araç {route['vehicle_id']}:")
        lines.append(f"  Güzergâh : {sequence}")
        lines.append(
            f"  Mesafe   : {route['distance']:.2f} km | "
            f"Yük: {route['load']}/{vehicle_capacity}"
        )
        lines.append("")

    lines.extend(
        [
            "GEMİNİ — STRATEJİK KARAR DESTEK RAPORU",
            "-" * 52,
            ai_report
            if ai_report
            else "(Rapor oluşturulmadı — API anahtarı girilmedi veya hata oluştu.)",
        ]
    )
    return "\n".join(lines)


def apply_map_click(
    df: pd.DataFrame, customer_id: int, x: float, y: float
) -> pd.DataFrame:
    updated = df.copy()
    mask = updated["id"] == customer_id
    updated.loc[mask, "x"] = round(float(x), 2)
    updated.loc[mask, "y"] = round(float(y), 2)
    return normalize_customers_df(updated)


def df_signature(df: pd.DataFrame) -> str:
    return df[["id", "x", "y", "name", "demand"]].to_csv(index=False)


def build_folium_map(df: pd.DataFrame):
    import folium

    pad = 3.0
    min_x, max_x = df["x"].min() - pad, df["x"].max() + pad
    min_y, max_y = df["y"].min() - pad, df["y"].max() + pad
    center_y = (min_y + max_y) / 2
    center_x = (min_x + max_x) / 2

    fmap = folium.Map(
        location=[center_y, center_x],
        zoom_start=12,
        tiles="CartoDB positron",
        attr="CartoDB",
    )
    bounds = [[min_y, min_x], [max_y, max_x]]
    fmap.fit_bounds(bounds)

    for _, row in df.iterrows():
        is_depot = int(row["id"]) == DEPOT_INDEX
        color = "#b91c1c" if is_depot else "#2563eb"
        radius = 12 if is_depot else 9
        folium.CircleMarker(
            location=[row["y"], row["x"]],
            radius=radius,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.85,
            popup=f"{row['name']}<br>X: {row['x']:.1f}, Y: {row['y']:.1f}",
            tooltip=row["name"],
        ).add_to(fmap)

    return fmap


def get_cached_folium_map(df: pd.DataFrame):
    signature = df_signature(df)
    if st.session_state.get("folium_cache_sig") != signature:
        st.session_state.folium_cache_sig = signature
        st.session_state.folium_cache_map = build_folium_map(df)
    return st.session_state.folium_cache_map


def render_fast_map_preview(df: pd.DataFrame, height: int = 480) -> None:
    preview = df.assign(lat=df["y"], lon=df["x"])
    st.map(preview[["lat", "lon"]], height=height, zoom=None)

SCALE = 100  # OR-Tools tamsayı mesafe matrisi için ölçek
ROUTE_COLORS = ["#2563eb", "#ea580c", "#16a34a", "#dc2626", "#9333ea"]


def euclidean_distance(
    x1: float, y1: float, x2: float, y2: float, multiplier: float = 1.0
) -> float:
    return math.hypot(x2 - x1, y2 - y1) * multiplier


def build_distance_matrix(
    df: pd.DataFrame, traffic_multiplier: float = 1.0
) -> list[list[int]]:
    n = len(df)
    matrix: list[list[int]] = []
    for i in range(n):
        row: list[int] = []
        for j in range(n):
            if i == j:
                row.append(0)
            else:
                dist = euclidean_distance(
                    df.iloc[i]["x"],
                    df.iloc[i]["y"],
                    df.iloc[j]["x"],
                    df.iloc[j]["y"],
                    traffic_multiplier,
                )
                row.append(int(round(dist * SCALE)))
        matrix.append(row)
    return matrix


def route_distance(
    df: pd.DataFrame,
    stops: list[int],
    traffic_multiplier: float = 1.0,
) -> float:
    if len(stops) < 2:
        return 0.0
    total = 0.0
    for a, b in zip(stops, stops[1:]):
        row_a = df[df["id"] == a].iloc[0]
        row_b = df[df["id"] == b].iloc[0]
        total += euclidean_distance(
            row_a["x"],
            row_a["y"],
            row_b["x"],
            row_b["y"],
            traffic_multiplier,
        )
    return total


def solve_cvrp(
    df: pd.DataFrame,
    num_vehicles: int,
    vehicle_capacity: int,
    traffic_multiplier: float,
) -> dict[str, Any]:
    from ortools.constraint_solver import pywrapcp, routing_enums_pb2

    demands = df["demand"].astype(int).tolist()
    distance_matrix = build_distance_matrix(df, traffic_multiplier=1.0)

    manager = pywrapcp.RoutingIndexManager(
        len(distance_matrix), num_vehicles, DEPOT_INDEX
    )
    routing = pywrapcp.RoutingModel(manager)

    def distance_callback(from_index: int, to_index: int) -> int:
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return distance_matrix[from_node][to_node]

    transit_callback_index = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    def demand_callback(from_index: int) -> int:
        return demands[manager.IndexToNode(from_index)]

    demand_callback_index = routing.RegisterUnaryTransitCallback(demand_callback)
    routing.AddDimensionWithVehicleCapacity(
        demand_callback_index,
        0,
        [vehicle_capacity] * num_vehicles,
        True,
        "Capacity",
    )

    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )
    search_parameters.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    )
    search_parameters.time_limit.FromSeconds(5)

    solution = routing.SolveWithParameters(search_parameters)

    if solution is None:
        return {
            "success": False,
            "routes": [],
            "total_distance_km": 0.0,
            "savings_pct": 0.0,
        }

    routes: list[dict[str, Any]] = []
    total_distance = 0.0

    for vehicle_id in range(num_vehicles):
        index = routing.Start(vehicle_id)
        customer_stops: list[int] = []
        route_load = 0

        while not routing.IsEnd(index):
            node = manager.IndexToNode(index)
            if node != DEPOT_INDEX:
                customer_stops.append(node)
                route_load += demands[node]
            index = solution.Value(routing.NextVar(index))

        if not customer_stops:
            continue

        full_stops = [DEPOT_INDEX] + customer_stops + [DEPOT_INDEX]
        leg_distance = route_distance(df, full_stops, traffic_multiplier)
        total_distance += leg_distance
        route_names = [df[df["id"] == n].iloc[0]["name"] for n in customer_stops]

        routes.append(
            {
                "vehicle_id": vehicle_id + 1,
                "stops": full_stops,
                "customers": customer_stops,
                "names": route_names,
                "load": route_load,
                "distance": leg_distance,
            }
        )
    naive_distance = compute_naive_baseline(
        df, num_vehicles, vehicle_capacity, traffic_multiplier
    )
    savings_pct = 0.0
    if naive_distance > 0:
        savings_pct = max(0.0, (naive_distance - total_distance) / naive_distance * 100)

    return {
        "success": True,
        "routes": routes,
        "total_distance_km": total_distance,
        "savings_pct": savings_pct,
        "naive_distance_km": naive_distance,
    }


def compute_naive_baseline(
    df: pd.DataFrame,
    num_vehicles: int,
    vehicle_capacity: int,
    traffic_multiplier: float,
) -> float:
    """Kapasiteye göre sırayla atama; her araç müşterilere girdi sırasıyla gider."""
    customer_indices = [i for i in df["id"] if i != DEPOT_INDEX]
    vehicle_loads = [0] * num_vehicles
    vehicle_routes: list[list[int]] = [[] for _ in range(num_vehicles)]

    for idx in customer_indices:
        demand = int(df[df["id"] == idx].iloc[0]["demand"])
        assigned = False
        for v in range(num_vehicles):
            if vehicle_loads[v] + demand <= vehicle_capacity:
                vehicle_routes[v].append(idx)
                vehicle_loads[v] += demand
                assigned = True
                break
        if not assigned:
            vehicle_routes[0].append(idx)
            vehicle_loads[0] += demand

    total = 0.0
    for stops in vehicle_routes:
        if not stops:
            continue
        full = [DEPOT_INDEX] + stops + [DEPOT_INDEX]
        total += route_distance(df, full, traffic_multiplier)
    return total


def resolve_api_key(sidebar_key: str) -> str:
    if sidebar_key and sidebar_key.strip():
        return sidebar_key.strip()
    if GEMINI_API_KEY_DEFAULT:
        return GEMINI_API_KEY_DEFAULT.strip()
    env_key = os.environ.get("GEMINI_API_KEY", "")
    if env_key:
        return env_key.strip()
    try:
        return st.secrets.get("GEMINI_API_KEY", "")
    except (AttributeError, FileNotFoundError, KeyError):
        return ""


def format_optimization_payload(
    result: dict[str, Any],
    num_vehicles: int,
    vehicle_capacity: int,
    traffic_multiplier: float,
) -> str:
    route_lines = []
    for route in result["routes"]:
        sequence = " → ".join(["Depo"] + route["names"] + ["Depo"])
        route_lines.append(
            f"- Araç {route['vehicle_id']}: {sequence} "
            f"(mesafe: {route['distance']:.2f} km, yük: {route['load']}/{vehicle_capacity})"
        )

    return (
        f"Toplam mesafe (trafik çarpanı ×{traffic_multiplier:.1f} dahil): "
        f"{result['total_distance_km']:.2f} km\n"
        f"Araç sayısı: {num_vehicles}\n"
        f"Araç kapasitesi: {vehicle_capacity}\n"
        f"Trafik / maliyet çarpanı: {traffic_multiplier:.1f}\n"
        f"Algoritmik tasarruf oranı: %{result['savings_pct']:.1f}\n"
        f"Naif plan mesafesi: {result['naive_distance_km']:.2f} km\n"
        f"Araç rotaları:\n" + "\n".join(route_lines)
    )


def generate_strategic_report(
    api_key: str,
    result: dict[str, Any],
    num_vehicles: int,
    vehicle_capacity: int,
    traffic_multiplier: float,
) -> str:
    optimization_data = format_optimization_payload(
        result, num_vehicles, vehicle_capacity, traffic_multiplier
    )

    prompt = (
        "Sen LogiMind lojistik optimizasyon sisteminin kıdemli yapay zeka danışmanısın. "
        "Önünde, matematiksel modellemesi bitmiş bir rota çözümünün şu verileri var:\n\n"
        f"{optimization_data}\n\n"
        "Bu verilere bakarak, lojistik operasyon yöneticisine hitaben Türkçe, profesyonel "
        've kısa bir "Stratejik Yönetici Özeti" ve 3 maddelik operasyonel risk/maliyet '
        "öneri raporu hazırla."
    )

    import google.generativeai as genai

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(GEMINI_MODEL)
    response = model.generate_content(prompt)
    if not response.text:
        raise ValueError("Gemini boş yanıt döndürdü.")
    return response.text.strip()


def plot_routes_visualization(
    df: pd.DataFrame,
    routes: list[dict[str, Any]],
):
    """Depo, müşteri noktaları ve araç rotalarını X–Y düzleminde çizer."""
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(10, 7))

    customers = df[df["id"] != DEPOT_INDEX]
    depot_row = df[df["id"] == DEPOT_INDEX].iloc[0]

    ax.scatter(
        customers["x"],
        customers["y"],
        c="#334155",
        s=140,
        zorder=4,
        edgecolors="white",
        linewidths=1.2,
        label="Müşteriler",
    )
    ax.scatter(
        [depot_row["x"]],
        [depot_row["y"]],
        c="#b91c1c",
        s=320,
        marker="s",
        zorder=5,
        edgecolors="white",
        linewidths=1.5,
        label="Depo (Merkez)",
    )

    for _, row in customers.iterrows():
        label = str(row["name"]).replace("Müşteri ", "")
        ax.annotate(
            label,
            (row["x"], row["y"]),
            textcoords="offset points",
            xytext=(6, 6),
            fontsize=9,
            color="#0f172a",
        )

    ax.annotate(
        "Depo",
        (depot_row["x"], depot_row["y"]),
        textcoords="offset points",
        xytext=(6, -12),
        fontsize=10,
        fontweight="bold",
        color="#b91c1c",
    )

    for route, color in zip(routes, ROUTE_COLORS):
        xs = [df.loc[df["id"] == node, "x"].iloc[0] for node in route["stops"]]
        ys = [df.loc[df["id"] == node, "y"].iloc[0] for node in route["stops"]]
        ax.plot(
            xs,
            ys,
            color=color,
            linewidth=2.5,
            marker="o",
            markersize=7,
            markerfacecolor="white",
            markeredgewidth=1.5,
            markeredgecolor=color,
            zorder=3,
            label=f"Araç {route['vehicle_id']}",
            alpha=0.9,
        )

    ax.set_xlabel("X koordinatı")
    ax.set_ylabel("Y koordinatı")
    ax.set_title("LogiMind — Optimize Araç Rotaları")
    ax.grid(True, linestyle="--", alpha=0.35)
    ax.legend(loc="upper left", framealpha=0.95)
    ax.set_aspect("equal", adjustable="datalim")
    fig.tight_layout()
    return fig


@st.fragment
def render_interactive_map(
    customers_df: pd.DataFrame,
    map_target_id: int,
) -> None:
    from streamlit_folium import st_folium

    folium_map = get_cached_folium_map(customers_df)
    map_response = st_folium(
        folium_map,
        width=None,
        height=480,
        returned_objects=["last_clicked"],
        key="customer_location_map",
    )

    if map_response and map_response.get("last_clicked"):
        click = map_response["last_clicked"]
        if click and click.get("lng") is not None and click.get("lat") is not None:
            click_sig = (round(click["lng"], 3), round(click["lat"], 3))
            if st.session_state.get("map_click_sig") != click_sig:
                st.session_state.map_click_sig = click_sig
                updated = apply_map_click(
                    customers_df,
                    int(map_target_id),
                    click["lng"],
                    click["lat"],
                )
                st.session_state.customers_df = updated
                if "folium_cache_sig" in st.session_state:
                    del st.session_state["folium_cache_sig"]
                if "folium_cache_map" in st.session_state:
                    del st.session_state["folium_cache_map"]
                target_name = updated.loc[updated["id"] == map_target_id, "name"].iloc[0]
                st.toast(
                    f"{target_name} konumu güncellendi: "
                    f"X={click['lng']:.1f}, Y={click['lat']:.1f}"
                )
                st.rerun()


# --- Arayüz ---
st.title("LogiMind — Rota Optimizasyonu")
st.caption("Kapasiteli Araç Rotalama (CVRP) · OR-Tools")

with st.sidebar:
    st.header("Senaryo Parametreleri")
    num_vehicles = st.slider("Araç Sayısı", min_value=1, max_value=5, value=2)
    vehicle_capacity = st.number_input(
        "Araç Kapasitesi",
        min_value=1,
        max_value=100,
        value=15,
        step=1,
    )
    traffic_multiplier = st.slider(
        "Trafik / Maliyet Çarpanı",
        min_value=1.0,
        max_value=2.0,
        value=1.0,
        step=0.1,
    )
    st.divider()
    st.subheader("Müşteri Listesi (CSV)")
    uploaded_csv = st.file_uploader(
        "CSV dosyası yükle",
        type=["csv"],
        help="Zorunlu sütunlar: X, Y, Demand. İsteğe bağlı: Name",
    )
    if uploaded_csv is not None:
        csv_key = f"{uploaded_csv.name}-{uploaded_csv.size}"
        if st.session_state.get("loaded_csv_key") != csv_key:
            try:
                st.session_state.customers_df = parse_uploaded_csv(uploaded_csv)
                st.session_state.loaded_csv_key = csv_key
                st.session_state.map_ui_ready = False
                clear_map_cache()
                st.success(
                    f"{len(st.session_state.customers_df) - 1} müşteri yüklendi."
                )
                st.rerun()
            except Exception as exc:
                st.error(f"CSV okunamadı: {exc}")
    st.divider()
    st.subheader("Gemini AI")
    gemini_api_key_input = st.text_input(
        "Gemini API Anahtarı",
        type="password",
        placeholder="AIza...",
        help="Anahtarınız yalnızca bu oturumda kullanılır; kaydedilmez.",
    )
    st.caption(f"Model: `{GEMINI_MODEL}`")

customers_df = init_customers_state()

st.header("Müşteri & Konum Yönetimi")
col_data, col_map = st.columns([1, 1.15], gap="large")

with col_data:
    st.subheader("Müşteri Verisi")
    st.caption("Tabloda X, Y ve talep değerlerini doğrudan düzenleyebilirsiniz.")
    edited_df = st.data_editor(
        customers_df,
        column_config={
            "id": st.column_config.NumberColumn("ID", disabled=True, width="small"),
            "name": st.column_config.TextColumn("Ad", width="medium"),
            "x": st.column_config.NumberColumn(
                "X", min_value=-200.0, max_value=200.0, step=0.5, format="%.1f"
            ),
            "y": st.column_config.NumberColumn(
                "Y", min_value=-200.0, max_value=200.0, step=0.5, format="%.1f"
            ),
            "demand": st.column_config.NumberColumn(
                "Talep", min_value=0, max_value=50, step=1
            ),
        },
        hide_index=True,
        num_rows="dynamic",
        height=420,
        width="stretch",
        key="customers_data_editor",
    )
    customers_df = normalize_customers_df(edited_df)
    st.session_state.customers_df = customers_df

    btn_col1, btn_col2 = st.columns(2)
    with btn_col1:
        if st.button("Varsayılan veriye dön", width="stretch"):
            st.session_state.customers_df = get_default_customers_df()
            st.session_state.pop("loaded_csv_key", None)
            st.session_state.pop("export_report", None)
            clear_map_cache()
            st.rerun()
    with btn_col2:
        total_demand_preview = int(
            customers_df.loc[customers_df["id"] != DEPOT_INDEX, "demand"].sum()
        )
        st.metric("Toplam talep", total_demand_preview)

with col_map:
    st.subheader("Konum Haritası")
    name_by_id = dict(zip(customers_df["id"], customers_df["name"]))
    map_target_id = st.selectbox(
        "Haritadan konum atanacak nokta",
        options=customers_df["id"].tolist(),
        format_func=lambda cid: name_by_id.get(cid, str(cid)),
        help="Haritada bir yere tıklayın; seçili noktanın X/Y koordinatları güncellenir.",
    )
    st.caption(
        "Haritada istediğiniz yere tıklayın. Seçili müşteri veya depo otomatik güncellenir."
    )

    if not st.session_state.map_ui_ready:
        render_fast_map_preview(customers_df, height=480)
        st.session_state.map_ui_ready = True
        st.rerun()
    else:
        render_interactive_map(customers_df, int(map_target_id))

st.divider()
optimize = st.button("Rotayı Optimize Et", type="primary")

if optimize:
    customers_df = st.session_state.customers_df
    total_demand = int(customers_df.loc[customers_df["id"] != DEPOT_INDEX, "demand"].sum())
    max_capacity = num_vehicles * vehicle_capacity

    if total_demand > max_capacity:
        st.error(
            f"Toplam talep ({total_demand}) mevcut filo kapasitesini "
            f"({max_capacity}) aşıyor. Araç sayısını veya kapasiteyi artırın."
        )
    else:
        result = solve_cvrp(
            customers_df,
            num_vehicles=num_vehicles,
            vehicle_capacity=int(vehicle_capacity),
            traffic_multiplier=traffic_multiplier,
        )

        if not result["success"]:
            st.warning("Çözüm bulunamadı. Parametreleri kontrol edin.")
        else:
            st.success("Rota optimizasyonu tamamlandı.")

            st.subheader("Rota Haritası (Matplotlib)")
            route_fig = plot_routes_visualization(customers_df, result["routes"])
            st.pyplot(route_fig, clear_figure=True)

            m1, m2, m3 = st.columns(3)
            m1.metric(
                "Toplam Mesafe (km)",
                f"{result['total_distance_km']:.2f}",
                help=f"Trafik çarpanı: ×{traffic_multiplier:.1f}",
            )
            m2.metric(
                "Algoritmik Tasarruf",
                f"%{result['savings_pct']:.1f}",
                help="Optimize rota vs. sıralı (naif) atama karşılaştırması",
            )
            m3.metric(
                "Naif Plan Mesafesi",
                f"{result['naive_distance_km']:.2f} km",
                delta=f"-{result['naive_distance_km'] - result['total_distance_km']:.2f} km",
                delta_color="inverse",
            )

            st.subheader("Araç Rotaları")
            for route in result["routes"]:
                sequence = " → ".join(
                    ["Depo"]
                    + [customers_df[customers_df["id"] == c].iloc[0]["name"] for c in route["customers"]]
                    + ["Depo"]
                )
                with st.expander(
                    f"Araç {route['vehicle_id']} · "
                    f"{route['distance']:.2f} km · Yük: {route['load']}/{vehicle_capacity}",
                    expanded=True,
                ):
                    st.write(f"**Güzergâh:** {sequence}")
                    st.write(
                        f"**Müşteri sırası:** {', '.join(route['names'])}"
                    )

            api_key = resolve_api_key(gemini_api_key_input)
            st.markdown("### 🧠 LogiMind AI - Stratejik Karar Destek Raporu")

            ai_report_text: str | None = None
            if not api_key:
                st.warning(
                    "Gemini raporu için sol panelden API anahtarınızı girin "
                    "veya `GEMINI_API_KEY_DEFAULT` / `GEMINI_API_KEY` ortam değişkenini tanımlayın."
                )
            else:
                with st.spinner("LogiMind AI stratejik raporu hazırlanıyor..."):
                    try:
                        ai_report_text = generate_strategic_report(
                            api_key=api_key,
                            result=result,
                            num_vehicles=num_vehicles,
                            vehicle_capacity=int(vehicle_capacity),
                            traffic_multiplier=traffic_multiplier,
                        )
                        st.info(ai_report_text)
                    except Exception as exc:
                        st.error(
                            f"Gemini raporu oluşturulamadı: {exc}. "
                            "API anahtarınızı ve model erişiminizi kontrol edin."
                        )

            st.session_state.export_report = build_export_report(
                result=result,
                num_vehicles=num_vehicles,
                vehicle_capacity=int(vehicle_capacity),
                traffic_multiplier=traffic_multiplier,
                ai_report=ai_report_text,
            )

            st.divider()
            st.download_button(
                label="Sonuçları Metin (.txt) Olarak İndir",
                data=st.session_state.export_report,
                file_name="logimind_optimizasyon_raporu.txt",
                mime="text/plain",
                type="primary",
                width="stretch",
            )
else:
    st.info(
        "Sol panelden senaryo parametrelerini ayarlayın, müşteri konumlarını tablo veya "
        "haritadan düzenleyin, ardından **Rotayı Optimize Et** ile CVRP çözümünü çalıştırın."
    )
    if st.session_state.get("export_report"):
        st.divider()
        st.download_button(
            label="Sonuçları Metin (.txt) Olarak İndir",
            data=st.session_state.export_report,
            file_name="logimind_optimizasyon_raporu.txt",
            mime="text/plain",
            type="primary",
            width="stretch",
        )
