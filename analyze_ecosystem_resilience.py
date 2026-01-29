#!/usr/bin/env python3
"""
Ecosystem Water Resilience Analysis

Analyzes ecosystem water sensitivity scores and generates:
- Overall vulnerability assessment
- Risk band distribution
- Spatial concentration patterns
- Key ecological concerns
"""

import geopandas as gpd
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, Tuple


def analyze_ecosystem_vulnerability(
    gdf: gpd.GeoDataFrame,
    score_column: str = "ecosystem_water_sensitivity_score"
) -> Dict[str, object]:
    """
    Analyze ecosystem water sensitivity scores and generate vulnerability assessment.
    
    Parameters
    ----------
    gdf: GeoDataFrame
        Ecosystem data with water sensitivity scores
    score_column: str
        Name of the sensitivity score column (0-1 scale)
    
    Returns
    -------
    dict
        Analysis results with vulnerability metrics and insights
    """
    if score_column not in gdf.columns:
        raise ValueError(f"Score column '{score_column}' not found in data")
    
    scores = gdf[score_column].dropna()
    
    if len(scores) == 0:
        return {
            "error": "No valid scores found in dataset"
        }
    
    # Overall vulnerability level
    mean_score = scores.mean()
    median_score = scores.median()
    std_score = scores.std()
    
    if mean_score < 0.33:
        overall_level = "Low"
        level_description = "Ecosystems demonstrate generally low water sensitivity, indicating relatively stable water-dependent functions."
    elif mean_score < 0.67:
        overall_level = "Moderate"
        level_description = "Ecosystems show moderate water sensitivity, with some areas requiring monitoring and adaptive management."
    else:
        overall_level = "High"
        level_description = "Ecosystems exhibit high water sensitivity, indicating significant vulnerability to water stress and requiring immediate conservation attention."
    
    # Risk band distribution
    high_threshold = 0.7  # Top 30% considered high sensitivity
    medium_threshold = 0.4  # 40-70th percentile considered medium
    
    high_count = (scores >= high_threshold).sum()
    medium_count = ((scores >= medium_threshold) & (scores < high_threshold)).sum()
    low_count = (scores < medium_threshold).sum()
    
    total = len(scores)
    high_pct = (high_count / total) * 100
    medium_pct = (medium_count / total) * 100
    low_pct = (low_count / total) * 100
    
    # Spatial concentration analysis
    # Check if ecosystems are clustered geographically
    if 'geometry' in gdf.columns:
        # Calculate coefficient of variation of scores by spatial proximity
        # Simple approach: check if high-scoring ecosystems are clustered
        high_scores_gdf = gdf[gdf[score_column] >= high_threshold].copy()
        
        if len(high_scores_gdf) > 1:
            # Calculate average distance between high-sensitivity ecosystems
            from shapely.geometry import Point
            centroids = high_scores_gdf.geometry.centroid
            distances = []
            for i, cent1 in enumerate(centroids):
                for cent2 in centroids.iloc[i+1:]:
                    if cent1 is not None and cent2 is not None:
                        dist = cent1.distance(cent2)
                        distances.append(dist)
            
            if distances:
                avg_distance = np.mean(distances)
                # Compare to overall ecosystem distribution
                all_centroids = gdf.geometry.centroid
                all_distances = []
                for i, cent1 in enumerate(all_centroids):
                    for cent2 in all_centroids.iloc[i+1:min(i+10, len(all_centroids))]:
                        if cent1 is not None and cent2 is not None:
                            dist = cent1.distance(cent2)
                            all_distances.append(dist)
                
                if all_distances:
                    overall_avg_distance = np.mean(all_distances)
                    concentration_ratio = avg_distance / overall_avg_distance if overall_avg_distance > 0 else 1.0
                    
                    if concentration_ratio < 0.7:
                        concentration = "Concentrated"
                        concentration_desc = "High-sensitivity ecosystems are spatially clustered, suggesting region-specific vulnerability drivers."
                    elif concentration_ratio > 1.3:
                        concentration = "Dispersed"
                        concentration_desc = "High-sensitivity ecosystems are widely distributed, indicating widespread systemic vulnerability."
                    else:
                        concentration = "Moderate"
                        concentration_desc = "High-sensitivity ecosystems show moderate spatial clustering."
                else:
                    concentration = "Unknown"
                    concentration_desc = "Spatial analysis inconclusive."
            else:
                concentration = "Unknown"
                concentration_desc = "Insufficient high-sensitivity ecosystems for spatial analysis."
        else:
            concentration = "N/A"
            concentration_desc = "Too few high-sensitivity ecosystems for spatial clustering analysis."
    else:
        concentration = "Unknown"
        concentration_desc = "No geometry data available for spatial analysis."
    
    # Key ecological concerns
    concerns = []
    
    # Check component scores if available
    component_cols = [
        "drought_norm",
        "groundwater_sensitivity_norm",
        "wetland_proximity_risk_norm",
        "protected_area_importance_norm"
    ]
    
    available_components = [col for col in component_cols if col in gdf.columns]
    
    if available_components:
        component_means = {col: gdf[col].mean() for col in available_components}
        
        # Identify dominant risk factors
        sorted_components = sorted(component_means.items(), key=lambda x: x[1], reverse=True)
        dominant_factor = sorted_components[0]
        
        if dominant_factor[0] == "drought_norm" and dominant_factor[1] > 0.6:
            concerns.append("Drought stress is the primary driver of ecosystem vulnerability, indicating climate-driven water scarcity.")
        
        if "groundwater_sensitivity_norm" in component_means and component_means["groundwater_sensitivity_norm"] > 0.6:
            concerns.append("High groundwater dependency suggests ecosystems may be vulnerable to aquifer depletion or contamination.")
        
        if "wetland_proximity_risk_norm" in component_means and component_means["wetland_proximity_risk_norm"] > 0.6:
            concerns.append("Wetland proximity risks indicate potential disruption of critical hydrological connectivity.")
        
        if "protected_area_importance_norm" in component_means and component_means["protected_area_importance_norm"] > 0.6:
            concerns.append("High protected area importance scores suggest significant conservation value at risk.")
    
    # General concerns based on score distribution
    if high_pct > 30:
        concerns.append(f"Over {high_pct:.1f}% of ecosystems fall in the high-sensitivity band, indicating widespread vulnerability.")
    
    if mean_score > 0.6:
        concerns.append("Elevated mean sensitivity suggests systemic water stress affecting multiple ecosystem functions.")
    
    if std_score < 0.15:
        concerns.append("Low score variability indicates uniform vulnerability patterns across ecosystems.")
    elif std_score > 0.35:
        concerns.append("High score variability suggests heterogeneous vulnerability, requiring targeted conservation strategies.")
    
    # Ecosystem type analysis if available
    if 'ecosystem_type' in gdf.columns:
        type_scores = gdf.groupby('ecosystem_type')[score_column].mean().sort_values(ascending=False)
        most_vulnerable_type = type_scores.index[0]
        concerns.append(f"'{most_vulnerable_type}' ecosystems show the highest average sensitivity ({type_scores.iloc[0]:.3f}).")
    
    return {
        "overall_vulnerability": {
            "level": overall_level,
            "description": level_description,
            "mean_score": float(mean_score),
            "median_score": float(median_score),
            "std_score": float(std_score),
            "min_score": float(scores.min()),
            "max_score": float(scores.max())
        },
        "risk_distribution": {
            "high_sensitivity": {
                "count": int(high_count),
                "percentage": float(high_pct),
                "threshold": high_threshold
            },
            "medium_sensitivity": {
                "count": int(medium_count),
                "percentage": float(medium_pct),
                "threshold_range": (medium_threshold, high_threshold)
            },
            "low_sensitivity": {
                "count": int(low_count),
                "percentage": float(low_pct),
                "threshold": medium_threshold
            },
            "total_ecosystems": int(total)
        },
        "spatial_pattern": {
            "concentration": concentration,
            "description": concentration_desc
        },
        "ecological_concerns": concerns,
        "component_analysis": {
            col: float(gdf[col].mean()) 
            for col in available_components
        } if available_components else None
    }


