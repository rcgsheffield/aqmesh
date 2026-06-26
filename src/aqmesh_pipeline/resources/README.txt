AQMesh Air Quality Data
=======================

This directory contains air quality readings collected from AQMesh outdoor sensor pods
deployed across Sheffield. The pipeline runs automatically every hour (at :06 past the
hour, Europe/London time) and keeps all files up to date.


Directory layout
----------------

raw/
  location=<n>/
    param=gas/
      <timestamp>_<seq>.json     Exact API payloads — never modified after writing
    param=particle/
      <timestamp>_<seq>.json

clean/
  location=<n>/
    aqmesh_<n>_gas.csv           Calibrated readings, one row per measurement
    aqmesh_<n>_gas.metadata.json Column descriptions, units, calibration details, and provenance
    aqmesh_<n>_particle.csv
    aqmesh_<n>_particle.metadata.json
    info.json                    Pod hardware and location metadata

resampled/
  location=<n>/
    aqmesh_<n>_gas_daily.csv     Daily averages of the clean readings
    aqmesh_<n>_particle_daily.csv

state/
  pointers.json                  Pipeline progress tracker — do not edit
  assets.json                    Pod registry snapshot — do not edit


File formats
------------

clean/ CSVs: UTF-8, comma-separated, one header row. Timestamps are in UTC.
  Gas parameters (µg/m³ or ppb — check the paired .metadata.json for units per column):
    NO2, CO, SO2, H2S, O3, plus temperature (°C), pressure (hPa), humidity (%RH)
  Particle parameters (µg/m³):
    PM1, PM2.5, PM4, PM10, total particle count (TPC), plus pressure and humidity

  Readings that the sensor flagged as unreliable (e.g. stabilising, not fitted) are
  represented as empty cells (NaN) rather than the raw sentinel values (-999, -1000).
  The reading_status column records the pod's self-reported quality flag for each row.

resampled/ CSVs: same column structure as the corresponding clean/ CSV, with one row
  per calendar day (UTC midnight boundaries). An additional n_readings column records
  how many per-reading observations contributed to each daily mean — use it to filter
  out low-confidence days or apply coverage weighting. Empty bins (no data) are NaN.

raw/ JSON: exact API payloads in the vendor's original format. Use clean/ or
  resampled/ for analysis; raw/ is retained for full provenance and reprocessing.


Further information
-------------------

Full documentation:  https://github.com/rcgsheffield/aqmesh
Contact:             j.heffer@sheffield.ac.uk
