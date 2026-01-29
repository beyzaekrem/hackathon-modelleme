from pathlib import Path
from typing import Dict, List

import geopandas as gpd
import numpy as np
import pandas as pd
import streamlit as st
import folium
from branca.colormap import LinearColormap
from streamlit_folium import st_folium


st.set_page_config(
    page_title="Su Stresi İstihbarat Dashboard'u",
    layout="wide",
)


@st.cache_data(show_spinner=False)
def load_model1_results(geojson_path: str) -> gpd.GeoDataFrame:
    """Load Model 1 GeoJSON output as a GeoDataFrame, in WGS84 for web mapping."""
    path = Path(geojson_path)
    if not path.exists():
        raise FileNotFoundError(f"GeoJSON file not found at: {path}")

    gdf = gpd.read_file(path)
    # Ensure WGS84 for web mapping
    if gdf.crs is not None and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)
    return gdf


@st.cache_data(show_spinner=False)
def load_model2_results(geojson_path: str) -> gpd.GeoDataFrame:
    """Load Model 2 GeoJSON output as a GeoDataFrame, in WGS84 for web mapping."""
    path = Path(geojson_path)
    if not path.exists():
        raise FileNotFoundError(f"GeoJSON file not found at: {path}")

    gdf = gpd.read_file(path)
    # Ensure WGS84 for web mapping
    if gdf.crs is not None and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)
    
    # Convert all datetime/timestamp columns to strings for JSON serialization
    gdf = gdf.copy()
    for col in gdf.columns:
        if col != 'geometry':
            # Check if column is datetime/timestamp type
            if pd.api.types.is_datetime64_any_dtype(gdf[col]):
                gdf[col] = gdf[col].astype(str)
            elif gdf[col].dtype == 'object':
                # Check for datetime objects in object columns
                sample = gdf[col].dropna().head(5)
                if len(sample) > 0 and isinstance(sample.iloc[0], (pd.Timestamp, pd.DatetimeTZDtype)):
                    gdf[col] = gdf[col].astype(str)
    
    # Fix invalid geometries
    invalid_count = (~gdf.geometry.is_valid).sum()
    if invalid_count > 0:
        # Try to fix invalid geometries using buffer(0) trick
        gdf.loc[~gdf.geometry.is_valid, 'geometry'] = gdf.loc[~gdf.geometry.is_valid, 'geometry'].buffer(0)
        # Remove any geometries that are still invalid or empty
        gdf = gdf[gdf.geometry.is_valid & ~gdf.geometry.is_empty].copy()
    
    return gdf


@st.cache_data(show_spinner=False)
def load_model3_results(geojson_path: str) -> gpd.GeoDataFrame:
    """Load Model 3 GeoJSON output as a GeoDataFrame, in WGS84 for web mapping."""
    path = Path(geojson_path)
    if not path.exists():
        raise FileNotFoundError(f"GeoJSON file not found at: {path}")

    gdf = gpd.read_file(path)
    # Ensure WGS84 for web mapping
    if gdf.crs is not None and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)
    
    # Convert all datetime/timestamp columns to strings for JSON serialization
    # This is critical for folium.GeoJson to work properly
    gdf = gdf.copy()
    for col in gdf.columns:
        if col != 'geometry':
            # Check if column is datetime/timestamp type
            if pd.api.types.is_datetime64_any_dtype(gdf[col]):
                gdf[col] = gdf[col].astype(str)
            elif gdf[col].dtype == 'object':
                # Check for datetime objects in object columns
                sample = gdf[col].dropna().head(5)
                if len(sample) > 0:
                    first_val = sample.iloc[0]
                    if isinstance(first_val, (pd.Timestamp, pd.DatetimeTZDtype)) or 'timestamp' in str(type(first_val)).lower():
                        gdf[col] = gdf[col].astype(str)
    
    # Fix invalid geometries
    invalid_count = (~gdf.geometry.is_valid).sum()
    if invalid_count > 0:
        # Try to fix invalid geometries using buffer(0) trick
        gdf.loc[~gdf.geometry.is_valid, 'geometry'] = gdf.loc[~gdf.geometry.is_valid, 'geometry'].buffer(0)
        # Remove any geometries that are still invalid or empty
        gdf = gdf[gdf.geometry.is_valid & ~gdf.geometry.is_empty].copy()
    
    return gdf


def make_water_stress_map(gdf: gpd.GeoDataFrame) -> folium.Map:
    """Create a Folium map colored by final_water_stress_score."""
    score_col = "final_water_stress_score"
    if score_col not in gdf.columns:
        raise KeyError(f"Expected column '{score_col}' in GeoDataFrame.")

    # Compute map center
    bounds = gdf.total_bounds  # [minx, miny, maxx, maxy]
    center_lat = (bounds[1] + bounds[3]) / 2
    center_lon = (bounds[0] + bounds[2]) / 2

    m = folium.Map(location=[center_lat, center_lon], zoom_start=7, tiles="cartodbpositron")

    # Color scale: green (low) → yellow → red (high)
    vmin = float(gdf[score_col].min())
    vmax = float(gdf[score_col].max())
    if vmin == vmax:
        # Avoid zero-range scale; expand slightly
        vmin = vmin - 0.001
        vmax = vmax + 0.001

    colormap = LinearColormap(
        colors=["green", "yellow", "red"],
        vmin=vmin,
        vmax=vmax,
    )
    colormap.caption = "Final Su Stresi Skoru"
    colormap.add_to(m)

    # Fields to show on hover
    hover_fields = [
        "drought_norm",
        "groundwater_norm",
        "agricultural_area_pressure",
        "final_water_stress_score",
    ]
    existing_hover_fields = [f for f in hover_fields if f in gdf.columns]

    def style_function(feature):
        score = feature["properties"].get(score_col, 0)
        return {
            "fillColor": colormap(score),
            "color": "black",
            "weight": 0.5,
            "fillOpacity": 0.7,
        }

    tooltip = folium.GeoJsonTooltip(
        fields=existing_hover_fields,
        aliases=[
            "Kuraklık (norm):",
            "Yeraltı Suyu (norm):",
            "Alan basıncı:",
            "Final su stresi:",
        ][: len(existing_hover_fields)],
        localize=True,
        sticky=True,
    )

    folium.GeoJson(
        gdf,
        style_function=style_function,
        tooltip=tooltip,
        name="Water Stress",
    ).add_to(m)

    folium.LayerControl().add_to(m)

    return m


