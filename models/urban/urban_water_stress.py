"""
Model 2: Urban Water Stress Intelligence.

This module implements a GeoPandas-based pipeline for city-level water stress analysis:

1. Load:
   - Population Grid 2024 (raster or vector grid cells with population counts)
   - Drinking Water Sources (point or polygon features)
   - Dams and Reservoirs (point or polygon features with capacity attributes)
   - City Atlas boundaries (polygon features)
2. Spatially aggregate population per city boundary
3. Estimate available water supply per city based on:
   - Distance to drinking water sources
   - Distance to dams
   - Dam capacity attributes (if available)
4. Compute Urban Water Stress Score per city:
   score = population_pressure / estimated_water_supply
5. Export:
   - GeoJSON with city polygons + score
   - CSV ranking cities by highest water stress

Assumptions
-----------
- Population Grid can be loaded as a vector dataset (GeoPackage/Shapefile with grid cells)
  or will be rasterized if provided as raster.
- Drinking Water Sources and Dams are point or polygon features readable by GeoPandas.
- City boundaries are polygon features.
- If dam capacity column is missing, supply estimation uses distance-based weighting only.

You can override default column names through function parameters.
"""

from pathlib import Path
from typing import Optional, Union

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import Point


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


def _aggregate_population_per_city(
    cities_gdf: gpd.GeoDataFrame, population_gdf: gpd.GeoDataFrame
) -> gpd.GeoDataFrame:
    """
    Spatially aggregate population from grid cells to city boundaries.

    Parameters
    ----------
    cities_gdf:
        City boundaries GeoDataFrame.
    population_gdf:
        Population grid GeoDataFrame (grid cells with population counts).

    Returns
    -------
    geopandas.GeoDataFrame
        Cities GeoDataFrame with added 'total_population' column.
    """
    # Ensure matching CRS
    population_gdf = _ensure_matching_crs(cities_gdf, population_gdf, "Population grid")

    # Find population column (common names)
    pop_col = None
    for col_name in ["population", "pop", "pop_total", "POP", "POP_TOTAL", "value"]:
        if col_name in population_gdf.columns:
            pop_col = col_name
            break

    if pop_col is None:
        # Try to find any numeric column that might be population
        numeric_cols = population_gdf.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) > 0:
            pop_col = numeric_cols[0]
        else:
            raise ValueError(
                "Could not identify population column in population grid. "
                "Expected column names: 'population', 'pop', 'pop_total', 'POP', 'POP_TOTAL', or 'value'."
            )

    # Use a projected CRS for area calculation
    if cities_gdf.crs is not None and not cities_gdf.crs.is_geographic:
        area_crs = cities_gdf.crs
    else:
        area_crs = "EPSG:3857"

    # Project for area calculations
    cities_proj = cities_gdf.to_crs(area_crs).copy()
    grid_proj = population_gdf.to_crs(area_crs).copy()

    # Compute grid cell areas
    grid_proj["grid_area"] = grid_proj.geometry.area

    # Aggregate population per city using spatial join and area weighting
    city_pop = {}
    for city_idx, city_row in cities_proj.iterrows():
        city_geom = city_row.geometry
        total_pop = 0.0

        # Find intersecting grid cells
        intersecting_grids = grid_proj[grid_proj.geometry.intersects(city_geom)]

        for grid_idx, grid_row in intersecting_grids.iterrows():
            grid_geom = grid_row.geometry
            grid_area = grid_row["grid_area"]

            if grid_area > 0:
                # Compute intersection area
                intersection = city_geom.intersection(grid_geom)
                if not intersection.is_empty:
                    intersection_area = intersection.area
                    # Area-weighted population: (intersection_area / grid_area) * population
                    pop_value = pd.to_numeric(grid_row[pop_col], errors="coerce")
                    if pd.notna(pop_value) and pop_value > 0:
                        weighted_pop = (intersection_area / grid_area) * pop_value
                        total_pop += weighted_pop

        city_pop[city_idx] = total_pop

    cities_gdf = cities_gdf.copy()
    cities_gdf["total_population"] = cities_gdf.index.map(city_pop).fillna(0.0)

    return cities_gdf


