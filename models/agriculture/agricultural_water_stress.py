"""
Model 1: Agricultural Water Stress Intelligence.

This module implements a GeoPandas overlay pipeline for a **weighted, multi-factor
water stress index**:

1. Load:
   - Agricultural Business Boundaries
   - Groundwater Bodies
   - SPI Drought Index (as vector polygons with drought attributes)
2. Perform spatial overlay:
   - Intersect agricultural areas with groundwater bodies
   - Overlay / join drought index attributes
3. Compute a scientifically interpretable Agricultural Water Stress Score per
   agricultural zone using **normalized components**:

   - ``drought_norm``               → normalized drought severity (0–1)
   - ``groundwater_norm``           → normalized groundwater sensitivity (0–1)
   - ``agricultural_area_pressure`` → normalized polygon area (0–1)

   The final score is a weighted sum:

       score = (0.45 * drought_norm)
             + (0.35 * groundwater_norm)
             + (0.20 * agricultural_area_pressure)

4. Optionally export results as:
   - GeoJSON for mapping
   - CSV summary table

Assumptions
-----------
- All three inputs are **vector** datasets readable by GeoPandas (e.g. Shapefile,
  GeoPackage, GeoJSON).
- The SPI drought index dataset contains a numeric column representing
  drought severity.
- The groundwater bodies dataset contains a numeric column representing
  groundwater sensitivity.

You can override the default column names through function parameters.
"""

from pathlib import Path
from typing import Optional, Union

import geopandas as gpd
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
        raise ValueError("Base GeoDataFrame (agricultural boundaries) has no CRS set.")
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