def generate_executive_summary(analysis: Dict[str, object]) -> str:
    """
    Generate a concise executive summary from analysis results.
    """
    vuln = analysis["overall_vulnerability"]
    dist = analysis["risk_distribution"]
    spatial = analysis["spatial_pattern"]
    concerns = analysis["ecological_concerns"]
    
    summary = f"""ECOSYSTEM WATER RESILIENCE ASSESSMENT

Overall Vulnerability: {vuln['level']}
{vuln['description']}

Risk Distribution:
- High Sensitivity (≥0.7): {dist['high_sensitivity']['percentage']:.1f}% ({dist['high_sensitivity']['count']} ecosystems)
- Medium Sensitivity (0.4-0.7): {dist['medium_sensitivity']['percentage']:.1f}% ({dist['medium_sensitivity']['count']} ecosystems)
- Low Sensitivity (<0.4): {dist['low_sensitivity']['percentage']:.1f}% ({dist['low_sensitivity']['count']} ecosystems)

Spatial Pattern: {spatial['concentration']}
{spatial['description']}

Key Concerns:
"""
    for i, concern in enumerate(concerns[:5], 1):  # Top 5 concerns
        summary += f"{i}. {concern}\n"
    
    return summary


if __name__ == "__main__":
    # Example usage
    import sys
    
    if len(sys.argv) > 1:
        geojson_path = Path(sys.argv[1])
        if not geojson_path.exists():
            print(f"Error: File not found: {geojson_path}")
            sys.exit(1)
        
        gdf = gpd.read_file(geojson_path)
        analysis = analyze_ecosystem_vulnerability(gdf)
        summary = generate_executive_summary(analysis)
        print(summary)
    else:
        print("Usage: python analyze_ecosystem_resilience.py <path_to_ecosystem_geojson>")
        print("\nExample:")
        print("  python analyze_ecosystem_resilience.py outputs/model3_ecosystem_resilience.geojson")
