"""
LinkedScan — Flask Backend with Supabase Sync
================================================
History is stored in BOTH:
  • Local SQLite  (linkedscan.db) — always works
  • Supabase      (cloud)         — if configured in .env

Run:
    pip install -r requirements.txt
    python app.py
"""

import re, time, threading, uuid, io, json, sqlite3, random, os
from datetime import datetime
from dotenv import load_dotenv

import pandas as pd
from flask import Flask, request, jsonify, send_file, render_template

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

load_dotenv()

app = Flask(__name__)

# ─── Supabase (optional) ──────────────────────────────────────────────────────
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

def supabase_insert(table, data):
    """POST a row to Supabase via REST API."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        return
    try:
        import urllib.request, urllib.error
        payload = json.dumps(data).encode()
        req = urllib.request.Request(
            f"{SUPABASE_URL}/rest/v1/{table}",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Prefer": "return=minimal",
            },
            method="POST",
        )
        urllib.request.urlopen(req, timeout=8)
    except Exception as e:
        print(f"[Supabase insert warning] {e}")

def supabase_delete(table, job_id):
    """DELETE a row from Supabase."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        return
    try:
        import urllib.request
        req = urllib.request.Request(
            f"{SUPABASE_URL}/rest/v1/{table}?job_id=eq.{job_id}",
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
            },
            method="DELETE",
        )
        urllib.request.urlopen(req, timeout=8)
    except Exception as e:
        print(f"[Supabase delete warning] {e}")


# ─── SQLite ───────────────────────────────────────────────────────────────────
DB_PATH = "linkedscan.db"

def init_db():
    con = sqlite3.connect(DB_PATH)
    con.execute("""
        CREATE TABLE IF NOT EXISTS job_history (
            id            TEXT PRIMARY KEY,
            job_id        TEXT UNIQUE,
            device_id     TEXT,
            filename      TEXT,
            started_at    TEXT,
            finished_at   TEXT,
            total         INTEGER DEFAULT 0,
            found         INTEGER DEFAULT 0,
            failed        INTEGER DEFAULT 0,
            avg_time_s    REAL    DEFAULT 0,
            success_rate  REAL    DEFAULT 0,
            results_json  TEXT,
            columns_json  TEXT,
            created_at    TEXT    DEFAULT (datetime('now'))
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS app_settings (
            key   TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    defaults = {
        "workers": "2", "min_delay": "1.5", "max_delay": "3.0",
        "retries": "2", "headless": "true", "rotate_ua": "true",
    }
    for k, v in defaults.items():
        con.execute("INSERT OR IGNORE INTO app_settings VALUES (?,?)", (k, v))
    con.commit()
    con.close()

init_db()

def get_setting(key, default=None):
    con = sqlite3.connect(DB_PATH)
    row = con.execute("SELECT value FROM app_settings WHERE key=?", (key,)).fetchone()
    con.close()
    return row[0] if row else default

def set_setting(key, value):
    con = sqlite3.connect(DB_PATH)
    con.execute("INSERT OR REPLACE INTO app_settings VALUES (?,?)", (key, str(value)))
    con.commit()
    con.close()

def save_history(job, device_id="anonymous"):
    results  = job.get("results", [])
    found    = sum(1 for r in results if r.get("associated_members") not in (None,"N/A",""))
    failed   = sum(1 for r in results if r.get("associated_members") == "N/A")
    timings  = [r.get("_time_s", 0) for r in results if r.get("_time_s")]
    avg_t    = round(sum(timings)/len(timings), 2) if timings else 0
    rate     = round(found/len(results)*100, 1) if results else 0
    clean    = [{k: v for k, v in r.items() if not k.startswith("_")} for r in results]
    cols     = job.get("columns", [])
    rec_id   = str(uuid.uuid4())

    # SQLite
    con = sqlite3.connect(DB_PATH)
    con.execute("""
        INSERT OR REPLACE INTO job_history
        (id, job_id, device_id, filename, started_at, finished_at,
         total, found, failed, avg_time_s, success_rate, results_json, columns_json)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        rec_id, job["id"], device_id,
        job.get("filename","unknown"),
        job.get("started_at",""), job.get("finished_at",""),
        len(results), found, failed, avg_t, rate,
        json.dumps(clean), json.dumps(cols),
    ))
    con.commit()
    con.close()

    # Supabase (background thread to not block)
    def push():
        supabase_insert("job_history", {
            "job_id":       job["id"],
            "device_id":    device_id,
            "filename":     job.get("filename","unknown"),
            "started_at":   job.get("started_at"),
            "finished_at":  job.get("finished_at"),
            "total":        len(results),
            "found":        found,
            "failed":       failed,
            "avg_time_s":   avg_t,
            "success_rate": rate,
            "results_json": clean,
            "columns_json": cols,
        })
    threading.Thread(target=push, daemon=True).start()


