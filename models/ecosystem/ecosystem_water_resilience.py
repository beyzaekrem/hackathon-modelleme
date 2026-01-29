"""
Model 3: Ecosystem Water Resilience Intelligence.

This module implements a GeoPandas-based pipeline for ecosystem-level water resilience analysis:

1. Load:
   - Wetlands (polygon features)
   - National Parks (polygon features)
   - Nature Parks (polygon features)
   - Groundwater Bodies (polygon features with sensitivity attributes)
   - Aquifer Boundaries (polygon features)
   - Drought SPI Index (vector polygons with drought severity)
   - Active Fault Lines (line features)
2. Compute spatial relationships:
   - Proximity of wetlands to groundwater bodies
   - Overlap of protected areas with drought zones
   - Distance of ecosystems to fault lines
3. Normalize components:
   - drought_norm
   - groundwater_sensitivity_norm
   - wetland_proximity_risk_norm
   - protected_area_importance_norm
4. Compute Ecosystem Water Sensitivity Score:
   score = (0.35 * drought_norm)
         + (0.30 * groundwater_sensitivity_norm)
         + (0.20 * wetland_proximity_risk_norm)
         + (0.15 * protected_area_importance_norm)
5. Export:
   - GeoJSON with ecosystem polygons + score
   - CSV ranking most vulnerable ecosystems

Assumptions
-----------
- Protected areas (National Parks + Nature Parks) are the primary ecosystem units.
- Wetlands are analyzed for proximity to groundwater bodies.
- All inputs are vector datasets readable by GeoPandas.
- Groundwater bodies have a sensitivity attribute.
- Drought index has a severity attribute.
- Higher scores indicate higher vulnerability (lower resilience).

You can override default column names through function parameters.
"""

from pathlib import Path
from typing import Optional, Union

import geopandas as gpd
import numpy as np
import pandas as pd


PathLike = Union[str, Path]


def _ensure_matching_crs(
    base: gpd.GeoDataFrame, other: gpd.GeoDataFrame, other_name: str
) -> gpd.GeoDataFrame:
    """
    Ensure that ``other`` has the same CRS as ``base``.

    Raises a ValueError if either CRS is missing.
    """
    if base.crs is None:
        raise ValueError(f"Base GeoDataFrame has no CRS set.")
    if other.crs is None:
        raise ValueError(f"{other_name} GeoDataFrame has no CRS set.")

    if base.crs != other.crs:
        return other.to_crs(base.crs)
    return other


def _normalize_series(series: pd.Series) -> pd.Series:
    """
    Min-max normalize a numeric Series to the [0, 1] range.

    If the series is constant or empty, returns zeros.
    """
    if series.empty:
        return series.copy()

    min_val = series.min()
    max_val = series.max()
    if pd.isna(min_val) or pd.isna(max_val) or max_val == min_val:
        return pd.Series(0.0, index=series.index)

    return (series - min_val) / (max_val - min_val)


def _compute_wetland_proximity_risk(
    ecosystems_gdf: gpd.GeoDataFrame,
    wetlands_gdf: gpd.GeoDataFrame,
    groundwater_gdf: gpd.GeoDataFrame,
    max_distance_m: float = 5000.0,
) -> pd.Series:
    """
    Compute wetland proximity risk for each ecosystem.

    Risk increases when wetlands are close to groundwater bodies (indicating
    dependency on groundwater that may be vulnerable).

    Parameters
    ----------
    ecosystems_gdf:
        Protected areas (ecosystems) GeoDataFrame.
    wetlands_gdf:
        Wetlands GeoDataFrame.
    groundwater_gdf:
        Groundwater bodies GeoDataFrame.
    max_distance_m:
        Maximum distance (meters) to consider. Default: 5000m (5km).

    Returns
    -------
    pandas.Series
        Risk scores (higher = more risk) for each ecosystem.
    """
    # Ensure matching CRS
    wetlands_gdf = _ensure_matching_crs(ecosystems_gdf, wetlands_gdf, "Wetlands")
    groundwater_gdf = _ensure_matching_crs(
        ecosystems_gdf, groundwater_gdf, "Groundwater bodies"
    )

    # Use projected CRS for distance calculations
    if ecosystems_gdf.crs is None or ecosystems_gdf.crs.is_geographic:
        work_crs = "EPSG:3857"
    else:
        work_crs = ecosystems_gdf.crs

    ecosystems_proj = ecosystems_gdf.to_crs(work_crs)
    wetlands_proj = wetlands_gdf.to_crs(work_crs)
    groundwater_proj = groundwater_gdf.to_crs(work_crs)

    # Compute centroids for ecosystems
    ecosystem_centroids = ecosystems_proj.geometry.centroid

    risk_scores = []
    for centroid in ecosystem_centroids:
        if centroid is None or centroid.is_empty:
            risk_scores.append(0.0)
            continue

        # Find wetlands within max_distance
        wetland_distances = wetlands_proj.geometry.distance(centroid)
        nearby_wetlands = wetlands_proj[wetland_distances <= max_distance_m]

        if nearby_wetlands.empty:
            risk_scores.append(0.0)
            continue

        # For each nearby wetland, check proximity to groundwater bodies
        total_risk = 0.0
        for wetland_idx, wetland_row in nearby_wetlands.iterrows():
            wetland_geom = wetland_row.geometry
            wetland_centroid = wetland_geom.centroid

            # Distance from wetland to nearest groundwater body
            gw_distances = groundwater_proj.geometry.distance(wetland_centroid)
            min_gw_distance = gw_distances.min()

            if min_gw_distance <= max_distance_m:
                # Inverse distance weighting: closer = higher risk
                # Risk = 1 / (1 + distance_km)
                distance_km = min_gw_distance / 1000.0
                risk = 1.0 / (1.0 + distance_km)
                total_risk += risk

        risk_scores.append(total_risk)

    return pd.Series(risk_scores, index=ecosystems_gdf.index)