def _estimate_water_supply_per_city(
    cities_gdf: gpd.GeoDataFrame,
    water_sources_gdf: gpd.GeoDataFrame,
    dams_gdf: gpd.GeoDataFrame,
    *,
    dam_capacity_column: Optional[str] = "capacity",
    max_distance_km: float = 50.0,
) -> gpd.GeoDataFrame:
    """
    Estimate available water supply per city based on proximity to sources and dams.

    Parameters
    ----------
    cities_gdf:
        City boundaries GeoDataFrame.
    water_sources_gdf:
        Drinking water sources GeoDataFrame (points or polygons).
    dams_gdf:
        Dams and reservoirs GeoDataFrame (points or polygons).
    dam_capacity_column:
        Name of the column in dams_gdf representing capacity (e.g., in cubic meters).
        If None or missing, distance-based weighting only.
    max_distance_km:
        Maximum distance (in km) to consider sources/dams. Default: 50 km.

    Returns
    -------
    geopandas.GeoDataFrame
        Cities GeoDataFrame with added 'estimated_water_supply' column.
    """
    # Ensure matching CRS (use a projected CRS for distance calculations)
    if cities_gdf.crs is None or cities_gdf.crs.is_geographic:
        work_crs = "EPSG:3857"  # Web Mercator for distance calculations
    else:
        work_crs = cities_gdf.crs

    cities_proj = cities_gdf.to_crs(work_crs)
    water_sources_proj = _ensure_matching_crs(
        cities_proj, water_sources_gdf, "Water sources"
    ).to_crs(work_crs)
    dams_proj = _ensure_matching_crs(cities_proj, dams_gdf, "Dams").to_crs(work_crs)

    # Convert max_distance to CRS units (meters for EPSG:3857)
    max_distance_m = max_distance_km * 1000

    # Compute city centroids for distance calculations
    cities_proj = cities_proj.copy()
    cities_proj["centroid"] = cities_proj.geometry.centroid

    # Extract centroids as points for distance calculations
    city_centroids = cities_proj["centroid"].values

    # Estimate supply from water sources (distance-weighted)
    supply_from_sources = []
    for centroid in city_centroids:
        if centroid is None or centroid.is_empty:
            supply_from_sources.append(0.0)
            continue

        # Find nearest water sources within max_distance
        distances = water_sources_proj.geometry.distance(centroid)
        nearby_sources = water_sources_proj[distances <= max_distance_m]

        if nearby_sources.empty:
            supply_from_sources.append(0.0)
        else:
            # Inverse distance weighting: closer sources contribute more
            # Supply = sum(1 / (1 + distance_km))
            distances_km = distances[distances <= max_distance_m] / 1000.0
            supply = (1.0 / (1.0 + distances_km)).sum()
            supply_from_sources.append(supply)

    # Estimate supply from dams (distance + capacity weighted)
    supply_from_dams = []
    has_capacity = dam_capacity_column and dam_capacity_column in dams_proj.columns

    for centroid in city_centroids:
        if centroid is None or centroid.is_empty:
            supply_from_dams.append(0.0)
            continue

        # Find nearest dams within max_distance
        distances = dams_proj.geometry.distance(centroid)
        nearby_dams = dams_proj[distances <= max_distance_m]

        if nearby_dams.empty:
            supply_from_dams.append(0.0)
        else:
            distances_km = distances[distances <= max_distance_m] / 1000.0

            if has_capacity:
                # Capacity-weighted inverse distance: capacity / (1 + distance_km)
                capacities = pd.to_numeric(
                    nearby_dams[dam_capacity_column], errors="coerce"
                ).fillna(0.0)
                # Normalize capacity to reasonable scale (assume cubic meters)
                # Use log scale to handle large variations
                capacities_norm = np.log1p(capacities / 1e6)  # Normalize by 1M m³
                supply = (capacities_norm / (1.0 + distances_km)).sum()
            else:
                # Distance-weighted only (same as water sources)
                supply = (1.0 / (1.0 + distances_km)).sum()

            supply_from_dams.append(supply)

    # Combine supply estimates (weighted sum)
    # Water sources: 0.4 weight, Dams: 0.6 weight (dams typically more reliable)
    total_supply = (
        0.4 * np.array(supply_from_sources) + 0.6 * np.array(supply_from_dams)
    )

    cities_gdf = cities_gdf.copy()
    cities_gdf["estimated_water_supply"] = total_supply

    # Avoid division by zero later: set minimum supply
    min_supply = cities_gdf["estimated_water_supply"][
        cities_gdf["estimated_water_supply"] > 0
    ].min()
    if pd.isna(min_supply) or min_supply <= 0:
        min_supply = 0.001
    cities_gdf["estimated_water_supply"] = cities_gdf["estimated_water_supply"].clip(
        lower=min_supply
    )

    return cities_gdf