def make_urban_water_stress_map(gdf: gpd.GeoDataFrame) -> folium.Map:
    """Create a Folium map colored by urban_water_stress_score."""
    score_col = "urban_water_stress_score"
    if score_col not in gdf.columns:
        raise KeyError(f"Expected column '{score_col}' in GeoDataFrame.")

    # Convert all datetime/timestamp columns to strings for JSON serialization
    # This is critical for folium.GeoJson to work properly
    gdf = gdf.copy()
    for col in gdf.columns:
        if col != 'geometry':
            # Check if column is datetime/timestamp type
            if pd.api.types.is_datetime64_any_dtype(gdf[col]):
                gdf[col] = gdf[col].astype(str)
            elif gdf[col].dtype == 'object':
                # Check for datetime objects in object columns
                sample = gdf[col].dropna().head(5)
                if len(sample) > 0:
                    first_val = sample.iloc[0]
                    if isinstance(first_val, (pd.Timestamp, pd.DatetimeTZDtype)) or 'timestamp' in str(type(first_val)).lower():
                        gdf[col] = gdf[col].astype(str)

    # Compute map center
    bounds = gdf.total_bounds  # [minx, miny, maxx, maxy]
    center_lat = (bounds[1] + bounds[3]) / 2
    center_lon = (bounds[0] + bounds[2]) / 2

    m = folium.Map(location=[center_lat, center_lon], zoom_start=7, tiles="cartodbpositron")

    # Color scale: green (low) → yellow → red (high)
    vmin = float(gdf[score_col].min())
    vmax = float(gdf[score_col].max())
    all_zero = (vmin == 0 and vmax == 0)
    
    if vmin == vmax:
        # Avoid zero-range scale; expand slightly
        if all_zero:
            # If all values are 0, use a small range to show gray/uncolored
            vmin = -0.001
            vmax = 0.001
        else:
            vmin = vmin - 0.001
            vmax = vmax + 0.001

    colormap = LinearColormap(
        colors=["green", "yellow", "red"],
        vmin=vmin,
        vmax=vmax,
    )
    colormap.caption = "Kentsel Su Stresi Skoru"
    colormap.add_to(m)

    # Fields to show on hover
    # Try to find city name column (common names)
    city_name_col = None
    for col_name in ["name", "city_name", "city", "NAME", "CITY_NAME", "CITY", "kentAtlasiDegeri"]:
        if col_name in gdf.columns:
            city_name_col = col_name
            break

    hover_fields = []
    hover_aliases = []

    if city_name_col:
        hover_fields.append(city_name_col)
        hover_aliases.append("Şehir:")

    hover_fields.extend([
        "total_population",
        "estimated_water_supply",
        "urban_water_stress_score",
    ])
    hover_aliases.extend([
        "Nüfus:",
        "Su Arzı:",
        "Su Stresi Skoru:",
    ])

    existing_hover_fields = [f for f in hover_fields if f in gdf.columns]
    existing_aliases = hover_aliases[: len(existing_hover_fields)]

    # Capture all_zero in closure
    all_zero_flag = all_zero
    
    def style_function(feature):
        score = feature["properties"].get(score_col, 0)
        # Handle zero scores - show in light gray
        if all_zero_flag or score == 0 or pd.isna(score):
            return {
                "fillColor": "#cccccc",  # Light gray for zero/no data
                "color": "black",
                "weight": 0.5,
                "fillOpacity": 0.5,
            }
        return {
            "fillColor": colormap(score),
            "color": "black",
            "weight": 0.5,
            "fillOpacity": 0.7,
        }

    tooltip = folium.GeoJsonTooltip(
        fields=existing_hover_fields,
        aliases=existing_aliases,
        localize=True,
        sticky=True,
    )

    folium.GeoJson(
        gdf,
        style_function=style_function,
        tooltip=tooltip,
        name="Urban Water Stress",
    ).add_to(m)

    folium.LayerControl().add_to(m)

    return m


def make_ecosystem_resilience_map(gdf: gpd.GeoDataFrame) -> folium.Map:
    """Create a Folium map colored by ecosystem_water_sensitivity_score."""
    score_col = "ecosystem_water_sensitivity_score"
    if score_col not in gdf.columns:
        raise KeyError(f"Expected column '{score_col}' in GeoDataFrame.")

    # Compute map center
    bounds = gdf.total_bounds  # [minx, miny, maxx, maxy]
    center_lat = (bounds[1] + bounds[3]) / 2
    center_lon = (bounds[0] + bounds[2]) / 2

    m = folium.Map(location=[center_lat, center_lon], zoom_start=7, tiles="cartodbpositron")

    # Color scale: green (low vulnerability) → yellow → red (high vulnerability)
    vmin = float(gdf[score_col].min())
    vmax = float(gdf[score_col].max())
    
    if vmin == vmax:
        # Avoid zero-range scale; expand slightly
        vmin = vmin - 0.001
        vmax = vmax + 0.001

    colormap = LinearColormap(
        colors=["green", "yellow", "red"],
        vmin=vmin,
        vmax=vmax,
    )
    colormap.caption = "Ekosistem Su Hassasiyeti Skoru"
    colormap.add_to(m)

    # Fields to show on hover
    # Try to find ecosystem name column
    ecosystem_name_col = None
    for col_name in ["ka_adi", "name", "ecosystem_name", "NAME"]:
        if col_name in gdf.columns:
            ecosystem_name_col = col_name
            break

    hover_fields = []
    hover_aliases = []

    if ecosystem_name_col:
        hover_fields.append(ecosystem_name_col)
        hover_aliases.append("Ekosistem:")

    hover_fields.extend([
        "ecosystem_type",
        "drought_norm",
        "groundwater_sensitivity_norm",
        "wetland_proximity_risk_norm",
        "protected_area_importance_norm",
        "ecosystem_water_sensitivity_score",
    ])
    hover_aliases.extend([
        "Tip:",
        "Kuraklık (norm):",
        "Yeraltı Suyu (norm):",
        "Sulak Alan Riski (norm):",
        "Önem (norm):",
        "Hassasiyet Skoru:",
    ])

    existing_hover_fields = [f for f in hover_fields if f in gdf.columns]
    existing_aliases = hover_aliases[: len(existing_hover_fields)]

    def style_function(feature):
        score = feature["properties"].get(score_col, 0)
        if pd.isna(score):
            return {
                "fillColor": "#cccccc",  # Light gray for no data
                "color": "black",
                "weight": 0.5,
                "fillOpacity": 0.5,
            }
        return {
            "fillColor": colormap(score),
            "color": "black",
            "weight": 0.5,
            "fillOpacity": 0.7,
        }

    tooltip = folium.GeoJsonTooltip(
        fields=existing_hover_fields,
        aliases=existing_aliases,
        localize=True,
        sticky=True,
    )

    folium.GeoJson(
        gdf,
        style_function=style_function,
        tooltip=tooltip,
        name="Ecosystem Water Sensitivity",
    ).add_to(m)

    folium.LayerControl().add_to(m)

    return m


