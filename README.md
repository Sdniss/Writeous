# 🕯️ Writeous

Kinetic progress tracking for disciplined writing. Monitors `.docx` manuscripts for real-time velocity and structural growth.

## 🚀 Usage

### 1. Monitor
Track word count velocity and section growth in real-time.
```bash
python writeous.py monitor manuscript.docx ./logs --interval 60 --goal 1000
```

### 2. Report
Visualize daily progress via ASCII charts.
```bash
python writeous.py report ./logs/writing_stats.csv
```

## ✨ Features
- **Velocity Tracking**: Real-time word count deltas.
- **Section Awareness**: Detects which chapter is growing (via Word Heading styles).
- **Goal Tracking**: Visual session progress bar.
- **CSV Logging**: Clean data for long-term analysis.

## 📂 Data
Logs are stored in a `writing_stats.csv` with the following:
- `timestamp`, `word_count`, `delta`, `section_count`, `active_section`

## 📝 Authors
- Mehdi
- Stijn

---
*Made for writers who value kinetics over project management.*