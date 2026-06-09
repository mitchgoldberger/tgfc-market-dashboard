"""
Fetches USDA AMS / NASS / FAS market reports and updates the dashboard DATA dict.
Every parser is wrapped so that, if a report is unreachable or its layout changes,
the corresponding numbers simply fall back to the baseline snapshot — the page
never breaks. Parse functions take already-extracted text so they can be unit-tested.
"""
import re, io, copy, datetime

HEADERS = {"User-Agent": "Mozilla/5.0 (TGFC market dashboard; contact taylor@thetgfc.com)"}

# ---------------- fetching ----------------
def _get(url, timeout=25):
    import requests
    r = requests.get(url, headers=HEADERS, timeout=timeout)
    r.raise_for_status()
    return r

def fetch_pdf_text(url):
    import pdfplumber
    content = _get(url).content
    out = []
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page in pdf.pages:
            out.append(page.extract_text() or "")
    return "\n".join(out)

def fetch_html_text(url):
    return _get(url).text

# ---------------- helpers ----------------
def _n(s):
    return float(str(s).replace(",", "").strip())

def _money_paren(x):
    x = x.strip()
    neg = x.startswith("(")
    x = x.strip("()")
    v = float(x)
    return -v if neg else v

MONTHS = {m: i for i, m in enumerate(
    ["January","February","March","April","May","June","July","August",
     "September","October","November","December"], 1)}

def _iso(datestr):
    # "June 03, 2026" or "Fri May 29, 2026" -> 2026-06-03
    m = re.search(r"([A-Z][a-z]+)\s+(\d{1,2}),?\s+(\d{4})", datestr)
    if not m: return None
    mon = MONTHS.get(m.group(1))
    if not mon: return None
    return "%s-%02d-%02d" % (m.group(3), mon, int(m.group(2)))

# ---------------- parsers ----------------
def parse_beef(t, b):
    m = re.search(r"Current Cutout Values:\s*([\d.]+)\s+([\d.]+)", t)
    if m: b["choice"], b["select"] = _n(m.group(1)), _n(m.group(2))
    m = re.search(r"Change from prior day:\s*(\(?-?[\d.]+\)?)\s+(\(?-?[\d.]+\)?)", t)
    if m: b["choiceChg"], b["selectChg"] = _money_paren(m.group(1)), _money_paren(m.group(2))
    m = re.search(r"Choice/Select spread:\s*([\d.]+)", t)
    if m: b["spread"] = _n(m.group(1))
    m = re.search(r"Total Load Count[^:]*:\s*([\d,]+)", t)
    if m: b["loads"] = int(_n(m.group(1)))
    m = re.search(r"Fresh 50% lean trimmings\s+\d+\s+[\d,]+\s+[\d.]+\s*-\s*[\d.]+\s+([\d.]+)", t)
    if m: b["trim50"] = _n(m.group(1))
    m = re.search(r"Current 5 Day Simple Average:\s*([\d.]+)\s+([\d.]+)", t)
    if m: b["avg5Choice"], b["avg5Select"] = _n(m.group(1)), _n(m.group(2))
    # composite primals: keep weekly-choice (4th elem) from baseline
    for row in b["primals"]:
        mm = re.search(r"Primal %s\s+([\d.]+)\s+([\d.]+)" % re.escape(row[0]), t)
        if mm:
            row[1], row[2] = _n(mm.group(1)), _n(mm.group(2))
    # ground beef daily (col 2 of [name, daily, weekly])
    for row in b["grinds"]:
        mm = re.search(re.escape(row[0]) + r"\s+\d+\s+[\d,]+\s+[\d.]+\s*-\s*[\d.]+\s+([\d.]+)", t)
        if mm: row[1] = _n(mm.group(1))
    md = re.search(r"Agricultural Marketing Service\s+([A-Z][a-z]+ \d{1,2}, \d{4})", t)
    if md and _iso(md.group(1)): b["asof"] = _iso(md.group(1))
    return b