def _compute_automated_insights(
    gdf: gpd.GeoDataFrame, score_col: str = "final_water_stress_score"
) -> Dict[str, object]:
    """
    Derive automated insights from the Model 1 output.

    Risk bands (by zone count, not area-weighted):
    - High risk: top 5% of scores
    - Medium risk: 40–70th percentile band
    - Low risk: below 40th percentile
    """
    if score_col not in gdf.columns or gdf.empty:
        return {
            "high_risk_share_pct": 0.0,
            "medium_risk_share_pct": 0.0,
            "low_risk_share_pct": 0.0,
            "cluster_insights": [],
            "recommended_actions": [],
        }

    scores = pd.to_numeric(gdf[score_col], errors="coerce").dropna()
    if scores.empty:
        return {
            "high_risk_share_pct": 0.0,
            "medium_risk_share_pct": 0.0,
            "low_risk_share_pct": 0.0,
            "cluster_insights": [],
            "recommended_actions": [],
        }

    n_total = len(scores)
    p95 = float(scores.quantile(0.95))
    p40 = float(scores.quantile(0.40))
    p70 = float(scores.quantile(0.70))

    high_mask = gdf[score_col] >= p95
    medium_mask = (gdf[score_col] >= p40) & (gdf[score_col] <= p70)
    low_mask = gdf[score_col] < p40

    n_high = int(high_mask.sum())
    n_medium = int(medium_mask.sum())
    n_low = int(low_mask.sum())

    high_share = (n_high / n_total) * 100 if n_total else 0.0
    medium_share = (n_medium / n_total) * 100 if n_total else 0.0
    low_share = (n_low / n_total) * 100 if n_total else 0.0

    # Spatial clustering: compare high-risk centroid to overall centroid
    cluster_insights: List[str] = []
    if n_high > 0 and gdf.geometry.notna().any():
        overall_bounds = gdf.total_bounds  # minx, miny, maxx, maxy
        overall_center_lat = (overall_bounds[1] + overall_bounds[3]) / 2
        overall_center_lon = (overall_bounds[0] + overall_bounds[2]) / 2

        high_gdf = gdf.loc[high_mask].copy()
        # Assume already in WGS84; centroids are approximate but good enough for narrative
        high_centroid = high_gdf.geometry.centroid
        high_center_lat = float(high_centroid.y.mean())
        high_center_lon = float(high_centroid.x.mean())

        lat_desc = "central"
        lon_desc = "central"
        lat_delta = high_center_lat - overall_center_lat
        lon_delta = high_center_lon - overall_center_lon

        # Simple directional description with a small tolerance
        tol = 0.1 * max(
            abs(overall_bounds[3] - overall_bounds[1]),
            abs(overall_bounds[2] - overall_bounds[0]),
        )

        if lat_delta > tol:
            lat_desc = "northern"
        elif lat_delta < -tol:
            lat_desc = "southern"

        if lon_delta > tol:
            lon_desc = "eastern"
        elif lon_delta < -tol:
            lon_desc = "western"

        # Assess how compact the high-risk cluster is
        high_bounds = high_gdf.total_bounds
        lat_span_ratio = abs(high_bounds[3] - high_bounds[1]) / max(
            1e-9, abs(overall_bounds[3] - overall_bounds[1])
        )
        lon_span_ratio = abs(high_bounds[2] - high_bounds[0]) / max(
            1e-9, abs(overall_bounds[2] - overall_bounds[0])
        )

        if lat_span_ratio < 0.5 and lon_span_ratio < 0.5:
            cluster_insights.append(
                f"High water stress zones are strongly clustered in the {lat_desc}-{lon_desc} "
                "part of the study area."
            )
        else:
            cluster_insights.append(
                "High water stress zones are distributed across the region without a single "
                "dominant cluster, indicating widespread vulnerability."
            )

    # Recommended actions based on band sizes
    recommended_actions: List[str] = []
    if high_share >= 5:
        recommended_actions.append(
            "Prioritize high-stress zones for **water-efficient irrigation upgrades**, "
            "such as drip systems and improved scheduling."
        )
        recommended_actions.append(
            "Develop **drought contingency plans** and targeted support for farmers in "
            "the highest-risk zones (top 5%)."
        )
    if medium_share >= 20:
        recommended_actions.append(
            "Scale up **no-regret measures** in medium-risk zones, including soil moisture "
            "monitoring, mulching, and deficit irrigation strategies."
        )
    if low_share > 50:
        recommended_actions.append(
            "Maintain current practices in low-risk zones while monitoring for emerging "
            "drought signals to prevent risk escalation."
        )
    if not recommended_actions:
        recommended_actions.append(
            "Overall water stress is relatively low; focus on maintaining monitoring systems "
            "and piloting water-efficient technologies in selected areas."
        )

    return {
        "high_risk_share_pct": high_share,
        "medium_risk_share_pct": medium_share,
        "low_risk_share_pct": low_share,
        "cluster_insights": cluster_insights,
        "recommended_actions": recommended_actions,
    }


