# MCA Lead Intelligence - Phase 1

A Python system that detects business events (UCC filings, hiring, permits) indicating MCA capital need, scores them using a calibrated framework, and outputs broker-ready leads.

**Core Question: "What just happened that makes an MCA inevitable and urgent?"**

## Features

- **Signal Harvesting**: Collect UCC filings from Florida Secretary of State (sunbiz.org)
- **MCA Detection**: Identify MCA-related filings using known lender database and pattern matching
- **Industry Classification**: Automatic industry detection from business names
- **FIT Scoring**: Score leads based on industry propensity and time in business
- **Priority Assignment**: P1-P5 priority levels based on composite scores
- **CSV Export**: Generate broker-ready lead lists

## Quick Start

### Installation

```bash
# Clone and enter directory
cd mca-lead-intelligence

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -e .

# For development
pip install -e ".[dev]"
```

### Basic Usage

```bash
# Run harvest from CSV file
python -m src.cli harvest -i data/sample_ucc_filings.csv -o output/leads.csv

# Harvest MCA-related leads only
python -m src.cli harvest -i data/ucc_filings.csv --mca-only

# With date range filter
python -m src.cli harvest -i data/ucc_filings.csv --start-date 2024-01-01 --end-date 2024-01-31

# Persist to database
python -m src.cli harvest -i data/ucc_filings.csv --persist
```

### Python API

```python
from src.pipeline import run_pipeline

# Generate leads from CSV
leads = run_pipeline(
    file_path="data/ucc_filings.csv",
    output_path="output/leads.csv",
    mca_only=True,
)

print(f"Generated {len(leads)} leads")
```

## Project Structure

```
mca-lead-intelligence/
├── src/
│   ├── harvesters/
│   │   ├── base.py           # Abstract harvester interface
│   │   ├── mca_detector.py   # MCA lender/pattern detection
│   │   └── ucc.py            # Florida UCC harvester
│   ├── models/
│   │   ├── signal.py         # Signal event model
│   │   ├── business.py       # Business entity model
│   │   └── lead.py           # Lead model
│   ├── scoring/
│   │   ├── industry_classifier.py  # Industry classification
│   │   ├── fit.py            # FIT dimension scoring
│   │   └── composite.py      # Combined scoring
│   ├── utils/
│   │   ├── config.py         # Configuration loader
│   │   ├── database.py       # Database setup
│   │   └── exporter.py       # CSV/Excel export
│   ├── pipeline.py           # Main orchestration
│   └── cli.py                # Command-line interface
├── config/
│   ├── scoring.yaml          # Scoring weights/thresholds
│   ├── industries.yaml       # Industry classification
│   └── mca_lenders.yaml      # Known MCA funders
├── data/                     # Input data files
├── output/                   # Generated leads
└── tests/                    # Test suite
```

## Scoring System

### FIT Score (0-100)

FIT measures how well a business fits the MCA customer profile:

| Component | Points | Description |
|-----------|--------|-------------|
| Industry Propensity | 0-10 | Based on industry's historical MCA usage |
| Time in Business | 0-5 | Maturity indicator |

**Industry Propensity Scores:**
- Very High (10): Restaurants, Trucking, Construction, HVAC
- High (8): Auto Services, Retail, Healthcare, Salons
- Moderate (5): Manufacturing, Wholesale, Landscaping
- Lower (2): Consulting, Technology, Real Estate

**Time in Business Scores:**
- 5+ years: 5 points
- 3-5 years: 4 points
- 2-3 years: 3 points
- 1-2 years: 2 points
- <1 year: 0 points (flagged as NURTURE)

### Priority Levels

| Priority | Score Range | Action |
|----------|-------------|--------|
| P1 | 75-100 | Immediate outreach |
| P2 | 60-74 | High priority follow-up |
| P3 | 45-59 | Standard follow-up |
| P4 | 30-44 | Nurture sequence |
| P5 | 0-29 | Long-term nurture |

### MCA Detection

Known MCA lenders are detected by matching secured party names:
- OnDeck Capital
- Credibly
- Rapid Finance
- Fundbox
- Kabbage
- BlueVine
- Square Capital
- PayPal Working Capital
- Libertas Funding
- Forward Financing
- Pearl Capital
- And many more...

Pattern-based detection looks for:
- "Merchant Cash" / "Revenue Purchase" / "Future Receivables"
- All-assets collateral descriptions
- Credit card receivables mentions

## Configuration

All scoring parameters are configurable via YAML files in `config/`:

### scoring.yaml
```yaml
weights:
  fit: 1.0      # Phase 1: FIT only
  intent: 0.0   # Phase 2
  timing: 0.0   # Phase 3

priority_thresholds:
  p1:
    min_score: 75
    max_score: 100
```

### industries.yaml
```yaml
industries:
  restaurants:
    propensity: 10
    keywords:
      - "restaurant"
      - "pizzeria"
      - "cafe"
```

### mca_lenders.yaml
```yaml
mca_lenders:
  - "OnDeck Capital"
  - "Credibly"
  # ...

detection_patterns:
  secured_party_patterns:
    - "Merchant Cash"
    - "Future Receivables"
```

## Data Models

### Signal
Represents a business event (UCC filing, etc.):
- Signal type (UCC_FILING, UCC_TERMINATION, etc.)
- Business identifier and name
- Signal date and source
- Raw data (full original record)
- Metadata (MCA detection results)

### Business
Represents a business entity:
- Legal name and DBA
- Address and state
- Formation date
- Classified industry

### Lead
Represents a scored, actionable lead:
- FIT score (0-100)
- Composite score
- Priority level (P1-P5)
- Score breakdown for explainability

## Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/test_mca_detector.py -v
```

## Phase 1 Success Criteria

- [x] Ingest UCC filings from CSV/JSON files
- [x] Identify MCA-related UCCs with >90% accuracy
- [x] Classify industries from business names
- [x] Calculate FIT scores
- [x] Generate scored lead CSV
- [x] Full traceability: lead → signal → raw data

## Future Phases

### Phase 2: INTENT Dimension
- UCC refinance window scoring
- MCA stack detection
- Payment behavior signals

### Phase 3: TIMING Dimension
- Signal freshness scoring
- Seasonal patterns
- Economic indicators

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| DATABASE_URL | sqlite:///./data/mca_leads.db | Database connection string |
| MCA_CONFIG_DIR | ./config | Configuration directory |
| SQL_ECHO | false | Enable SQL query logging |

## License

MIT License