# ─── User Agents ──────────────────────────────────────────────────────────────
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_2) AppleWebKit/605.1.15 Version/17.2 Safari/605.1.15",
]

def get_driver():
    ua = random.choice(USER_AGENTS) if get_setting("rotate_ua") == "true" else USER_AGENTS[0]
    options = Options()
    if get_setting("headless", "true") == "true":
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1440,900")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument(f"user-agent={ua}")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    service = Service(ChromeDriverManager().install())
    driver  = webdriver.Chrome(service=service, options=options)
    driver.execute_cdp_cmd("Network.setUserAgentOverride", {"userAgent": ua})
    driver.execute_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
    driver.execute_script("Object.defineProperty(navigator,'plugins',{get:()=>[1,2,3,4,5]})")
    driver.execute_script("Object.defineProperty(navigator,'languages',{get:()=>['en-US','en']})")
    return driver


def linkedin_login(driver, email, password):
    driver.get("https://www.linkedin.com/login")
    time.sleep(random.uniform(1.5, 2.5))
    for ch in email:
        driver.find_element(By.ID, "username").send_keys(ch)
        time.sleep(random.uniform(0.03, 0.09))
    time.sleep(random.uniform(0.3, 0.7))
    for ch in password:
        driver.find_element(By.ID, "password").send_keys(ch)
        time.sleep(random.uniform(0.03, 0.09))
    time.sleep(random.uniform(0.5, 1.0))
    driver.find_element(By.XPATH, '//button[@type="submit"]').click()
    time.sleep(random.uniform(4, 6))
    cur = driver.current_url
    if "checkpoint" in cur or "challenge" in cur:
        raise RuntimeError("LinkedIn security check triggered.")
    if "login" in cur:
        raise RuntimeError("LinkedIn login failed — check credentials.")


def normalize_url(raw):
    raw = str(raw).strip().rstrip("/")
    if raw.startswith("http"):
        return raw
    raw = raw.lstrip("/")
    if not raw.startswith("company/"):
        raw = "company/" + raw
    return "https://www.linkedin.com/" + raw


URL_CANDIDATES = ["linkedin_url", "url", "LinkedIn URL", "LinkedIn", "company_url"]

def extract_url(row):
    for key in URL_CANDIDATES:
        if key in row and str(row[key]).strip():
            return str(row[key]).strip()
    return str(list(row.values())[0]).strip()


def fetch_members(driver, company_url, retries=None):
    if retries is None:
        retries = int(get_setting("retries", "2"))
    for attempt in range(retries + 1):
        try:
            driver.get(company_url + "/people/")
            try:
                WebDriverWait(driver, 7).until(
                    EC.presence_of_element_located(
                        (By.XPATH, '//*[contains(text(),"associated members")]')
                    )
                )
            except Exception:
                time.sleep(3)
            body = driver.find_element(By.TAG_NAME, "body").text
            m = re.search(r"([\d,]+)\s+associated members", body, re.IGNORECASE)
            if m:
                return m.group(1).replace(",", "")
            m = re.search(r"([\d,]+)\s*(?:employees on LinkedIn|employees|members)", body, re.IGNORECASE)
            if m:
                return m.group(1).replace(",", "")
            # fallback: about page
            driver.get(company_url + "/about/")
            time.sleep(3)
            body = driver.find_element(By.TAG_NAME, "body").text
            m = re.search(r"([\d,]+)\s*(?:associated members|employees on LinkedIn|employees)", body, re.IGNORECASE)
            if m:
                return m.group(1).replace(",", "")
        except Exception:
            if attempt < retries:
                time.sleep(random.uniform(2, 4))
    return "N/A"


# ─── Job store ────────────────────────────────────────────────────────────────
jobs = {}
jobs_lock = threading.Lock()


