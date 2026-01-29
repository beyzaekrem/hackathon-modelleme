#!/usr/bin/env python3
"""
Run Model 3 and generate ecosystem vulnerability analysis.
"""

from pathlib import Path
import os
import geopandas as gpd
from models.ecosystem import build_ecosystem_water_resilience
from analyze_ecosystem_resilience import analyze_ecosystem_vulnerability, generate_executive_summary

# Data directory
DATA_DIR = Path("/Users/beyzaekrem/Downloads")
OUTPUT_DIR = Path(__file__).parent / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)

def find_file(patterns, directory):
    all_files = [f for f in os.listdir(directory) if f.endswith('.geojson')]
    for pattern in patterns:
        pattern_lower = pattern.lower()
        for filename in all_files:
            filename_lower = filename.lower()
            if all(part in filename_lower for part in pattern_lower.split()):
                return directory / filename
    for pattern in patterns:
        pattern_lower = pattern.lower()
        for filename in all_files:
            if pattern_lower in filename.lower():
                return directory / filename
    raise FileNotFoundError(f"Could not find file matching {patterns}")

# Find input files
print("Locating input files...")
wetlands_path = find_file(["sulak"], DATA_DIR)
national_parks_path = find_file(["milli-park"], DATA_DIR)
nature_parks_path = find_file(["tabiat"], DATA_DIR)
groundwater_path = find_file(["akifer"], DATA_DIR)
aquifer_path = find_file(["havza"], DATA_DIR)
drought_path = find_file(["kuraklık", "spi"], DATA_DIR)
faults_path = find_file(["diri-fay"], DATA_DIR)

print("\nRunning Model 3: Ecosystem Water Resilience...")

# Prepare groundwater sensitivity (same as Model 1)
def prepare_groundwater_sensitivity(gdf):
    """Create groundwater_sensitivity column from akifer field."""
    gdf = gdf.copy()
    sensitivity_map = {
        "Verimsiz": 0.2,
        "Sınırlı Verimli": 0.5,
        "Verimli": 0.8,
    }
    gdf["groundwater_sensitivity"] = gdf["akifer"].map(lambda x: sensitivity_map.get(x, 0.5))
    return gdf

def prepare_drought_severity(gdf, column="last12month", buffer_km=50.0):
    """Prepare drought severity from SPI index, creating buffers for point data."""
    import pandas as pd
    gdf = gdf.copy()
    
    # Check if geometries are points
    geom_types = gdf.geometry.geom_type.unique()
    is_point_data = 'Point' in geom_types or (len(geom_types) == 1 and geom_types[0] == 'Point')
    
    if is_point_data:
        if gdf.crs is None or gdf.crs.is_geographic:
            work_crs = "EPSG:32636"
            gdf_proj = gdf.to_crs(work_crs)
        else:
            gdf_proj = gdf.copy()
            work_crs = gdf.crs
        
        buffer_m = buffer_km * 1000
        gdf_proj['geometry'] = gdf_proj.geometry.buffer(buffer_m)
        
        if gdf.crs is None or gdf.crs.is_geographic:
            gdf = gdf_proj.to_crs(gdf.crs if gdf.crs else "EPSG:4326")
        else:
            gdf = gdf_proj.to_crs(gdf.crs)
    
    spi_values = pd.to_numeric(gdf[column], errors="coerce").fillna(0)
    severity = (3 - spi_values) / 6
    severity = severity.clip(0, 1)
    gdf["drought_severity"] = severity
    return gdf

gw_gdf = gpd.read_file(groundwater_path)
gw_gdf = prepare_groundwater_sensitivity(gw_gdf)

drought_gdf = gpd.read_file(drought_path)
drought_gdf = prepare_drought_severity(drought_gdf, column="last12month", buffer_km=50.0)

# Ensure CRS consistency
parks_gdf = gpd.read_file(national_parks_path)
target_crs = parks_gdf.crs if parks_gdf.crs else "EPSG:4326"