def _compute_score_decomposition(
    gdf: gpd.GeoDataFrame, top_n: int = 5
) -> pd.DataFrame:
    """
    Decompose final_water_stress_score into percentage contributions for top N zones.

    The score formula is:
        score = (0.45 * drought_norm) + (0.35 * groundwater_norm) + (0.20 * agricultural_area_pressure)

    For each zone, compute the percentage contribution of each component to the final score.
    """
    required_cols = [
        "final_water_stress_score",
        "drought_norm",
        "groundwater_norm",
        "agricultural_area_pressure",
    ]
    missing = [c for c in required_cols if c not in gdf.columns]
    if missing:
        return pd.DataFrame()

    # Get top N highest-risk zones
    top_zones = gdf.nlargest(top_n, "final_water_stress_score").copy()

    # Extract component values
    drought_vals = pd.to_numeric(top_zones["drought_norm"], errors="coerce").fillna(0.0)
    groundwater_vals = pd.to_numeric(
        top_zones["groundwater_norm"], errors="coerce"
    ).fillna(0.0)
    area_vals = pd.to_numeric(
        top_zones["agricultural_area_pressure"], errors="coerce"
    ).fillna(0.0)
    final_scores = pd.to_numeric(
        top_zones["final_water_stress_score"], errors="coerce"
    ).fillna(0.0)

    # Compute weighted contributions
    # Score = 0.45 * drought + 0.35 * groundwater + 0.20 * area
    drought_contribution = 0.45 * drought_vals
    groundwater_contribution = 0.35 * groundwater_vals
    area_contribution = 0.20 * area_vals

    # Compute percentage contributions (avoid division by zero)
    total_contribution = drought_contribution + groundwater_contribution + area_contribution
    epsilon = 1e-10
    drought_pct = (drought_contribution / (total_contribution + epsilon)) * 100
    groundwater_pct = (groundwater_contribution / (total_contribution + epsilon)) * 100
    area_pct = (area_contribution / (total_contribution + epsilon)) * 100

    # Determine dominant risk factor
    contributions_df = pd.DataFrame(
        {
            "drought_pct": drought_pct,
            "groundwater_pct": groundwater_pct,
            "area_pct": area_pct,
        }
    )
    dominant_factors = []
    for idx in contributions_df.index:
        row = contributions_df.loc[idx]
        max_col = row.idxmax()
        if max_col == "drought_pct":
            dominant_factors.append("Drought")
        elif max_col == "groundwater_pct":
            dominant_factors.append("Groundwater")
        else:
            dominant_factors.append("Area Pressure")

    # Build result DataFrame
    result = pd.DataFrame(
        {
            "zone_index": top_zones.index,
            "final_water_stress_score": final_scores.values,
            "drought_contribution_pct": drought_pct.values,
            "groundwater_contribution_pct": groundwater_pct.values,
            "area_contribution_pct": area_pct.values,
            "dominant_risk_factor": dominant_factors,
        }
    )

    return result


def _generate_explainability_summary(decomp_df: pd.DataFrame) -> str:
    """Generate a narrative summary of the score decomposition."""
    if decomp_df.empty:
        return "No data available for explainability analysis."

    # Count dominant factors
    factor_counts = decomp_df["dominant_risk_factor"].value_counts()
    total_zones = len(decomp_df)

    # Determine primary driver
    primary_factor = factor_counts.index[0] if len(factor_counts) > 0 else None
    primary_count = factor_counts.iloc[0] if len(factor_counts) > 0 else 0
    primary_pct = (primary_count / total_zones) * 100 if total_zones > 0 else 0

    # Compute average contributions
    avg_drought = decomp_df["drought_contribution_pct"].mean()
    avg_groundwater = decomp_df["groundwater_contribution_pct"].mean()
    avg_area = decomp_df["area_contribution_pct"].mean()

    summary_parts = []

    if primary_factor and primary_pct >= 60:
        summary_parts.append(
            f"Most high-risk zones ({primary_pct:.0f}%) are primarily driven by "
            f"**{primary_factor.lower()} pressure**."
        )
    elif primary_factor:
        summary_parts.append(
            f"The dominant risk factor varies across zones, with "
            f"**{primary_factor.lower()}** being the primary driver in "
            f"{primary_pct:.0f}% of the top 5 highest-risk zones."
        )

    summary_parts.append(
        f"On average, the final water stress score is composed of "
        f"{avg_drought:.1f}% drought contribution, "
        f"{avg_groundwater:.1f}% groundwater sensitivity contribution, and "
        f"{avg_area:.1f}% agricultural area pressure contribution."
    )

    return " ".join(summary_parts)


def render_model1_tab() -> None:
    """Render the Model 1 (Agricultural Water Stress) tab."""
    st.header("Model 1: Tarımsal Su Stresi İstihbaratı")
    st.markdown(
        "**Tarımsal Su Stresi İstihbaratı** (Model 1) için görsel karar destek dashboard'u."
    )

    # ---- Sidebar configuration ----
    root_dir = Path(__file__).resolve().parents[1]
    default_geojson = root_dir / "outputs" / "model1_water_stress.geojson"

    st.sidebar.header("Model 1 Yapılandırması")
    geojson_path_str = st.sidebar.text_input(
        "Model 1 GeoJSON dosya yolu",
        value=str(default_geojson),
        help="Pipeline tarafından üretilen `model1_water_stress.geojson` dosyasının yolu.",
        key="model1_path",
    )

    # ---- Load data ----
    try:
        gdf = load_model1_results(geojson_path_str)
    except FileNotFoundError as e:
        st.error(str(e))
        st.info("GeoJSON çıktısını oluşturmak için önce Model 1'i çalıştırın.")
        return
    except Exception as e:
        st.error(f"GeoJSON yüklenemedi: {e}")
        return

    if gdf.empty:
        st.warning("Yüklenen GeoJSON dosyası hiçbir özellik içermiyor.")
        return

    score_col = "final_water_stress_score"
    if score_col not in gdf.columns:
        st.error(f"Beklenen '{score_col}' sütunu veride bulunamadı.")
        return

    # ---- Layout: Map + Top 10 table ----
    map_col, table_col = st.columns((2, 1))

    with map_col:
        st.subheader("Su Stresi Haritası")
        m = make_water_stress_map(gdf)
        st_folium(m, width="100%", height=600)

    with table_col:
        st.subheader("En Yüksek Riskli 10 Tarımsal Bölge")
        top10 = (
            gdf[
                [
                    score_col,
                    "drought_norm",
                    "groundwater_norm",
                    "agricultural_area_pressure",
                ]
            ]
            .copy()
        )
        top10 = top10.sort_values(score_col, ascending=False).head(10)
        if "geometry" in top10.columns:
            top10 = pd.DataFrame(top10.drop(columns="geometry"))
        st.dataframe(top10.reset_index(drop=True), use_container_width=True)

    # ---- Automated insights panel ----
    st.markdown("---")
    st.subheader("Otomatik İçgörüler")

    insights = _compute_automated_insights(gdf, score_col=score_col)

    st.markdown(
        f"**Yüksek su stresi altındaki bölgelerin payı (en üst %5):** "
        f"{insights['high_risk_share_pct']:.1f}%"
    )
    st.markdown(
        f"**Orta risk bandındaki bölgelerin payı (%40–70):** "
        f"{insights['medium_risk_share_pct']:.1f}%"
    )
    st.markdown(
        f"**Düşük risk bandındaki bölgelerin payı:** "
        f"{insights['low_risk_share_pct']:.1f}%"
    )

    cluster_insights = insights.get("cluster_insights") or []
    if cluster_insights:
        st.markdown("**Riskin mekansal desenleri:**")
        for line in cluster_insights:
            st.markdown(f"- {line}")

    recommended_actions = insights.get("recommended_actions") or []
    if recommended_actions:
        st.markdown("**Önerilen eylemler:**")
        for action in recommended_actions:
            st.markdown(f"- {action}")

    # ---- Explainability section ----
    st.markdown("---")
    st.subheader("Açıklanabilirlik: Skor Ayrıştırması")

    st.markdown(
        "Bu bölüm, en yüksek riskli 5 tarımsal bölge için **final su stresi skorunu** "
        "ayrıştırır ve her bileşen faktörün yüzde katkısını gösterir. "
        "Skor formülü: "
        "`final_skor = (0.45 × drought_norm) + (0.35 × groundwater_norm) + "
        "(0.20 × agricultural_area_pressure)`."
    )

    decomp_df = _compute_score_decomposition(gdf, top_n=5)

    if decomp_df.empty:
        st.warning(
            "Skor ayrıştırması hesaplanamadı. GeoDataFrame'in şu sütunları içerdiğinden emin olun: "
            "'final_water_stress_score', 'drought_norm', 'groundwater_norm', "
            "ve 'agricultural_area_pressure'."
        )
    else:
        # Display decomposition table
        display_cols = [
            "zone_index",
            "final_water_stress_score",
            "drought_contribution_pct",
            "groundwater_contribution_pct",
            "area_contribution_pct",
            "dominant_risk_factor",
        ]
        display_df = decomp_df[display_cols].copy()
        display_df = display_df.rename(
            columns={
                "zone_index": "Bölge ID",
                "final_water_stress_score": "Final Skor",
                "drought_contribution_pct": "Kuraklık %",
                "groundwater_contribution_pct": "Yeraltı Suyu %",
                "area_contribution_pct": "Alan Basıncı %",
                "dominant_risk_factor": "Baskın Faktör",
            }
        )
        # Format percentages
        display_df["Kuraklık %"] = display_df["Kuraklık %"].apply(lambda x: f"{x:.1f}%")
        display_df["Yeraltı Suyu %"] = display_df["Yeraltı Suyu %"].apply(
            lambda x: f"{x:.1f}%"
        )
        display_df["Alan Basıncı %"] = display_df["Alan Basıncı %"].apply(
            lambda x: f"{x:.1f}%"
        )
        display_df["Final Skor"] = display_df["Final Skor"].apply(
            lambda x: f"{x:.3f}"
        )

        st.dataframe(display_df.reset_index(drop=True), use_container_width=True)

        # Generate and display narrative summary
        summary = _generate_explainability_summary(decomp_df)
        st.markdown("**Özet:**")
        st.info(summary)