def run_job(job_id, rows, columns, email, password, n_workers, device_id):
    job = jobs[job_id]
    job["status"]     = "running"
    job["started_at"] = datetime.utcnow().isoformat()

    min_delay = float(get_setting("min_delay", "1.5"))
    max_delay = float(get_setting("max_delay", "3.0"))
    retries   = int(get_setting("retries", "2"))

    drivers = []
    results = [None] * len(rows)

    try:
        for _ in range(n_workers):
            d = get_driver()
            linkedin_login(d, email, password)
            drivers.append(d)

        idx_lock = threading.Lock()
        current  = [0]

        def worker(driver):
            while True:
                if job["_stop_evt"].is_set():
                    break
                job["_pause_evt"].wait()
                with idx_lock:
                    if current[0] >= len(rows):
                        break
                    i = current[0]
                    current[0] += 1
                url = normalize_url(extract_url(rows[i]))
                t0  = time.time()
                count   = fetch_members(driver, url, retries)
                elapsed = round(time.time() - t0, 2)
                result  = dict(rows[i])
                result["associated_members"] = count
                result["_time_s"]            = elapsed
                results[i] = result
                with jobs_lock:
                    job["timings"].append(elapsed)
                    job["progress"] = sum(1 for r in results if r is not None)
                    job["results"]  = [r for r in results if r is not None]
                time.sleep(random.uniform(min_delay, max_delay))

        threads = [threading.Thread(target=worker, args=(d,), daemon=True) for d in drivers]
        for t in threads: t.start()
        for t in threads: t.join()

        if job["_stop_evt"].is_set():
            job["status"] = "stopped"
        else:
            job["status"]      = "done"
            job["finished_at"] = datetime.utcnow().isoformat()
            job["results"]     = [r for r in results if r is not None]
            save_history(job, device_id)

    except Exception as e:
        job["status"] = "error"
        job["error"]  = str(e)
    finally:
        for d in drivers:
            try: d.quit()
            except: pass


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400
    file      = request.files["file"]
    email     = request.form.get("email", "").strip()
    password  = request.form.get("password", "").strip()
    device_id = request.form.get("device_id", "anonymous")
    if not email or not password:
        return jsonify({"error": "Credentials required"}), 400
    filename  = file.filename.lower()
    try:
        df = pd.read_csv(file) if filename.endswith(".csv") else pd.read_excel(file)
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    if df.empty:
        return jsonify({"error": "File is empty"}), 400

    rows      = df.to_dict(orient="records")
    columns   = list(df.columns)
    job_id    = str(uuid.uuid4())
    n_workers = int(get_setting("workers", "2"))
    pause_evt = threading.Event(); pause_evt.set()
    stop_evt  = threading.Event()

    with jobs_lock:
        jobs[job_id] = {
            "id": job_id, "filename": file.filename,
            "status": "queued", "progress": 0,
            "total": len(rows), "results": [], "error": None,
            "columns": columns, "started_at": "", "finished_at": "",
            "timings": [], "_pause_evt": pause_evt, "_stop_evt": stop_evt,
        }

    threading.Thread(
        target=run_job,
        args=(job_id, rows, columns, email, password, n_workers, device_id),
        daemon=True
    ).start()

    return jsonify({"job_id": job_id, "total": len(rows), "filename": file.filename})