def build_urban_water_stress(
    city_boundaries_path: PathLike,
    population_grid_path: PathLike,
    water_sources_path: PathLike,
    dams_path: PathLike,
    *,
    population_column: Optional[str] = None,
    dam_capacity_column: Optional[str] = "capacity",
    max_distance_km: float = 50.0,
    output_geojson_path: Optional[PathLike] = None,
    output_csv_path: Optional[PathLike] = None,
) -> gpd.GeoDataFrame:
    """
    Run the Model 2 geospatial pipeline and return a GeoDataFrame with urban water stress scores.

    Parameters
    ----------
    city_boundaries_path:
        Path to the City Atlas boundaries dataset (polygon features).
    population_grid_path:
        Path to the Population Grid 2024 dataset (vector grid cells with population counts).
    water_sources_path:
        Path to the Drinking Water Sources dataset (point or polygon features).
    dams_path:
        Path to the Dams and Reservoirs dataset (point or polygon features).
    population_column:
        Name of the population column in the grid. If None, auto-detects common names.
    dam_capacity_column:
        Name of the capacity column in dams dataset. Default: ``"capacity"``.
        If None or column missing, uses distance-based weighting only.
    max_distance_km:
        Maximum distance (km) to consider water sources and dams. Default: 50 km.
    output_geojson_path:
        Optional path where a GeoJSON file with city polygons and scores will be written.
    output_csv_path:
        Optional path where a CSV ranking cities by highest water stress will be written.

    Returns
    -------
    geopandas.GeoDataFrame
        GeoDataFrame with city polygons and the following columns:

        - ``total_population`` (aggregated from grid)
        - ``estimated_water_supply`` (distance + capacity weighted)
        - ``urban_water_stress_score`` (population_pressure / estimated_water_supply)
    """
    # Resolve paths
    city_boundaries_path = Path(city_boundaries_path)
    population_grid_path = Path(population_grid_path)
    water_sources_path = Path(water_sources_path)
    dams_path = Path(dams_path)

    # ------------------------------------------------------------------
    # 1. Load input layers
    # ------------------------------------------------------------------
    cities_gdf = gpd.read_file(city_boundaries_path)
    population_gdf = gpd.read_file(population_grid_path)
    water_sources_gdf = gpd.read_file(water_sources_path)
    dams_gdf = gpd.read_file(dams_path)

    if cities_gdf.empty:
        raise ValueError("City boundaries dataset is empty.")

    # ------------------------------------------------------------------
    # 2. Aggregate population per city
    # ------------------------------------------------------------------
    cities_gdf = _aggregate_population_per_city(cities_gdf, population_gdf)

    # ------------------------------------------------------------------
    # 3. Estimate water supply per city
    # ------------------------------------------------------------------
    cities_gdf = _estimate_water_supply_per_city(
        cities_gdf,
        water_sources_gdf,
        dams_gdf,
        dam_capacity_column=dam_capacity_column,
        max_distance_km=max_distance_km,
    )

    # ------------------------------------------------------------------
    # 4. Compute Urban Water Stress Score
    # ------------------------------------------------------------------
    # Score = population_pressure / estimated_water_supply
    # Population pressure is normalized population (0-1 scale)
    population_vals = cities_gdf["total_population"].fillna(0.0)
    max_pop = population_vals.max()
    if max_pop > 0:
        population_pressure = population_vals / max_pop
    else:
        population_pressure = pd.Series(0.0, index=cities_gdf.index)

    cities_gdf = cities_gdf.copy()
    cities_gdf["population_pressure"] = population_pressure
    cities_gdf["urban_water_stress_score"] = (
        cities_gdf["population_pressure"] / cities_gdf["estimated_water_supply"]
    )

    # ------------------------------------------------------------------
    # 5. Optional exports
    # ------------------------------------------------------------------
    if output_geojson_path is not None:
        output_geojson_path = Path(output_geojson_path)
        output_geojson_path.parent.mkdir(parents=True, exist_ok=True)
        cities_gdf.to_file(output_geojson_path, driver="GeoJSON")

    if output_csv_path is not None:
        output_csv_path = Path(output_csv_path)
        output_csv_path.parent.mkdir(parents=True, exist_ok=True)
        # Sort by water stress score (descending) for ranking
        csv_df = cities_gdf.sort_values(
            "urban_water_stress_score", ascending=False
        ).drop(columns="geometry")
        csv_df.to_csv(output_csv_path, index=False)

    return cities_gdf