def _compute_urban_insights(
    gdf: gpd.GeoDataFrame, score_col: str = "urban_water_stress_score"
) -> Dict[str, object]:
    """
    Derive automated insights from the Model 2 output.

    Risk bands:
    - High risk: top 20% of scores
    - Medium risk: 40–80th percentile band
    - Low risk: bottom 40%
    """
    if score_col not in gdf.columns or gdf.empty:
        return {
            "high_risk_share_pct": 0.0,
            "medium_risk_share_pct": 0.0,
            "low_risk_share_pct": 0.0,
            "pattern_insights": [],
            "recommended_actions": [],
        }

    scores = pd.to_numeric(gdf[score_col], errors="coerce").dropna()
    if scores.empty:
        return {
            "high_risk_share_pct": 0.0,
            "medium_risk_share_pct": 0.0,
            "low_risk_share_pct": 0.0,
            "pattern_insights": [],
            "recommended_actions": [],
        }

    n_total = len(scores)
    p80 = float(scores.quantile(0.80))  # Top 20%
    p40 = float(scores.quantile(0.40))  # Bottom 40% threshold

    high_mask = gdf[score_col] >= p80
    medium_mask = (gdf[score_col] >= p40) & (gdf[score_col] < p80)
    low_mask = gdf[score_col] < p40

    n_high = int(high_mask.sum())
    n_medium = int(medium_mask.sum())
    n_low = int(low_mask.sum())

    high_share = (n_high / n_total) * 100 if n_total else 0.0
    medium_share = (n_medium / n_total) * 100 if n_total else 0.0
    low_share = (n_low / n_total) * 100 if n_total else 0.0

    # Pattern detection: analyze drivers of high risk
    pattern_insights: List[str] = []

    if n_high > 0:
        high_risk_cities = gdf.loc[high_mask].copy()
        all_cities = gdf.copy()

        # Check if high-risk cities are primarily large-population cities
        if "total_population" in gdf.columns:
            high_pop = pd.to_numeric(
                high_risk_cities["total_population"], errors="coerce"
            ).fillna(0.0)
            all_pop = pd.to_numeric(
                all_cities["total_population"], errors="coerce"
            ).fillna(0.0)

            median_pop_all = all_pop.median()
            median_pop_high = high_pop.median()

            if median_pop_high > median_pop_all * 1.5:
                pattern_insights.append(
                    "High-risk cities are **primarily large-population cities**, "
                    f"with a median population of {median_pop_high:,.0f} compared to "
                    f"{median_pop_all:,.0f} for all cities."
                )
            elif median_pop_high < median_pop_all * 0.7:
                pattern_insights.append(
                    "High-risk cities include many **smaller cities**, suggesting "
                    "water supply constraints rather than population pressure alone."
                )

        # Analyze correlation: population pressure vs water supply
        if "total_population" in gdf.columns and "estimated_water_supply" in gdf.columns:
            high_pop = pd.to_numeric(
                high_risk_cities["total_population"], errors="coerce"
            ).fillna(0.0)
            high_supply = pd.to_numeric(
                high_risk_cities["estimated_water_supply"], errors="coerce"
            ).fillna(0.0)

            all_pop = pd.to_numeric(
                all_cities["total_population"], errors="coerce"
            ).fillna(0.0)
            all_supply = pd.to_numeric(
                all_cities["estimated_water_supply"], errors="coerce"
            ).fillna(0.0)

            # Normalize for comparison
            max_pop = all_pop.max()
            max_supply = all_supply.max()

            if max_pop > 0 and max_supply > 0:
                high_pop_norm = high_pop / max_pop
                high_supply_norm = high_supply / max_supply

                # Compare medians
                median_pop_norm_high = high_pop_norm.median()
                median_supply_norm_high = high_supply_norm.median()

                if median_pop_norm_high > median_supply_norm_high * 1.3:
                    pattern_insights.append(
                        "High-risk cities are **primarily driven by population pressure** "
                        "rather than low water availability, indicating demand-side challenges."
                    )
                elif median_supply_norm_high < median_pop_norm_high * 0.7:
                    pattern_insights.append(
                        "High-risk cities are **primarily driven by low water supply** "
                        "rather than population pressure, indicating supply-side constraints."
                    )
                else:
                    pattern_insights.append(
                        "High-risk cities show a **balanced combination** of population "
                        "pressure and water supply constraints."
                    )

    # Recommended actions based on patterns and risk distribution
    recommended_actions: List[str] = []

    if high_share >= 15:
        # Check if it's population-driven or supply-driven
        if pattern_insights and any(
            "population pressure" in insight.lower() for insight in pattern_insights
        ):
            recommended_actions.append(
                "**Demand management** for large cities: Implement water conservation "
                "programs, leak reduction initiatives, and tiered pricing structures to "
                "reduce per-capita consumption."
            )
            recommended_actions.append(
                "**Water-efficient infrastructure**: Upgrade urban water systems with "
                "smart metering, greywater recycling, and rainwater harvesting in "
                "high-population stress zones."
            )
        elif pattern_insights and any(
            "low water supply" in insight.lower() for insight in pattern_insights
        ):
            recommended_actions.append(
                "**Infrastructure investment** for supply-limited cities: Develop new "
                "water sources, expand reservoir capacity, and improve water distribution "
                "networks to increase supply reliability."
            )
            recommended_actions.append(
                "**Diversification of water sources**: Explore groundwater development, "
                "desalination, and inter-basin transfers for cities with constrained supply."
            )
        else:
            recommended_actions.append(
                "**Integrated water resource management**: Address both demand and supply "
                "challenges through a combination of conservation measures and infrastructure "
                "investments."
            )

    if medium_share >= 30:
        recommended_actions.append(
            "**Preventive measures** in medium-risk cities: Establish early-warning systems, "
            "drought contingency plans, and pilot water efficiency programs to prevent "
            "escalation to high risk."
        )

    if low_share > 50:
        recommended_actions.append(
            "**Maintain resilience** in low-risk cities: Continue monitoring, maintain "
            "infrastructure, and prepare for future population growth and climate variability."
        )

    if not recommended_actions:
        recommended_actions.append(
            "Overall urban water stress is relatively low; focus on **monitoring systems** "
            "and **long-term planning** to maintain water security as cities grow."
        )

    return {
        "high_risk_share_pct": high_share,
        "medium_risk_share_pct": medium_share,
        "low_risk_share_pct": low_share,
        "pattern_insights": pattern_insights,
        "recommended_actions": recommended_actions,
    }