@app.route("/status/<job_id>")
def status(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Not found"}), 404
    timings  = job.get("timings", [])
    avg_t    = round(sum(timings)/len(timings), 2) if timings else 0
    n_workers= int(get_setting("workers", "2"))
    eta_s    = round(avg_t*(job["total"]-job["progress"])/n_workers) if avg_t and job["total"]>job["progress"] else 0
    found    = sum(1 for r in job["results"] if r.get("associated_members") not in (None,"N/A",""))
    failed   = sum(1 for r in job["results"] if r.get("associated_members") == "N/A")
    return jsonify({
        "status": job["status"], "progress": job["progress"],
        "total": job["total"], "error": job.get("error"),
        "found": found, "failed": failed,
        "avg_time": avg_t, "eta_s": eta_s,
        "filename": job.get("filename",""),
        "paused": not job["_pause_evt"].is_set(),
    })


@app.route("/partial/<job_id>")
def partial(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Not found"}), 404
    clean = [{k: v for k, v in r.items() if not k.startswith("_")} for r in job["results"]]
    return jsonify({"results": clean, "columns": job["columns"]})


@app.route("/control/<job_id>/<action>", methods=["POST"])
def control(job_id, action):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Not found"}), 404
    if action == "pause":   job["_pause_evt"].clear(); job["status"] = "paused"
    elif action == "resume": job["_pause_evt"].set();  job["status"] = "running"
    elif action == "stop":   job["_stop_evt"].set();   job["_pause_evt"].set()
    return jsonify({"ok": True})


@app.route("/download/<job_id>")
def download(job_id):
    results = None
    job = jobs.get(job_id)
    if job:
        results = [{k: v for k, v in r.items() if not k.startswith("_")} for r in job["results"]]
    else:
        con = sqlite3.connect(DB_PATH)
        row = con.execute("SELECT results_json FROM job_history WHERE job_id=?", (job_id,)).fetchone()
        con.close()
        if row: results = json.loads(row[0])
    if not results:
        return jsonify({"error": "No results"}), 400

    df  = pd.DataFrame(results)
    out = io.BytesIO()
    fmt = request.args.get("fmt", "xlsx")
    if fmt == "csv":
        df.to_csv(out, index=False); out.seek(0)
        return send_file(out, mimetype="text/csv", as_attachment=True, download_name="linkedscan_results.csv")
    else:
        df.to_excel(out, index=False); out.seek(0)
        return send_file(out,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True, download_name="linkedscan_results.xlsx")


# ─── History (SQLite — device-scoped) ─────────────────────────────────────────
@app.route("/history")
def history_list():
    device_id = request.args.get("device_id", "anonymous")
    con = sqlite3.connect(DB_PATH)
    rows = con.execute("""
        SELECT job_id, filename, started_at, finished_at,
               total, found, failed, avg_time_s, success_rate, columns_json
        FROM job_history
        WHERE device_id = ?
        ORDER BY created_at DESC LIMIT 100
    """, (device_id,)).fetchall()
    con.close()
    keys = ["job_id","filename","started_at","finished_at","total","found","failed","avg_time_s","success_rate","columns_json"]
    return jsonify([dict(zip(keys,r)) for r in rows])


@app.route("/history/<job_id>", methods=["DELETE"])
def history_delete(job_id):
    con = sqlite3.connect(DB_PATH)
    con.execute("DELETE FROM job_history WHERE job_id=?", (job_id,))
    con.commit()
    con.close()
    supabase_delete("job_history", job_id)
    return jsonify({"ok": True})


# ─── Analytics ────────────────────────────────────────────────────────────────
@app.route("/analytics")
def analytics():
    device_id = request.args.get("device_id", "anonymous")
    con = sqlite3.connect(DB_PATH)
    rows = con.execute("""
        SELECT job_id, filename, started_at, total, found, failed,
               avg_time_s, success_rate, results_json
        FROM job_history WHERE device_id=? ORDER BY created_at ASC
    """, (device_id,)).fetchall()
    con.close()
    if not rows:
        return jsonify({"empty": True})
    total_runs    = len(rows)
    total_scraped = sum(r[3] for r in rows)
    total_found   = sum(r[4] for r in rows)
    total_failed  = sum(r[5] for r in rows)
    avg_times     = [r[6] for r in rows if r[6]]
    overall_avg   = round(sum(avg_times)/len(avg_times), 2) if avg_times else 0
    success_rate  = round(total_found/total_scraped*100, 1) if total_scraped else 0
    trend = [{"label":r[1] or r[0][:8], "date":r[2][:10] if r[2] else "",
              "found":r[4], "failed":r[5], "total":r[3], "avg_t":r[6] or 0} for r in rows]
    buckets = {"0-20":0,"21-50":0,"51-100":0,"101-500":0,"501-1K":0,"1K-5K":0,"5K-10K":0,"10K+":0}
    def bucket(c):
        if   c<=20:    return "0-20"
        elif c<=50:    return "21-50"
        elif c<=100:   return "51-100"
        elif c<=500:   return "101-500"
        elif c<=1000:  return "501-1K"
        elif c<=5000:  return "1K-5K"
        elif c<=10000: return "5K-10K"
        else:          return "10K+"
    for r in rows:
        try:
            for item in json.loads(r[8]):
                c = item.get("associated_members")
                if c and c != "N/A":
                    try: buckets[bucket(int(c))] += 1
                    except: pass
        except: pass
    return jsonify({
        "total_runs": total_runs, "total_scraped": total_scraped,
        "total_found": total_found, "total_failed": total_failed,
        "overall_avg_t": overall_avg, "success_rate": success_rate,
        "trend": trend[-20:], "distribution": buckets,
        "time_trend": [{"label":r[1] or r[0][:8], "avg_t":round(r[6],2)} for r in rows if r[6]][-20:],
    })


# ─── Settings ─────────────────────────────────────────────────────────────────
@app.route("/settings", methods=["GET"])
def get_settings():
    con = sqlite3.connect(DB_PATH)
    rows = con.execute("SELECT key, value FROM app_settings").fetchall()
    con.close()
    cfg = {r[0]: r[1] for r in rows}
    cfg["supabase_url"] = SUPABASE_URL
    cfg["supabase_key"] = SUPABASE_KEY[:8]+"..." if SUPABASE_KEY else ""
    return jsonify(cfg)


@app.route("/settings", methods=["POST"])
def update_settings():
    data = request.json or {}
    allowed = {"workers","min_delay","max_delay","retries","headless","rotate_ua"}
    for k, v in data.items():
        if k in allowed:
            set_setting(k, str(v))
    return jsonify({"ok": True})


@app.route("/supabase-status")
def supabase_status():
    return jsonify({
        "configured": bool(SUPABASE_URL and SUPABASE_KEY),
        "url": SUPABASE_URL,
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"\n  LinkedScan v4 — running on port {port}\n")
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
