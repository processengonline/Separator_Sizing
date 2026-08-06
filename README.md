# Separator Sizing Tool (2-Phase & 3-Phase)

## Overview

This repository contains a Python-based separator sizing tool for preliminary design and verification of **horizontal 2-phase and 3-phase separators** used in oil & gas processing facilities.

The tool automates sizing calculations typically performed in engineering spreadsheets by implementing industry-recognized design methodologies from **API 12J**, **GPSA Engineering Data Book**, and common EPC engineering practices.

The objective is to determine an optimum separator diameter and length while satisfying gas handling capacity, liquid retention requirements, and recommended vessel geometry constraints.

---

# Engineering Objectives

The sizing methodology evaluates separator dimensions against multiple design criteria:

- Gas handling capacity using the **Souders-Brown (K-factor) method**
- Oil and water residence time requirements
- Liquid holdup volume
- Vessel geometry (L/D ratio)
- Operating velocity verification
- Preliminary separator sizing for FEED and Detailed Engineering

The tool is intended for conceptual and preliminary design and can be expanded to include detailed mechanical and process checks.

---

# Design Standards & References

The sizing methodology is based on:

- API 12J – Specification for Oil and Gas Separators
- GPSA Engineering Data Book
- Campbell Process Engineering Guidelines
- Company Engineering Standards (where applicable)

---

# Features

- Horizontal 2-phase separator sizing
- Horizontal 3-phase separator sizing
- Gas capacity calculation using Souders-Brown equation
- Liquid residence time calculation
- Required liquid holdup volume estimation
- Diameter and length iteration
- Automatic L/D ratio verification
- Gas velocity validation
- API/GPSA compliance checks
- Modular Python architecture for future enhancements

---

# Repository Structure

```text
Separator-Sizing/
│
├── README.md                     # Project documentation
├── separator_sizing.py           # Main calculation engine
├── inputs.yaml                   # Design inputs
├── examples/
│   ├── two_phase_case.yaml
│   ├── three_phase_case.yaml
│   └── sample_results.md
├── results/
│   ├── sizing_report.txt
│   └── sizing_summary.csv
├── utils/
│   ├── calculations.py
│   ├── geometry.py
│   └── validation.py
└── docs/
    ├── methodology.md
    ├── equations.md
    └── references.md
```

---

# Input Parameters

The tool accepts process and design data through a YAML configuration file.

### Process Conditions

- Operating pressure
- Operating temperature
- Gas flow rate
- Oil flow rate
- Water flow rate

### Fluid Properties

- Gas density
- Oil density
- Water density
- Gas viscosity
- Liquid viscosity
- Surface tension

### Design Criteria

- K-factor
- Required residence time
- Design droplet size
- Maximum allowable gas velocity
- Target L/D ratio
- Separator orientation

---

# Engineering Methodology

The sizing workflow follows the sequence below:

1. Import operating conditions and fluid properties.
2. Calculate maximum allowable gas velocity using the Souders-Brown equation.
3. Determine the minimum gas flow area.
4. Calculate required liquid retention volume based on residence time.
5. Iterate through trial vessel diameters.
6. Determine the minimum vessel length satisfying:
   - Gas capacity
   - Liquid holdup
   - Residence time
   - Recommended L/D ratio
7. Select the smallest vessel meeting all design criteria.
8. Generate a sizing report.

---

# Usage

Clone the repository:

```bash
git clone https://github.com/<username>/Separator-Sizing.git
cd Separator-Sizing
```

Install dependencies:

```bash
pip install pyyaml
```

Run the sizing tool:

```bash
python separator_sizing.py inputs.yaml
```

---

# Sample Output

```text
---------------------------------------
Separator Sizing Results
---------------------------------------

Recommended Diameter : 1.80 m

Recommended Length   : 7.20 m

Gas Velocity         : 0.82 m/s

Allowable Velocity   : 0.95 m/s

Residence Time       : 4.8 min

L/D Ratio            : 4.0

Gas Capacity Check   : PASS

Residence Time Check : PASS

API Geometry Check   : PASS

Overall Status       : ACCEPTABLE
```

---

# Future Enhancements

The current version provides preliminary sizing. Planned enhancements include:

- Vertical separator sizing
- Inlet diverter sizing
- Wire mesh demister sizing
- Mist extractor pressure drop
- Weir design
- Oil-water interface calculations
- Boot sizing
- Slug volume calculations
- Liquid level controller sizing
- PSV relief load estimation
- Mechanical vessel weight estimation
- Interactive graphical user interface (GUI)
- Excel and PDF report generation

---

# Engineering Skills Demonstrated

- Process Equipment Design
- Separator Sizing
- Oil & Gas Processing
- Python for Process Engineering
- Process Automation
- API 12J
- GPSA Engineering Data Book
- Process Design Calculations
- Equipment Rating
- FEED & Detailed Engineering

---

# Disclaimer

This repository is intended for educational, portfolio, and preliminary engineering purposes. Final equipment sizing should always be verified against project specifications, applicable design codes, client standards, and detailed engineering calculations.

---

# Author

**Shubham**

**Process Engineer | 12+ Years Experience**

Specializing in:

- Process Simulation (Aspen HYSYS & Honeywell UniSim)
- Oil & Gas Processing
- LNG & GTL Facilities
- Process Equipment Design
- EPC Detailed Engineering
- Plant Troubleshooting
- Digital Engineering & Python Automation