def _compute_protected_area_importance(
    ecosystems_gdf: gpd.GeoDataFrame,
) -> pd.Series:
    """
    Compute importance score for protected areas based on area and type.

    National Parks typically have higher conservation importance than Nature Parks.

    Parameters
    ----------
    ecosystems_gdf:
        Protected areas GeoDataFrame (should have a type/category column).

    Returns
    -------
    pandas.Series
        Importance scores (higher = more important) for each ecosystem.
    """
    # Use a projected CRS for area calculation
    if ecosystems_gdf.crs is None or ecosystems_gdf.crs.is_geographic:
        work_crs = "EPSG:3857"
    else:
        work_crs = ecosystems_gdf.crs

    ecosystems_proj = ecosystems_gdf.to_crs(work_crs)

    # Compute areas
    areas = ecosystems_proj.geometry.area

    # Try to identify type/category column
    type_col = None
    for col_name in ["type", "category", "TYPE", "CATEGORY", "park_type", "designation"]:
        if col_name in ecosystems_gdf.columns:
            type_col = col_name
            break

    # Base importance on area (normalized)
    importance = _normalize_series(areas)

    # Boost importance for National Parks if type column exists
    if type_col:
        type_values = ecosystems_gdf[type_col].astype(str).str.lower()
        national_park_mask = type_values.str.contains("national", na=False)
        importance = importance.copy()
        importance[national_park_mask] = importance[national_park_mask] * 1.5
        # Clip to [0, 1]
        importance = importance.clip(0.0, 1.0)

    return importance


