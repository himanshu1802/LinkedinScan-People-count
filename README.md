## 🌐 Live Demo

👉 

# LinkedScan — LinkedIn People Intelligence Platform

![Python](https://img.shields.io/badge/Python-3.10+-blue?style=flat-square&logo=python)
![Flask](https://img.shields.io/badge/Flask-3.0-lightgrey?style=flat-square&logo=flask)
![Selenium](https://img.shields.io/badge/Selenium-4.18-green?style=flat-square&logo=selenium)
![Supabase](https://img.shields.io/badge/Supabase-Cloud--DB-3ECF8E?style=flat-square&logo=supabase)
![License](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)

> A powerful web application to bulk-scrape **LinkedIn company people counts**, filter results by range, analyse performance metrics in real time, and persist history to the cloud via **Supabase**.

---

## 📸 Preview

| Dark Mode | Light Mode |
|-----------|------------|
| Full red-black dashboard with live table | Clean white theme with range filter |

> The UI includes light/dark toggle, live progress bar, real-time analytics charts, completion timer, and a built-in terminal log.

---

## ✨ Features

### 🔍 Scraper
- Upload **CSV or Excel** files containing LinkedIn company URLs
- **Multi-file queue** — upload several files and process them one by one
- **Per-job Pause / Resume / Stop** controls
- **Parallel workers** (1–3) for fast scraping — ~100 companies in 4 minutes with 2 workers
- **Live results table** with search filter and **range filter dropdown**
- Range badges on every row: `0–20`, `21–50`, `51–100`, `101–500`, `501–1K`, `1K–5K`, `5K–10K`, `10K+`
- **Completion time badge** shown when a job finishes
- Export full results or **filtered subset** as `.xlsx` or `.csv`
- Built-in **terminal log** showing real-time status

### 📂 History
- Every completed job saved to **Supabase cloud** (persistent across devices)
- Falls back to **SQLite** on server and **localStorage** in browser
- Download any past run as Excel or CSV at any time
- Identified by a **Device ID** — return from any browser and restore history

### 📊 Analytics
- **Real-time charts** (Chart.js) that update every 3 seconds:
  - Found vs N/A per run (bar chart)
  - Member count distribution by range (doughnut chart)
  - Average scrape time trend (line chart)
  - Success rate trend (line chart)
- KPI cards: Total runs, scraped, found, N/A, success rate, avg time/row

### ⚙️ Settings
- Parallel workers: 1 / 2 / 3
- Random delay window (min / max seconds)
- Retry count on failure
- Toggle headless browser mode
- Toggle user-agent rotation
- Supabase connection management

### 🛡️ Anti-Ban Protection
- Human-like keystroke simulation with random per-key delays
- Random delays between requests (never fixed intervals)
- User-agent rotation across Chrome, Firefox, and Safari
- `navigator.webdriver` spoofed to `undefined`
- `navigator.plugins` set to realistic values
- CDP `userAgent` override per browser session

---

## 🏗️ Project Structure

```
linkedscan/
├── app.py                  # Flask backend (scraper, history, analytics, settings)
├── requirements.txt        # Python dependencies
├── .env.example            # Environment variable template
├── supabase_setup.sql      # Run once in your Supabase SQL Editor
├── linkedscan.db           # Auto-created SQLite database (gitignored)
└── templates/
    └── index.html          # Full frontend (single-file, no build step)
```

---

## 🚀 Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/your-username/linkedscan.git
cd linkedscan
```

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment (optional — can also be done from the UI)

```bash
cp .env.example .env
# Edit .env and add your Supabase URL and key
```

### 4. Run the server

```bash
python app.py
```

### 5. Open in your browser

```
http://localhost:5000
```

---

## ☁️ Supabase Cloud Setup (5 minutes, free)

Supabase gives your history **permanent cloud storage** so results are accessible from any device.

### Step 1 — Create a free Supabase project

1. Go to [supabase.com](https://supabase.com) and sign up (free)
2. Create a new project (any name, any region)

### Step 2 — Run the SQL schema

1. In your Supabase project, open **SQL Editor → New query**
2. **Copy and paste** the contents of `supabase_setup.sql` into the editor
3. Click **Run** — you should see a green success message

> ⚠️ Do not paste the filename — paste the actual SQL code from inside the file.

### Step 3 — Get your credentials

1. Go to **Settings → API** in your Supabase dashboard
2. Copy your **Project URL** and **anon / public key**

### Step 4 — Connect from the app

Either paste credentials into the **Settings → Cloud Sync** section of the UI,
or add them to your `.env` file:

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key-here
```

---

## 📋 Input File Format

Your CSV or Excel file should have a column with LinkedIn company URLs.

**Accepted column names (any one works):**

| Column name | Example value |
|-------------|---------------|
| `linkedin_url` | `https://www.linkedin.com/company/google/` |
| `url` | `https://www.linkedin.com/company/microsoft/` |
| `LinkedIn URL` | `https://www.linkedin.com/company/apple/` |
| `company_url` | `company/amazon` |
| *(first column)* | Falls back automatically if no match found |

All other columns in your file are **preserved** and returned in the output.

**Example `companies.csv`:**

```csv
company_name,linkedin_url
Google,https://www.linkedin.com/company/google/
Microsoft,https://www.linkedin.com/company/microsoft/
Apple,https://www.linkedin.com/company/apple/
```

---

## 📤 Output

The output file contains all original columns plus two new columns:

| Column | Description |
|--------|-------------|
| `associated_members` | Raw member count (e.g. `196543`) or `N/A` |
| `range` | Range bucket (e.g. `10K+`, `1K–5K`) |

---

## ⚡ Performance

| Workers | Min Delay | ~100 companies |
|---------|-----------|----------------|
| 1 worker | 1.5s | ~7 minutes |
| 2 workers | 1.5s | ~4 minutes ← recommended |
| 3 workers | 1.0s | ~2.5 minutes |

> Recommended: Use **2 workers** with **1.5s min delay** for the best balance of speed and account safety.

---

## 🔄 How Cloud History Works

1. When you first open the app, your browser is assigned a **Device ID** (stored in `localStorage`)
2. Every completed scrape job is saved to Supabase tagged with your Device ID
3. When you return — same browser or different device — history is loaded from the cloud
4. To restore history on a new device, go to **Settings** and enter your Device ID

---

## 🛠️ API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/upload` | Upload file and start scrape job |
| `GET` | `/status/<job_id>` | Get job status and progress |
| `GET` | `/partial/<job_id>` | Get partial results so far |
| `POST` | `/control/<job_id>/<action>` | pause / resume / stop |
| `GET` | `/download/<job_id>?fmt=xlsx\|csv` | Download results |
| `GET` | `/history?device_id=...` | List completed jobs |
| `DELETE` | `/history/<job_id>` | Delete a history entry |
| `GET` | `/analytics?device_id=...` | Analytics data |
| `GET` | `/settings` | Get current settings |
| `POST` | `/settings` | Update settings |

---

## 📦 Dependencies

### Python

```
flask>=3.0
pandas>=2.0
openpyxl>=3.1
selenium>=4.18
webdriver-manager>=4.0
xlrd>=2.0
python-dotenv>=1.0
```

### Frontend (loaded from CDN, no install needed)

- [Chart.js 4.4](https://www.chartjs.org/) — analytics charts
- [Supabase JS v2](https://supabase.com/docs/reference/javascript) — cloud history
- [DM Sans + DM Mono + Playfair Display](https://fonts.google.com/) — typography

---

## ⚠️ Important Disclaimer

> Scraping LinkedIn may violate their [Terms of Service](https://www.linkedin.com/legal/user-agreement).
> This project is intended for **personal and research use only**.
> Use responsibly. Do not scrape more than 500 accounts per session from a single LinkedIn account.
> The authors take no responsibility for account bans or other consequences.

---

## 🤝 Contributing

Pull requests are welcome. For major changes, please open an issue first.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Commit your changes (`git commit -m 'Add my feature'`)
4. Push to the branch (`git push origin feature/my-feature`)
5. Open a Pull Request

---

## 🙏 Acknowledgements

- [Selenium](https://www.selenium.dev/) for browser automation
- [Flask](https://flask.palletsprojects.com/) for the lightweight backend
- [Supabase](https://supabase.com/) for free cloud database hosting
- [Chart.js](https://www.chartjs.org/) for beautiful real-time charts