def _compute_ecosystem_insights(
    gdf: gpd.GeoDataFrame, score_col: str = "ecosystem_water_sensitivity_score"
) -> Dict[str, object]:
    """
    Derive automated insights from the Model 3 output.

    Risk bands:
    - High risk: top 20% of scores (≥80th percentile)
    - Medium risk: 40–80th percentile band
    - Low risk: bottom 40%
    """
    if score_col not in gdf.columns or gdf.empty:
        return {
            "high_risk_share_pct": 0.0,
            "medium_risk_share_pct": 0.0,
            "low_risk_share_pct": 0.0,
            "pattern_insights": [],
            "recommended_actions": [],
        }

    scores = pd.to_numeric(gdf[score_col], errors="coerce").dropna()
    if scores.empty:
        return {
            "high_risk_share_pct": 0.0,
            "medium_risk_share_pct": 0.0,
            "low_risk_share_pct": 0.0,
            "pattern_insights": [],
            "recommended_actions": [],
        }

    n_total = len(scores)
    p80 = float(scores.quantile(0.80))  # Top 20%
    p40 = float(scores.quantile(0.40))  # Bottom 40% threshold

    high_mask = gdf[score_col] >= p80
    medium_mask = (gdf[score_col] >= p40) & (gdf[score_col] < p80)
    low_mask = gdf[score_col] < p40

    n_high = int(high_mask.sum())
    n_medium = int(medium_mask.sum())
    n_low = int(low_mask.sum())

    high_share = (n_high / n_total) * 100 if n_total else 0.0
    medium_share = (n_medium / n_total) * 100 if n_total else 0.0
    low_share = (n_low / n_total) * 100 if n_total else 0.0

    # Pattern detection: analyze drivers of high risk
    pattern_insights: List[str] = []

    if n_high > 0:
        high_risk_ecosystems = gdf.loc[high_mask].copy()
        all_ecosystems = gdf.copy()

        # Analyze component contributions
        component_cols = [
            "drought_norm",
            "groundwater_sensitivity_norm",
            "wetland_proximity_risk_norm",
            "protected_area_importance_norm",
        ]

        for col in component_cols:
            if col in gdf.columns:
                high_vals = pd.to_numeric(
                    high_risk_ecosystems[col], errors="coerce"
                ).fillna(0.0)
                all_vals = pd.to_numeric(
                    all_ecosystems[col], errors="coerce"
                ).fillna(0.0)

                mean_high = high_vals.mean()
                mean_all = all_vals.mean()

                if mean_high > mean_all * 1.2:
                    col_name = col.replace("_norm", "").replace("_", " ").title()
                    pattern_insights.append(
                        f"High-risk ecosystems show **elevated {col_name}** "
                        f"({mean_high:.3f} vs {mean_all:.3f} average), indicating this "
                        "factor is a key driver of vulnerability."
                    )

        # Analyze ecosystem type distribution
        if "ecosystem_type" in gdf.columns:
            high_types = high_risk_ecosystems["ecosystem_type"].value_counts()
            all_types = all_ecosystems["ecosystem_type"].value_counts()

            for etype in high_types.index:
                high_pct = (high_types[etype] / n_high) * 100
                all_pct = (all_types.get(etype, 0) / n_total) * 100

                if high_pct > all_pct * 1.3:
                    pattern_insights.append(
                        f"**{etype}s** are overrepresented in high-risk category "
                        f"({high_pct:.1f}% vs {all_pct:.1f}% overall), suggesting "
                        "type-specific vulnerability factors."
                    )

    # Recommended actions based on patterns and risk distribution
    recommended_actions: List[str] = []

    if high_share >= 15:
        recommended_actions.append(
            "**Immediate intervention** required for high-risk ecosystems: Implement "
            "groundwater protection zones, drought contingency plans, and enhanced "
            "monitoring systems."
        )
        recommended_actions.append(
            "**Regional coordination** needed: High-risk ecosystems are distributed "
            "across multiple regions, requiring coordinated conservation efforts."
        )

    if medium_share >= 40:
        recommended_actions.append(
            "**Preventive resilience-building** for medium-risk ecosystems: Implement "
            "early intervention measures to prevent transition to high-risk status under "
            "projected climate change impacts."
        )

    if pattern_insights and any("drought" in insight.lower() for insight in pattern_insights):
        recommended_actions.append(
            "**Climate adaptation** priority: High drought exposure requires integration "
            "of climate adaptation measures into all protected area management plans."
        )

    if pattern_insights and any("groundwater" in insight.lower() for insight in pattern_insights):
        recommended_actions.append(
            "**Groundwater protection** critical: Implement protection zones around "
            "ecosystem-dependent aquifers and coordinate groundwater management at basin scale."
        )

    if not recommended_actions:
        recommended_actions.append(
            "Overall ecosystem water resilience is relatively good; focus on **monitoring systems** "
            "and **preventive measures** to maintain resilience under climate change."
        )

    return {
        "high_risk_share_pct": high_share,
        "medium_risk_share_pct": medium_share,
        "low_risk_share_pct": low_share,
        "pattern_insights": pattern_insights,
        "recommended_actions": recommended_actions,
    }


