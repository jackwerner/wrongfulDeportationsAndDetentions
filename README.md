# Wrongful Deportation & Detention Dashboard

## Overview
This dashboard visualizes court cases involving wrongful deportation or detention using data from CourtListener. It provides an interactive interface to explore and analyze legal cases related to immigration enforcement actions.

## Features
- **Case Statistics**: View metrics on total wrongful cases, deportation cases, detention cases, and combined cases
- **Interactive Filters**:
  - Court selection
  - Date range
  - Citizenship status
- **Detailed Case Information**:
  - Case grouping by related cases
  - Full case summaries
  - Links to original court documents
- **Data Visualizations**:
  - Cases by Court distribution
  - Timeline of case filings

## Data Source
The dashboard uses data from CourtListener, a free legal research platform maintained by the Free Law Project. The data is filtered using specific search queries focusing on:
- Alien Enemy Act cases
- El Salvador-related cases
- Terrorism confinement center cases
- Cases involving wrongful/unlawful deportation or detention
- Cases filed after March 15th, 2025

## Requirements
- Python 3.x
- Required packages:
  - streamlit
  - pandas
  - matplotlib
  - seaborn

## Installation
1. Clone this repository
2. Install required packages:
```bash
pip install -r requirements.txt
```

## Usage
Run the dashboard using Streamlit:
```bash
streamlit run cl_main.py
```

## Contributing
Contributions are welcome! Please feel free to submit a Pull Request.

## License
[Add your chosen license here]

## Note
This dashboard specifically tracks cases filed after March 2025 related to the Trump administration's invocation of the Alien Enemies Act. Some cases may not appear individually if they are part of larger class action lawsuits.