def build_ecosystem_water_resilience(
    wetlands_path: PathLike,
    national_parks_path: PathLike,
    nature_parks_path: PathLike,
    groundwater_bodies_path: PathLike,
    aquifer_boundaries_path: PathLike,
    drought_index_path: PathLike,
    fault_lines_path: PathLike,
    *,
    drought_severity_column: str = "drought_severity",
    groundwater_sensitivity_column: str = "groundwater_sensitivity",
    max_distance_m: float = 5000.0,
    output_geojson_path: Optional[PathLike] = None,
    output_csv_path: Optional[PathLike] = None,
) -> gpd.GeoDataFrame:
    """
    Run the Model 3 geospatial pipeline and return a GeoDataFrame with ecosystem water resilience scores.

    Parameters
    ----------
    wetlands_path:
        Path to the Wetlands dataset (polygon features).
    national_parks_path:
        Path to the National Parks dataset (polygon features).
    nature_parks_path:
        Path to the Nature Parks dataset (polygon features).
    groundwater_bodies_path:
        Path to the Groundwater Bodies dataset (polygon features with sensitivity).
    aquifer_boundaries_path:
        Path to the Aquifer Boundaries dataset (polygon features).
    drought_index_path:
        Path to the Drought SPI Index dataset (vector polygons with drought severity).
    fault_lines_path:
        Path to the Active Fault Lines dataset (line features).
    drought_severity_column:
        Name of the drought severity column. Default: ``"drought_severity"``.
    groundwater_sensitivity_column:
        Name of the groundwater sensitivity column. Default: ``"groundwater_sensitivity"``.
    max_distance_m:
        Maximum distance (meters) for proximity calculations. Default: 5000m.
    output_geojson_path:
        Optional path where a GeoJSON file with ecosystem polygons and scores will be written.
    output_csv_path:
        Optional path where a CSV ranking most vulnerable ecosystems will be written.

    Returns
    -------
    geopandas.GeoDataFrame
        GeoDataFrame with ecosystem polygons and the following columns:

        - ``drought_norm`` (0–1)
        - ``groundwater_sensitivity_norm`` (0–1)
        - ``wetland_proximity_risk_norm`` (0–1)
        - ``protected_area_importance_norm`` (0–1)
        - ``ecosystem_water_sensitivity_score`` (weighted multi-factor index)
    """
    # Resolve paths
    wetlands_path = Path(wetlands_path)
    national_parks_path = Path(national_parks_path)
    nature_parks_path = Path(nature_parks_path)
    groundwater_bodies_path = Path(groundwater_bodies_path)
    aquifer_boundaries_path = Path(aquifer_boundaries_path)
    drought_index_path = Path(drought_index_path)
    fault_lines_path = Path(fault_lines_path)

    # ------------------------------------------------------------------
    # 1. Load input layers
    # ------------------------------------------------------------------
    wetlands_gdf = gpd.read_file(wetlands_path)
    national_parks_gdf = gpd.read_file(national_parks_path)
    nature_parks_gdf = gpd.read_file(nature_parks_path)
    groundwater_gdf = gpd.read_file(groundwater_bodies_path)
    aquifer_gdf = gpd.read_file(aquifer_boundaries_path)
    drought_gdf = gpd.read_file(drought_index_path)
    fault_lines_gdf = gpd.read_file(fault_lines_path)

    # Combine protected areas (National Parks + Nature Parks) as primary ecosystem units
    national_parks_gdf = national_parks_gdf.copy()
    national_parks_gdf["ecosystem_type"] = "National Park"
    nature_parks_gdf = nature_parks_gdf.copy()
    nature_parks_gdf["ecosystem_type"] = "Nature Park"

    # Ensure matching CRS between parks
    nature_parks_gdf = _ensure_matching_crs(
        national_parks_gdf, nature_parks_gdf, "Nature Parks"
    )

    # Combine into single ecosystems GeoDataFrame
    ecosystems_gdf = gpd.GeoDataFrame(
        pd.concat([national_parks_gdf, nature_parks_gdf], ignore_index=True),
        crs=national_parks_gdf.crs,
    )

    if ecosystems_gdf.empty:
        raise ValueError("No protected areas found in input datasets.")

    # Add ecosystem ID for tracking through overlays
    ecosystems_gdf = ecosystems_gdf.reset_index(drop=True)
    ecosystems_gdf["ecosystem_id"] = ecosystems_gdf.index

    # ------------------------------------------------------------------
    # 2. Overlay drought index with ecosystems
    # ------------------------------------------------------------------
    drought_gdf = _ensure_matching_crs(
        ecosystems_gdf, drought_gdf, "Drought index"
    )

    # Spatial overlay: intersect ecosystems with drought zones
    ecosystems_drought = gpd.overlay(
        ecosystems_gdf[["ecosystem_id", "geometry"]],
        drought_gdf,
        how="intersection",
    )

    if ecosystems_drought.empty:
        # If no overlap, assign default drought values
        ecosystems_gdf[drought_severity_column] = 0.0
    else:
        # Aggregate drought severity per ecosystem (use maximum if multiple zones overlap)
        if drought_severity_column in ecosystems_drought.columns:
            drought_by_ecosystem = (
                ecosystems_drought.groupby("ecosystem_id")[drought_severity_column]
                .max()
            )
            ecosystems_gdf[drought_severity_column] = (
                ecosystems_gdf["ecosystem_id"]
                .map(drought_by_ecosystem)
                .fillna(0.0)
            )
        else:
            ecosystems_gdf[drought_severity_column] = 0.0

    # ------------------------------------------------------------------
    # 3. Overlay groundwater bodies with ecosystems
    # ------------------------------------------------------------------
    groundwater_gdf = _ensure_matching_crs(
        ecosystems_gdf, groundwater_gdf, "Groundwater bodies"
    )

    ecosystems_gw = gpd.overlay(
        ecosystems_gdf[["ecosystem_id", "geometry"]],
        groundwater_gdf,
        how="intersection",
    )

    if ecosystems_gw.empty:
        ecosystems_gdf[groundwater_sensitivity_column] = 0.0
    else:
        # Aggregate groundwater sensitivity per ecosystem (use maximum)
        if groundwater_sensitivity_column in ecosystems_gw.columns:
            gw_by_ecosystem = (
                ecosystems_gw.groupby("ecosystem_id")[groundwater_sensitivity_column]
                .max()
            )
            ecosystems_gdf[groundwater_sensitivity_column] = (
                ecosystems_gdf["ecosystem_id"]
                .map(gw_by_ecosystem)
                .fillna(0.0)
            )
        else:
            ecosystems_gdf[groundwater_sensitivity_column] = 0.0

    # ------------------------------------------------------------------
    # 4. Compute distance to fault lines
    # ------------------------------------------------------------------
    fault_lines_gdf = _ensure_matching_crs(
        ecosystems_gdf, fault_lines_gdf, "Fault lines"
    )

    # Use projected CRS for distance calculations
    if ecosystems_gdf.crs is None or ecosystems_gdf.crs.is_geographic:
        work_crs = "EPSG:3857"
    else:
        work_crs = ecosystems_gdf.crs

    ecosystems_proj = ecosystems_gdf.to_crs(work_crs)
    fault_lines_proj = fault_lines_gdf.to_crs(work_crs)

    # Compute minimum distance from each ecosystem to nearest fault line
    ecosystem_centroids = ecosystems_proj.geometry.centroid
    min_fault_distances = []
    for centroid in ecosystem_centroids:
        if centroid is None or centroid.is_empty:
            min_fault_distances.append(np.inf)
        else:
            distances = fault_lines_proj.geometry.distance(centroid)
            min_fault_distances.append(distances.min())

    ecosystems_gdf["fault_distance_m"] = min_fault_distances

    # ------------------------------------------------------------------
    # 5. Compute wetland proximity risk
    # ------------------------------------------------------------------
    wetland_proximity_risk = _compute_wetland_proximity_risk(
        ecosystems_gdf, wetlands_gdf, groundwater_gdf, max_distance_m=max_distance_m
    )
    ecosystems_gdf["wetland_proximity_risk"] = wetland_proximity_risk

    # ------------------------------------------------------------------
    # 6. Compute protected area importance
    # ------------------------------------------------------------------
    protected_area_importance = _compute_protected_area_importance(ecosystems_gdf)
    ecosystems_gdf["protected_area_importance"] = protected_area_importance

    # ------------------------------------------------------------------
    # 7. Normalize components
    # ------------------------------------------------------------------
    drought_severity_raw = pd.to_numeric(
        ecosystems_gdf[drought_severity_column], errors="coerce"
    ).fillna(0.0)
    groundwater_sensitivity_raw = pd.to_numeric(
        ecosystems_gdf[groundwater_sensitivity_column], errors="coerce"
    ).fillna(0.0)

    ecosystems_gdf["drought_norm"] = _normalize_series(drought_severity_raw)
    ecosystems_gdf["groundwater_sensitivity_norm"] = _normalize_series(
        groundwater_sensitivity_raw
    )
    ecosystems_gdf["wetland_proximity_risk_norm"] = _normalize_series(
        wetland_proximity_risk
    )
    ecosystems_gdf["protected_area_importance_norm"] = _normalize_series(
        protected_area_importance
    )

    # ------------------------------------------------------------------
    # 8. Compute Ecosystem Water Sensitivity Score
    # ------------------------------------------------------------------
    ecosystems_gdf["ecosystem_water_sensitivity_score"] = (
        0.35 * ecosystems_gdf["drought_norm"]
        + 0.30 * ecosystems_gdf["groundwater_sensitivity_norm"]
        + 0.20 * ecosystems_gdf["wetland_proximity_risk_norm"]
        + 0.15 * ecosystems_gdf["protected_area_importance_norm"]
    )

    # ------------------------------------------------------------------
    # 9. Optional exports
    # ------------------------------------------------------------------
    if output_geojson_path is not None:
        output_geojson_path = Path(output_geojson_path)
        output_geojson_path.parent.mkdir(parents=True, exist_ok=True)
        ecosystems_gdf.to_file(output_geojson_path, driver="GeoJSON")

    if output_csv_path is not None:
        output_csv_path = Path(output_csv_path)
        output_csv_path.parent.mkdir(parents=True, exist_ok=True)
        # Sort by water sensitivity score (descending) for ranking
        csv_df = ecosystems_gdf.sort_values(
            "ecosystem_water_sensitivity_score", ascending=False
        ).drop(columns="geometry")
        csv_df.to_csv(output_csv_path, index=False)

    return ecosystems_gdf