def render_model2_tab() -> None:
    """Render the Model 2 (Urban Water Stress) tab."""
    st.header("Model 2: Kentsel Su Stresi İstihbaratı")
    st.markdown(
        "**Kentsel Su Stresi İstihbaratı** (Model 2) için görsel karar destek dashboard'u - "
        "Şehir düzeyinde su riski analizi."
    )

    # ---- Sidebar configuration ----
    root_dir = Path(__file__).resolve().parents[1]
    default_geojson = root_dir / "outputs" / "model2_urban_water_stress.geojson"

    st.sidebar.header("Model 2 Yapılandırması")
    geojson_path_str = st.sidebar.text_input(
        "Model 2 GeoJSON dosya yolu",
        value=str(default_geojson),
        help="Pipeline tarafından üretilen `model2_urban_water_stress.geojson` dosyasının yolu.",
        key="model2_path",
    )

    # ---- Load data ----
    try:
        gdf = load_model2_results(geojson_path_str)
    except FileNotFoundError as e:
        st.error(str(e))
        st.info("GeoJSON çıktısını oluşturmak için önce Model 2'yi çalıştırın.")
        return
    except Exception as e:
        st.error(f"GeoJSON yüklenemedi: {e}")
        return

    if gdf.empty:
        st.warning("Yüklenen GeoJSON dosyası hiçbir özellik içermiyor.")
        return

    score_col = "urban_water_stress_score"
    if score_col not in gdf.columns:
        st.error(f"Beklenen '{score_col}' sütunu veride bulunamadı.")
        return

    # ---- Layout: Map + Top 10 table ----
    map_col, table_col = st.columns((2, 1))

    with map_col:
        st.subheader("Kentsel Su Stresi Haritası")
        m = make_urban_water_stress_map(gdf)
        st_folium(m, width="100%", height=600)

    with table_col:
        st.subheader("En Yüksek Stresli 10 Şehir")
        # Find city name column if available
        city_name_col = None
        for col_name in ["name", "city_name", "city", "NAME", "CITY_NAME", "CITY"]:
            if col_name in gdf.columns:
                city_name_col = col_name
                break

        display_cols = [score_col, "total_population", "estimated_water_supply"]
        if city_name_col:
            display_cols.insert(0, city_name_col)

        top10 = gdf[display_cols].copy()
        top10 = top10.sort_values(score_col, ascending=False).head(10)
        if "geometry" in top10.columns:
            top10 = pd.DataFrame(top10.drop(columns="geometry"))

        # Format numeric columns for better readability
        if "total_population" in top10.columns:
            top10["total_population"] = top10["total_population"].apply(
                lambda x: f"{x:,.0f}" if pd.notna(x) else "N/A"
            )
        if "estimated_water_supply" in top10.columns:
            top10["estimated_water_supply"] = top10["estimated_water_supply"].apply(
                lambda x: f"{x:.2f}" if pd.notna(x) else "N/A"
            )
        if score_col in top10.columns:
            top10[score_col] = top10[score_col].apply(
                lambda x: f"{x:.3f}" if pd.notna(x) else "N/A"
            )

        # Rename columns for display
        rename_dict = {
            score_col: "Su Stresi Skoru",
            "total_population": "Nüfus",
            "estimated_water_supply": "Su Arzı",
        }
        if city_name_col:
            rename_dict[city_name_col] = "Şehir Adı"

        top10 = top10.rename(columns=rename_dict)
        st.dataframe(top10.reset_index(drop=True), use_container_width=True)

    # ---- Automated Urban Insights panel ----
    st.markdown("---")
    st.subheader("Otomatik Kentsel İçgörüler")

    insights = _compute_urban_insights(gdf, score_col=score_col)

    st.markdown(
        f"**Yüksek su stresi altındaki şehirlerin payı (en üst %20):** "
        f"{insights['high_risk_share_pct']:.1f}%"
    )
    st.markdown(
        f"**Orta risk bandındaki şehirlerin payı (%40–80):** "
        f"{insights['medium_risk_share_pct']:.1f}%"
    )
    st.markdown(
        f"**Düşük risk bandındaki şehirlerin payı (en alt %40):** "
        f"{insights['low_risk_share_pct']:.1f}%"
    )

    pattern_insights = insights.get("pattern_insights") or []
    if pattern_insights:
        st.markdown("**Risk deseni analizi:**")
        for line in pattern_insights:
            st.markdown(f"- {line}")

    recommended_actions = insights.get("recommended_actions") or []
    if recommended_actions:
        st.markdown("**Önerilen eylemler:**")
        for action in recommended_actions:
            st.markdown(f"- {action}")