def parse_pork(t, p):
    # today's row: date loads carcass loin butt picnic rib ham belly
    m = re.search(r"\d{2}/\d{2}/\d{4}\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)", t)
    if m:
        vals = [ _n(x) for x in m.groups() ]
        # vals = loads, carcass, loin, butt, picnic, rib, ham, belly
        p["carcass"] = vals[1]; p["belly"] = vals[7]
        order = [("Loin",2),("Butt",3),("Picnic",4),("Rib",5),("Ham",6),("Belly",7)]
        cur = {nm: vals[i] for nm, i in order}
        for row in p["primals"]:
            if row[0] in cur: row[1] = cur[row[0]]
    m = re.search(r"Change:\s*(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)", t)
    if m:
        ch = [ float(x) for x in m.groups() ]  # carcass, loin, butt, picnic, rib, ham, belly
        p["carcassChg"] = ch[0]
        cmap = dict(zip(["Loin","Butt","Picnic","Rib","Ham","Belly"], ch[1:]))
        for row in p["primals"]:
            if row[0] in cmap: row[2] = cmap[row[0]]
    m = re.search(r"Five Day Average\s*--\s*([\d.]+)", t)
    if m: p["avg5"] = _n(m.group(1))
    m = re.search(r"Loads PORK CUTS\s*:\s*([\d.]+)", t)
    if m: p["loadsCuts"] = _n(m.group(1))
    m = re.search(r"Loads TRIM/PROCESS PORK\s*:\s*([\d.]+)", t)
    if m: p["loadsTrim"] = _n(m.group(1))
    for row in p["trim"]:
        mm = re.search(re.escape(row[0]) + r"\s+[\d,]+\s+[\d.]+\s*-\s*[\d.]+\s+([\d.]+)", t)
        if mm: row[1] = _n(mm.group(1))
    md = re.search(r"(May|June|April|January|February|March|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}", t)
    if md and _iso(md.group(0)): p["asof"] = _iso(md.group(0))
    return p

def parse_slaughter(t, s):
    # first occurrence of each species line: name current weekAgo yearAgo WTD prevWTD lyWTD YTD ly_YTD pct%
    for row in s["rows"]:
        nm = row[0].split(" (")[0]  # "Chicken (young)" -> "Chicken"
        mm = re.search(re.escape(nm) + r"(?:\s*\([A-Za-z]+\))?\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+[\d,]+\s+[\d,]+\s+([\d,]+)\s+[\d,]+\s+(-?[\d.]+)%", t)
        if mm:
            row[1] = int(_n(mm.group(1)))   # current day
            row[2] = int(_n(mm.group(2)))   # week ago day
            row[3] = int(_n(mm.group(3)))   # year ago day
            row[4] = int(_n(mm.group(5)))   # YTD
            row[5] = float(mm.group(6))     # YTD %
    md = re.search(r"Report for ([A-Z][a-z]+ \d{1,2}, \d{4})", t)
    if md and _iso(md.group(1)): s["asof"] = _iso(md.group(1))
    return s

def parse_hogs(t, cash):
    # Negotiated totals carcass base + net are the last numbers on those rows (after a possible '*')
    m = re.search(r"Carcass Base Price\s+[\d.\s*]+?([\d.]+)\s*\n", t)
    base = None
    m = re.search(r"Carcass Base Price\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+\*?\s*([\d.]+)", t)
    if m: base = _n(m.group(5))
    netm = re.search(r"Average Net Price\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+\*?\s*([\d.]+)", t)
    net = _n(netm.group(5)) if netm else None
    bg = re.search(r"Barrows and Gilts.*?:\s*([\d,]+)", t)
    cw = re.search(r"Average Carcass Wt\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+\*?\s*([\d.]+)", t)
    for row in cash["rows"]:
        if row[0].startswith("Hogs — Negotiated"):
            if bg: row[1] = int(_n(bg.group(1)))
            if cw: row[2] = _n(cw.group(5))
            if base is not None: row[3] = base
        if row[0].startswith("Hogs — Avg net"):
            if net is not None: row[3] = net
    md = re.search(r"(May|June|April|January|February|March|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}", t)
    if md and _iso(md.group(0)): cash["hogAsof"] = _iso(md.group(0))
    return cash

def parse_poultry(t, q):
    m = re.search(r"National Composite Whole\s+Bird:\s*[\d.]+\s*-\s*[\d.]+\s+([\d.]+)\s+(-?[\d.]+)", t)
    if m: q["wholeComposite"], q["wholeChg"] = _n(m.group(1)), float(m.group(2))
    mb = re.search(r"Breast - B/S:\s*[\d.]+\s*-\s*[\d.]+\s+([\d.]+)\s+(-?[\d.]+)", t)
    if mb: q["breast"], q["breastChg"] = _n(mb.group(1)), float(mb.group(2))
    # parts table: "<label>: lo - hi  wtd  chg ..."
    label_map = {"Breast — B/S":"Breast - B/S","Tenderloins":"Tenderloins","Thighs — B/S":"Thighs - B/S",
                 "Wings — Whole":"Wings - Whole","Drumsticks":"Drumsticks","Leg Quarters — Bulk":"Leg quarters - Bulk",
                 "Legs — Bone-in":"Legs - Bone-in"}
    for row in q["parts"]:
        lab = label_map.get(row[0], row[0])
        mm = re.search(re.escape(lab) + r":\s*[\d.]+\s*-\s*[\d.]+\s+([\d.]+)\s+(-?[\d.]+)", t)
        if mm: row[1], row[2] = _n(mm.group(1)), float(mm.group(2))
    for row in q["whole"]:
        lab = row[0].replace("WOGs Composite","National Composite WOGS").replace("National Composite Whole Bird","National Composite Whole\n?\\s*Bird")
        mm = re.search(re.escape(row[0].replace("—","-")) + r":\s*[\d.]+\s*-\s*[\d.]+\s+([\d.]+)\s+(-?[\d.]+)", t)
        if mm: row[1], row[2] = _n(mm.group(1)), float(mm.group(2))
    return q

