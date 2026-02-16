![Python](https://img.shields.io/badge/python-3.10-blue)
![Streamlit](https://img.shields.io/badge/streamlit-%23FF4B4B)
![Status](https://img.shields.io/badge/status-completed-success)
# Smart Water Stress Modeling Platform

A data-oriented modeling platform designed to evaluate water stress conditions using environmental and geographic data, developed as part of a hackathon project.

## Overview

This repository contains a Python-based system for analyzing water stress across different regions. The platform uses environmental input data and performs modular calculations to assess water availability under various conditions. The project also includes a dashboard interface to visualize results and support decision making.

The system was developed in the context of a collaborative hackathon challenge focused on sustainable water management.

## Motivation

Water stress is a critical issue for agriculture, urban planning, and ecosystem sustainability. Traditional approaches often lack data-driven support for understanding local water stress conditions.

The goal of this project is to provide a flexible and extensible framework for analyzing different stress factors related to water availability, with a user-friendly interface for interpretation and visualization.

## Key Features

- Environmental data preprocessing and modeling  
- Water stress evaluation modules  
- Interactive visualization through a dashboard  
- Modular code structure for future extension  
- Designed for readability and reproducibility

## Technologies Used

This project is built using:

- **Python** – Main development language  
- **Pandas** – Data processing and analysis  
- **GeoPandas** – Geospatial data support  
- **Streamlit** – Dashboard interface  
- **Jupyter Notebook** – Research and exploration  
- **Git & GitHub** – Version control

## Repository Structure

The repository is organized as follows:

📁 assets/ # Supporting static assets
📁 datasets/ # Environmental and input datasets
📁 water_stress_dashboard/ # Dashboard front-end files
📄 app.py # Dashboard entry script
📄 components.py # Modular helper functions
📄 main.py # Main execution script
📄 utils.py # Utility functions
📄 water_stress_helpers.py # Water stress logic
📄 requirements.txt # Project dependencies


## Installation and Setup

To run the system locally, follow these steps:

1. Clone the repository:

git clone https://github.com/beyzaekrem/hackathon-modelleme.git


2. Navigate to the project folder:

cd hackathon-modelleme


3. Create a virtual environment and activate it:

python3 -m venv .venv
source .venv/bin/activate


4. Install the required packages:

pip install -r requirements.txt


## Running the Application

To start the dashboard:

streamlit run water_stress_dashboard/app.py


## Example Usage

Example use cases include:

- Evaluating water stress for a specific dataset  
- Examining dashboard output for multiple environmental conditions  
- Modifying water stress logic for extended research

## What I Learned

This project demonstrates the following technical competencies:

- Data processing and transformation  
- Modular Python project design  
- Geospatial data handling with GeoPandas  
- Interactive data visualization with Streamlit  
- Experimentation in research context

## Future Improvements

The current version serves as a prototype and could be extended with:

- Real-time sensor data integration  
- Advanced machine learning models for prediction  
- Cloud-based deployment and API integration  
- Support for additional environmental variables  
- Enhanced visualization and reporting features

## Author

Developed by **Beyza Ekrem**  
Computer Engineering Student