def render_model3_tab() -> None:
    """Render the Model 3 (Ecosystem Water Resilience) tab."""
    st.header("Model 3: Ekosistem Su Direnci İstihbaratı")
    st.markdown(
        "**Ekosistem Su Direnci İstihbaratı** (Model 3) için görsel karar destek dashboard'u - "
        "Korunan alan su kırılganlığı analizi."
    )

    # ---- Sidebar configuration ----
    root_dir = Path(__file__).resolve().parents[1]
    default_geojson = root_dir / "outputs" / "model3_ecosystem_resilience.geojson"

    st.sidebar.header("Model 3 Yapılandırması")
    geojson_path_str = st.sidebar.text_input(
        "Model 3 GeoJSON dosya yolu",
        value=str(default_geojson),
        help="Pipeline tarafından üretilen `model3_ecosystem_resilience.geojson` dosyasının yolu.",
        key="model3_path",
    )

    # ---- Load data ----
    try:
        gdf = load_model3_results(geojson_path_str)
    except FileNotFoundError as e:
        st.error(str(e))
        st.info("GeoJSON çıktısını oluşturmak için önce Model 3'ü çalıştırın.")
        return
    except Exception as e:
        st.error(f"GeoJSON yüklenemedi: {e}")
        return

    if gdf.empty:
        st.warning("Yüklenen GeoJSON dosyası hiçbir özellik içermiyor.")
        return

    score_col = "ecosystem_water_sensitivity_score"
    if score_col not in gdf.columns:
        st.error(f"Beklenen '{score_col}' sütunu veride bulunamadı.")
        return

    # ---- Layout: Map + Top 10 table ----
    map_col, table_col = st.columns((2, 1))

    with map_col:
        st.subheader("Ekosistem Su Hassasiyeti Haritası")
        m = make_ecosystem_resilience_map(gdf)
        st_folium(m, width="100%", height=600)

    with table_col:
        st.subheader("En Yüksek Riskli 10 Ekosistem")
        # Find ecosystem name column if available
        ecosystem_name_col = None
        for col_name in ["ka_adi", "name", "ecosystem_name"]:
            if col_name in gdf.columns:
                ecosystem_name_col = col_name
                break

        display_cols = [
            score_col,
            "drought_norm",
            "groundwater_sensitivity_norm",
            "ecosystem_type",
        ]
        if ecosystem_name_col:
            display_cols.insert(0, ecosystem_name_col)

        top10 = gdf[display_cols].copy()
        top10 = top10.sort_values(score_col, ascending=False).head(10)
        if "geometry" in top10.columns:
            top10 = pd.DataFrame(top10.drop(columns="geometry"))

        # Format numeric columns for better readability
        if score_col in top10.columns:
            top10[score_col] = top10[score_col].apply(
                lambda x: f"{x:.3f}" if pd.notna(x) else "N/A"
            )
        for col in ["drought_norm", "groundwater_sensitivity_norm"]:
            if col in top10.columns:
                top10[col] = top10[col].apply(
                    lambda x: f"{x:.3f}" if pd.notna(x) else "N/A"
                )

        # Rename columns for display
        rename_dict = {
            score_col: "Sensitivity Score",
            "drought_norm": "Drought",
            "groundwater_sensitivity_norm": "Groundwater",
            "ecosystem_type": "Type",
        }
        if ecosystem_name_col:
            rename_dict[ecosystem_name_col] = "Ecosystem Name"

        top10 = top10.rename(columns=rename_dict)
        st.dataframe(top10.reset_index(drop=True), use_container_width=True)

    # ---- Automated Ecosystem Insights panel ----
    st.markdown("---")
    st.subheader("Automated Ecosystem Insights")

    insights = _compute_ecosystem_insights(gdf, score_col=score_col)

    st.markdown(
        f"**Share of ecosystems under high water sensitivity (top 20%):** "
        f"{insights['high_risk_share_pct']:.1f}%"
    )
    st.markdown(
        f"**Share of ecosystems in medium sensitivity band (40–80th percentile):** "
        f"{insights['medium_risk_share_pct']:.1f}%"
    )
    st.markdown(
        f"**Share of ecosystems in low sensitivity band:** "
        f"{insights['low_risk_share_pct']:.1f}%"
    )

    pattern_insights = insights.get("pattern_insights") or []
    if pattern_insights:
        st.markdown("**Spatial and ecological patterns:**")
        for line in pattern_insights:
            st.markdown(f"- {line}")

    recommended_actions = insights.get("recommended_actions") or []
    if recommended_actions:
        st.markdown("**Recommended actions:**")
        for action in recommended_actions:
            st.markdown(f"- {action}")

    # ---- Component Analysis section ----
    st.markdown("---")
    st.subheader("Component Analysis")

    component_cols = [
        "drought_norm",
        "groundwater_sensitivity_norm",
        "wetland_proximity_risk_norm",
        "protected_area_importance_norm",
    ]

    component_data = []
    component_names_tr = {
        "drought_norm": "Kuraklık",
        "groundwater_sensitivity_norm": "Yeraltı Suyu Hassasiyeti",
        "wetland_proximity_risk_norm": "Sulak Alan Yakınlık Riski",
        "protected_area_importance_norm": "Korunan Alan Önemi",
    }
    
    for col in component_cols:
        if col in gdf.columns:
            component_data.append({
                "Bileşen": component_names_tr.get(col, col.replace("_norm", "").replace("_", " ").title()),
                "Ortalama": gdf[col].mean(),
                "Min": gdf[col].min(),
                "Max": gdf[col].max(),
                "Ağırlık": "35%" if "drought" in col else "30%" if "groundwater" in col else "20%" if "wetland" in col else "15%",
            })

    if component_data:
        comp_df = pd.DataFrame(component_data)
        comp_df["Ortalama"] = comp_df["Ortalama"].apply(lambda x: f"{x:.3f}")
        comp_df["Min"] = comp_df["Min"].apply(lambda x: f"{x:.3f}")
        comp_df["Max"] = comp_df["Max"].apply(lambda x: f"{x:.3f}")
        st.dataframe(comp_df, use_container_width=True)


def main() -> None:
    st.title("Su Stresi İstihbarat Dashboard'u")
    st.markdown(
        "**Tarımsal bölgeler** (Model 1), **kentsel şehirler** (Model 2) ve "
        "**korunan ekosistemler** (Model 3) için kapsamlı su stresi analiz dashboard'u."
    )

    # Create tabs
    tab1, tab2, tab3 = st.tabs(
        [
            "🌾 Tarımsal Su Stresi (Model 1)",
            "🏙️ Kentsel Su Stresi (Model 2)",
            "🌿 Ekosistem Su Direnci (Model 3)",
        ]
    )

    with tab1:
        render_model1_tab()

    with tab2:
        render_model2_tab()

    with tab3:
        render_model3_tab()


if __name__ == "__main__":
    main()