def parse_trade(t, trade):
    t = re.sub(r"<[^>]+>", " ", t)          # strip HTML tags
    t = re.sub(r"\*+", "", t)               # strip markdown bold if present
    t = re.sub(r"\s+", " ", t)
    def grab(species):
        i = t.find(species + ":")
        block = t[i:i+600] if i >= 0 else ""
        ns = re.search(r"Net sales of ([\d,]+)\s*(?:MT|metric tons)", block)
        ex = re.search(r"Exports of ([\d,]+)\s*MT", block)
        return (ns.group(1) if ns else None, ex.group(1) if ex else None)
    bns, bex = grab("Beef")
    pns, pex = grab("Pork")
    for row in trade["rows"]:
        if row[0] == "Beef" and "Net" in row[1] and bns: row[2] = bns + " MT"
        if row[0] == "Beef" and "Export" in row[1] and bex: row[2] = bex + " MT"
        if row[0] == "Pork" and "Net" in row[1] and pns: row[2] = pns + " MT"
        if row[0] == "Pork" and "Export" in row[1] and pex: row[2] = pex + " MT"
    return trade

# ---------------- WoW summary recompute ----------------
def recompute_wow(D):
    try:
        rows = D["wow"]["rows"]
        bymap = {r[0]: r for r in rows}
        # pork carcass vs ~1wk earlier (first vs last of series)
        ser = D["pork"]["series"]["carcass"]
        if "Pork — Carcass cutout" in bymap and len(ser) >= 2:
            r = bymap["Pork — Carcass cutout"]; r[1] = "$%.2f/cwt" % D["pork"]["carcass"]; r[2] = round(ser[-1]-ser[0],2)
        # poultry from chicken report change
        if "Poultry — Whole bird" in bymap:
            r = bymap["Poultry — Whole bird"]; r[1] = "%.2f¢/lb" % D["poultry"]["wholeComposite"]; r[2] = D["poultry"]["wholeChg"]
        if "Poultry — B/S breast" in bymap:
            r = bymap["Poultry — B/S breast"]; r[1] = "%.2f¢/lb" % D["poultry"]["breast"]; r[2] = D["poultry"]["breastChg"]
        # slaughter WTD vs prior week not available post-parse; leave baseline
    except Exception:
        pass
    return D

# ---------------- orchestrator ----------------
REPORTS = {
    "beef":   "https://www.ams.usda.gov/mnreports/ams_2453.pdf",
    "pork":   "https://www.ams.usda.gov/mnreports/ams_2498.pdf",
    "slaughter":"https://www.ams.usda.gov/mnreports/ams_3208.pdf",
    "hogs":   "https://www.ams.usda.gov/mnreports/ams_2511.pdf",
    "poultry":"https://www.ams.usda.gov/mnreports/ams_3646.pdf",
    "trade":  "https://apps.fas.usda.gov/export-sales/highlite.htm",
}

def build_data(baseline):
    D = copy.deepcopy(baseline)
    status = {}
    def run(key, fetch, parse):
        try:
            txt = fetch(REPORTS[key]); parse(txt); status[key] = "ok"
        except Exception as e:
            status[key] = "fallback (%s)" % (str(e)[:50])
    run("beef", fetch_pdf_text, lambda t: parse_beef(t, D["beef"]))
    run("pork", fetch_pdf_text, lambda t: parse_pork(t, D["pork"]))
    run("slaughter", fetch_pdf_text, lambda t: parse_slaughter(t, D["slaughter"]))
    run("hogs", fetch_pdf_text, lambda t: parse_hogs(t, D["cash"]))
    run("poultry", fetch_pdf_text, lambda t: parse_poultry(t, D["poultry"]))
    run("trade", fetch_html_text, lambda t: parse_trade(t, D["trade"]))
    recompute_wow(D)
    D["refreshed"] = datetime.date.today().isoformat()
    D["_status"] = status
    return D
