# Su Stresi İstihbarat Dashboard'u

Bu proje, **GeoPandas** ile geliştirilmiş üç farklı su stresi analiz modelini içeren kapsamlı bir geospatial analiz pipeline'ıdır.

## Modeller

### Model 1: Tarımsal Su Stresi İstihbaratı
Tarımsal bölgeler için su stresi skorunu hesaplar:
- Tarımsal işletme sınırları ve yeraltı suyu gövdelerinin kesişimi
- Kuraklık indeksi (SPI) özellikleri

### Model 2: Kentsel Su Stresi İstihbaratı
Şehir düzeyinde su stresi analizi:
- Nüfus basıncı
- Su arzı tahmini
- Şehir düzeyinde risk değerlendirmesi

### Model 3: Ekosistem Su Direnci İstihbaratı
Korunan alanlar için su kırılganlığı analizi:
- Kuraklık maruziyeti
- Yeraltı suyu hassasiyeti
- Sulak alan yakınlık riski
- Korunan alan önemi

## Kurulum

1. Sanal ortam oluşturun ve bağımlılıkları yükleyin:

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

2. Giriş veri dosyalarınızı hazırlayın (GeoPandas tarafından desteklenen vektör formatları: Shapefile, GeoPackage, GeoJSON)

## Dashboard Kullanımı

Streamlit dashboard'unu çalıştırmak için:

```bash
streamlit run dashboards/streamlit_app.py
```

Dashboard şu özellikleri içerir:
- 🌾 Tarımsal Su Stresi (Model 1)
- 🏙️ Kentsel Su Stresi (Model 2)
- 🌿 Ekosistem Su Direnci (Model 3)

Her model için:
- İnteraktif haritalar
- En yüksek riskli bölgeler tablosu
- Otomatik içgörüler
- Skor ayrıştırması ve bileşen analizi

## Modelleri Programatik Olarak Çalıştırma

### Model 1

```python
from models.agriculture import build_agricultural_water_stress

results = build_agricultural_water_stress(
    agri_boundaries_path="data/tarım-işletme-sınırları.geojson",
    groundwater_bodies_path="data/akifer-sınırları.geojson",
    drought_index_path="data/kuraklık-spi-indeksi.geojson",
    output_geojson_path="outputs/model1_water_stress.geojson",
    output_csv_path="outputs/model1_water_stress.csv",
)
```

### Model 2

```python
from models.urban import build_urban_water_stress

results = build_urban_water_stress(
    city_boundaries_path="data/şehir-atlası-2019.geojson",
    population_grid_path="data/nüfus-gridli-2024.geojson",
    water_sources_path="data/içme-suyu-kaynakları.geojson",
    dams_path="data/baraj-ve-göletler.geojson",
    output_geojson_path="outputs/model2_urban_water_stress.geojson",
    output_csv_path="outputs/model2_urban_water_stress.csv",
)
```

### Model 3

```python
from models.ecosystem import build_ecosystem_water_resilience

results = build_ecosystem_water_resilience(
    wetlands_path="data/sulak-alanlar.geojson",
    national_parks_path="data/milli-parklar.geojson",
    nature_parks_path="data/tabiat-parkları.geojson",
    groundwater_bodies_path="data/akifer-sınırları.geojson",
    aquifer_boundaries_path="data/havza-sınırları.geojson",
    drought_index_path="data/kuraklık-spi-indeksi.geojson",
    fault_lines_path="data/diri-faylar.geojson",
    output_geojson_path="outputs/model3_ecosystem_resilience.geojson",
    output_csv_path="outputs/model3_ecosystem_resilience.csv",
)
```

## Proje Yapısı

```
deneme/
├── dashboards/          # Streamlit dashboard uygulaması
│   └── streamlit_app.py
├── models/              # Model implementasyonları
│   ├── agriculture/     # Model 1
│   ├── urban/           # Model 2
│   └── ecosystem/       # Model 3
├── outputs/             # Model çıktıları
├── notebooks/           # Jupyter notebook'lar
├── requirements.txt     # Python bağımlılıkları
└── README.md           # Bu dosya
```

## Bağımlılıklar

- geopandas >= 0.14, < 1.0
- pandas >= 2.0, < 3.0
- shapely >= 2.0, < 3.0
- streamlit >= 1.40, < 2.0
- folium >= 0.17, < 0.18
- streamlit-folium >= 0.22, < 0.23

## Analiz ve Raporlar

Proje aşağıdaki analiz ve raporları içerir:

- `executive_summary_ecosystem_resilience.md` - Üst düzey karar vericiler için özet
- `model_reliability_assessment.md` - Model güvenilirlik değerlendirmesi
- `spatial_distribution_narrative.md` - Mekansal dağılım analizi
- `automated_insights.txt` - Otomatik içgörüler

## Lisans

Bu proje açık kaynak kodludur.