def build_agricultural_water_stress(
    agri_boundaries_path: PathLike,
    groundwater_bodies_path: PathLike,
    drought_index_path: PathLike,
    *,
    drought_severity_column: str = "drought_severity",
    groundwater_sensitivity_column: str = "groundwater_sensitivity",
    area_crs: Optional[str] = "EPSG:3857",
    output_geojson_path: Optional[PathLike] = None,
    output_csv_path: Optional[PathLike] = None,
) -> gpd.GeoDataFrame:
    """
    Run the Model 1 geospatial pipeline and return a GeoDataFrame with scores.

    Parameters
    ----------
    agri_boundaries_path:
        Path to the Agricultural Business Boundaries dataset.
    groundwater_bodies_path:
        Path to the Groundwater Bodies dataset.
    drought_index_path:
        Path to the SPI Drought Index dataset (vector polygons with
        a drought severity attribute).
    drought_severity_column:
        Name of the column in the drought index layer representing
        drought severity. Default: ``"drought_severity"``.
    groundwater_sensitivity_column:
        Name of the column in the groundwater bodies layer representing
        groundwater sensitivity. Default: ``"groundwater_sensitivity"``.
    area_crs:
        CRS to use for area calculation. If ``None``, area is computed
        in the input CRS of the overlay result. Default: ``"EPSG:3857"``.
    output_geojson_path:
        Optional path where a GeoJSON file with full geometries and
        attributes will be written.
    output_csv_path:
        Optional path where a CSV summary (attributes only, no geometry)
        will be written.

    Returns
    -------
    geopandas.GeoDataFrame
        GeoDataFrame with intersected geometries and the following columns:

        - ``drought_norm`` (0–1)
        - ``groundwater_norm`` (0–1)
        - ``agricultural_area_pressure`` (0–1)
        - ``final_water_stress_score`` (weighted multi-factor index)

        For backwards compatibility, an alias column
        ``agricultural_water_stress_score`` is also provided.
    """
    # Resolve paths (for nicer errors and consistency)
    agri_boundaries_path = Path(agri_boundaries_path)
    groundwater_bodies_path = Path(groundwater_bodies_path)
    drought_index_path = Path(drought_index_path)

    # ------------------------------------------------------------------
    # 1. Load input layers
    # ------------------------------------------------------------------
    agri_gdf = gpd.read_file(agri_boundaries_path)
    gw_gdf = gpd.read_file(groundwater_bodies_path)
    drought_gdf = gpd.read_file(drought_index_path)

    # ------------------------------------------------------------------
    # 2. Harmonise CRS between layers
    # ------------------------------------------------------------------
    gw_gdf = _ensure_matching_crs(agri_gdf, gw_gdf, "Groundwater bodies")
    drought_gdf = _ensure_matching_crs(agri_gdf, drought_gdf, "Drought index")

    # ------------------------------------------------------------------
    # 3. Spatial overlay: agriculture ∩ groundwater
    # ------------------------------------------------------------------
    agri_gw = gpd.overlay(agri_gdf, gw_gdf, how="intersection")

    # If the overlay is empty, short-circuit early
    if agri_gw.empty:
        agri_gw["area"] = []
        agri_gw["agricultural_area_pressure"] = []
        agri_gw["drought_norm"] = []
        agri_gw["groundwater_norm"] = []
        agri_gw["final_water_stress_score"] = []
        agri_gw["agricultural_water_stress_score"] = []
        return agri_gw

    # ------------------------------------------------------------------
    # 4. Overlay / join drought index
    # ------------------------------------------------------------------
    # We use overlay to get geometries segmented by drought index polygons.
    agri_gw_drought = gpd.overlay(agri_gw, drought_gdf, how="intersection")

    if agri_gw_drought.empty:
        agri_gw_drought["area"] = []
        agri_gw_drought["agricultural_area_pressure"] = []
        agri_gw_drought["drought_norm"] = []
        agri_gw_drought["groundwater_norm"] = []
        agri_gw_drought["final_water_stress_score"] = []
        agri_gw_drought["agricultural_water_stress_score"] = []
        return agri_gw_drought

    # ------------------------------------------------------------------
    # 5. Compute area and normalized area (agricultural area pressure)
    # ------------------------------------------------------------------
    if area_crs is not None:
        work_gdf = agri_gw_drought.to_crs(area_crs)
    else:
        work_gdf = agri_gw_drought

    # Area is in square units of the chosen CRS (e.g. square metres for EPSG:3857).
    areas = work_gdf.geometry.area
    agricultural_area_pressure = _normalize_series(areas)

    agri_gw_drought = agri_gw_drought.copy()
    agri_gw_drought["area"] = areas
    agri_gw_drought["agricultural_area_pressure"] = agricultural_area_pressure

    # ------------------------------------------------------------------
    # 6. Validate required columns for score
    # ------------------------------------------------------------------
    missing_cols = [
        col
        for col in (drought_severity_column, groundwater_sensitivity_column)
        if col not in agri_gw_drought.columns
    ]
    if missing_cols:
        missing_str = ", ".join(missing_cols)
        raise KeyError(
            f"Missing required columns for score computation: {missing_str}. "
            "Ensure these fields exist in the input datasets or pass the correct "
            "column names to `build_agricultural_water_stress`."
        )

    # ------------------------------------------------------------------
    # 7. Compute normalized components and final Water Stress Score
    # ------------------------------------------------------------------
    drought_severity_raw = agri_gw_drought[drought_severity_column].astype(float)
    groundwater_sensitivity_raw = agri_gw_drought[
        groundwater_sensitivity_column
    ].astype(float)

    drought_norm = _normalize_series(drought_severity_raw)
    groundwater_norm = _normalize_series(groundwater_sensitivity_raw)

    agri_gw_drought["drought_norm"] = drought_norm
    agri_gw_drought["groundwater_norm"] = groundwater_norm

    final_score = (
        0.45 * drought_norm
        + 0.35 * groundwater_norm
        + 0.20 * agri_gw_drought["agricultural_area_pressure"]
    )

    agri_gw_drought["final_water_stress_score"] = final_score

    # Backwards-compatible alias
    agri_gw_drought["agricultural_water_stress_score"] = final_score

    # ------------------------------------------------------------------
    # 8. Optional exports
    # ------------------------------------------------------------------
    if output_geojson_path is not None:
        output_geojson_path = Path(output_geojson_path)
        output_geojson_path.parent.mkdir(parents=True, exist_ok=True)
        agri_gw_drought.to_file(output_geojson_path, driver="GeoJSON")

    if output_csv_path is not None:
        output_csv_path = Path(output_csv_path)
        output_csv_path.parent.mkdir(parents=True, exist_ok=True)
        # Drop geometry for a clean tabular export
        non_geo_df = pd.DataFrame(agri_gw_drought.drop(columns="geometry"))
        non_geo_df.to_csv(output_csv_path, index=False)

    return agri_gw_drought