if gw_gdf.crs != target_crs:
    gw_gdf = gw_gdf.to_crs(target_crs)
if drought_gdf.crs != target_crs:
    drought_gdf = drought_gdf.to_crs(target_crs)

# Save temporary files
temp_gw_path = OUTPUT_DIR / "temp_groundwater_ecosystem.geojson"
temp_drought_path = OUTPUT_DIR / "temp_drought_ecosystem.geojson"
gw_gdf.to_file(temp_gw_path, driver="GeoJSON")
drought_gdf.to_file(temp_drought_path, driver="GeoJSON")

# Import helper functions
import sys
sys.path.insert(0, str(Path(__file__).parent))

def prepare_groundwater_sensitivity(gdf):
    """Create groundwater_sensitivity column from akifer field."""
    gdf = gdf.copy()
    sensitivity_map = {
        "Verimsiz": 0.2,
        "Sınırlı Verimli": 0.5,
        "Verimli": 0.8,
    }
    gdf["groundwater_sensitivity"] = gdf["akifer"].map(lambda x: sensitivity_map.get(x, 0.5))
    return gdf

def prepare_drought_severity(gdf, column="last12month", buffer_km=50.0):
    """Prepare drought severity from SPI index, creating buffers for point data."""
    import pandas as pd
    gdf = gdf.copy()
    
    # Check if geometries are points
    geom_types = gdf.geometry.geom_type.unique()
    is_point_data = 'Point' in geom_types or (len(geom_types) == 1 and geom_types[0] == 'Point')
    
    if is_point_data:
        if gdf.crs is None or gdf.crs.is_geographic:
            work_crs = "EPSG:32636"
            gdf_proj = gdf.to_crs(work_crs)
        else:
            gdf_proj = gdf.copy()
            work_crs = gdf.crs
        
        buffer_m = buffer_km * 1000
        gdf_proj['geometry'] = gdf_proj.geometry.buffer(buffer_m)
        
        if gdf.crs is None or gdf.crs.is_geographic:
            gdf = gdf_proj.to_crs(gdf.crs if gdf.crs else "EPSG:4326")
        else:
            gdf = gdf_proj.to_crs(gdf.crs)
    
    spi_values = pd.to_numeric(gdf[column], errors="coerce").fillna(0)
    severity = (3 - spi_values) / 6
    severity = severity.clip(0, 1)
    gdf["drought_severity"] = severity
    return gdf

# Run Model 3
output_geojson = OUTPUT_DIR / "model3_ecosystem_resilience.geojson"
output_csv = OUTPUT_DIR / "model3_ecosystem_resilience.csv"

results = build_ecosystem_water_resilience(
    wetlands_path=str(wetlands_path),
    national_parks_path=str(national_parks_path),
    nature_parks_path=str(nature_parks_path),
    groundwater_bodies_path=str(temp_gw_path),
    aquifer_boundaries_path=str(aquifer_path),
    drought_index_path=str(temp_drought_path),
    fault_lines_path=str(faults_path),
    drought_severity_column="drought_severity",
    groundwater_sensitivity_column="groundwater_sensitivity",
    output_geojson_path=str(output_geojson),
    output_csv_path=str(output_csv),
)

print(f"\n✓ Model 3 completed: {len(results)} ecosystems processed")

# Clean up temp files
temp_gw_path.unlink(missing_ok=True)
temp_drought_path.unlink(missing_ok=True)

# Analyze results
print("\n" + "="*60)
print("ECOSYSTEM WATER RESILIENCE ANALYSIS")
print("="*60)

analysis = analyze_ecosystem_vulnerability(results)
summary = generate_executive_summary(analysis)
print(summary)

# Save analysis to file
analysis_path = OUTPUT_DIR / "model3_analysis_summary.txt"
with open(analysis_path, 'w') as f:
    f.write(summary)
print(f"\nAnalysis summary saved to: {analysis_path}")
