import os
import json
import re
import time
import math
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timezone

# ==========================================
# ENVIRONMENT CONFIGURATION
# ==========================================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
SITE_BASE_URL = os.environ.get("SITE_BASE_URL", "https://hanifsalman11.github.io/range-hood-index").rstrip("/")
INDEXNOW_KEY = os.environ.get("INDEXNOW_KEY", "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6").strip()
CUSTOM_HOOD = os.environ.get("CUSTOM_HOOD", "").strip()
PAGES_PER_RUN = int(os.environ.get("PAGES_PER_RUN", "3"))

DOCS_DIR = "docs"
DATA_DIR = "data"
PUBLISHED_FILE = os.path.join(DATA_DIR, "published_hoods.json")
MONETIZATION_FILE = os.path.join(DATA_DIR, "monetization.json")

_CACHED_MODELS = None

# Format: (Model / Stove Scenario, Stove Width In, Total Gas BTU, Hood Width In, Rec Blower CFM, Duct Dia In, Mount Type)
SEED_HOODS = [
    ("ZLINE KB-36 (36-Inch 700 CFM) Wall-Mount Range Hood", 36, 60000, 36, 700, 8, "Wall-Mount Chimney"),
    ("ZLINE KL3-48 (48-Inch 1,200 CFM) Dual-Motor Pro Hood", 48, 102000, 48, 1200, 10, "Wall-Mount Pro"),
    ("ZLINE 698-36 (36-Inch 700 CFM) Custom Wood Hood Insert", 36, 62000, 36, 700, 8, "Liner Insert"),
    ("Hauslane Chef Series PS18 (30-Inch 860 CFM) Under-Cabinet", 30, 52000, 30, 860, 6, "Under-Cabinet Pro"),
    ("Hauslane Chef Series PS38 (36-Inch 900 CFM) Range Hood", 36, 65000, 36, 900, 8, "Under-Cabinet / Wall"),
    ("Vent-A-Hood PRH9-236 (36-Inch 600 CFM) Magic Lung Blower", 36, 58000, 36, 600, 8, "Under-Cabinet / Wall"),
    ("Vent-A-Hood PRH18-348 (48-Inch 900 CFM) Triple Blower", 48, 90000, 48, 900, 10, "Pro Wall-Mount"),
    ("Broan-NuTone E60E36SS Elite (36-Inch 650 CFM) Pro Hood", 36, 55000, 36, 650, 8, "Under-Cabinet / Wall"),
    ("Broan-NuTone MD8TU & MD6TU Universal Make-Up Air Damper", 36, 65000, 36, 750, 8, "IRC M1503.4 MUA Kit"),
    ("Zephyr Tempest II ZPT-E36BS (36-Inch 650 / 1,200 CFM)", 36, 65000, 36, 650, 8, "Under-Cabinet Pro"),
    ("Zephyr Monsoon II (36-Inch & 48-Inch) Custom Liner Insert", 48, 92000, 48, 1100, 10, "Custom Hood Insert"),
    ("XtremeAirPX06-U36 (36-Inch 900 CFM) 1.0mm Stainless", 36, 68000, 36, 900, 8, "Under-Cabinet Pro"),
    ("Cosmo QS75 & 668ICS750 (30-Inch 500 CFM) Range Hood", 30, 44000, 30, 500, 6, "Under-Cabinet / Island"),
    ("Fotile JQG7501 & Pixie Air (30-Inch 850 CFM) Side-Draft", 30, 56000, 30, 850, 6, "Slanted Wing Capture"),
    ("Faber Inca Pro Plus (30-Inch & 36-Inch 600 CFM) Insert", 36, 54000, 36, 600, 8, "Custom Cabinet Insert"),
    ("Fantech FKD8XL &HL10 Inline Remote Attic Range Blower", 48, 95000, 48, 1000, 10, "Remote Inline Blower"),
    ("30-Inch 4-Burner Gas Range (45,000 BTU) Hood CFM Sizing", 30, 45000, 30, 550, 6, "Wall / Under-Cabinet"),
    ("30-Inch 5-Burner Pro Gas Range (58,000 BTU) Hood Sizing", 30, 58000, 36, 700, 8, "Wall / Under-Cabinet"),
    ("36-Inch 6-Burner Pro Gas Range (72,000 BTU) Hood Sizing", 36, 72000, 36, 850, 8, "Wall-Mount Pro"),
    ("36-Inch Kitchen Island Gas Cooktop (60,000 BTU) Hood Sizing", 36, 60000, 42, 900, 8, "Ceiling Island Mount"),
    ("48-Inch 8-Burner / Griddle Pro Range (105,000 BTU) Sizing", 48, 105000, 48, 1200, 10, "Wall-Mount Pro"),
    ("60-Inch Commercial-Style Residential Range (140,000 BTU)", 60, 140000, 60, 1500, 12, "Dual-Blower Pro"),
    ("Wolf 36-Inch Dual-Fuel / Gas Range (65,000 BTU) Hood Sizing", 36, 65000, 36, 800, 8, "Pro Wall / Insert"),
    ("Wolf 48-Inch Gas Range w/ Infrared Griddle (92,000 BTU)", 48, 92000, 48, 1100, 10, "Pro Wall / Insert"),
    ("Thor Kitchen 36-Inch LRG3601U (68,000 BTU) Range Hood", 36, 68000, 36, 800, 8, "Wall-Mount Pro"),
    ("Thor Kitchen 48-Inch Gas Range (102,000 BTU) Hood Sizing", 48, 102000, 48, 1200, 10, "Wall-Mount Pro"),
    ("30-Inch & 36-Inch Induction Cooktop Condensate CFM Sizing", 36, 36000, 36, 400, 6, "Code-Exempt ≤400 CFM"),
    ("Indoor Wok Burner & High-Heat Searing (900+ CFM) Hood", 36, 75000, 42, 950, 8, "Deep 24\" Capture Basin"),
    ("IRC M1503.4 400-CFM Make-Up Air Threshold & Damper Sizing", 36, 60000, 36, 700, 8, "8\" Motorized MUA Damper"),
    ("6-Inch vs 8-Inch vs 10-Inch Range Hood Duct CFM & Sone Loss", 36, 65000, 36, 750, 8, "Rigid Smooth-Walled Duct")
]


def load_json(filepath, default):
    """Self-healing JSON loader: otomatis pulih jika file korup atau kosong."""
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, type(default)) else default
        except Exception as e:
            print(f"[SELF-HEAL] Recovering {filepath} due to read notice: {e}")
    return default


def save_json(filepath, data):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def slugify(text):
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    return re.sub(r"[\s-]+", "-", text).strip("-")


def safe_float(val, default=650.0):
    try:
        cleaned = re.sub(r"[^0-9.]", "", str(val))
        return float(cleaned) if cleaned else float(default)
    except Exception:
        return float(default)


def build_amazon_url(search_keywords, mon_cfg):
    domain = mon_cfg.get("marketplace_domain", "www.amazon.com")
    tag = mon_cfg.get("amazon_associate_tag", "YOUR_AMAZON_TAG-20")
    encoded_q = urllib.parse.quote_plus(search_keywords)
    return f"https://{domain}/s?k={encoded_q}&tag={tag}"


def get_active_gemini_model(api_key):
    """
    LAPIS 1: Mesin Pemindai Versi Otomatis berbasis Regex tanpa angka versi manual.
    Otomatis mendeteksi model Gemini Flash STABIL generasi tertinggi lintas tahun.
    """
    global _CACHED_MODELS
    if _CACHED_MODELS is not None:
        return _CACHED_MODELS

    list_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    try:
        req = urllib.request.Request(list_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            scored_models = []

            for m in data.get("models", []):
                name = m.get("name", "").replace("models/", "")
                methods = m.get("supportedGenerationMethods", [])

                if "generateContent" not in methods or "flash" not in name.lower():
                    continue

                if any(bad in name.lower() for bad in [
                    "preview", "exp", "thinking", "image", "tts", "audio", "vision", "8b"
                ]):
                    continue

                ver_match = re.search(r"gemini-(\d+(?:\.\d+)?)-flash", name.lower())
                if ver_match:
                    ver_num = float(ver_match.group(1))
                    if name.lower() == f"gemini-{ver_match.group(1)}-flash":
                        tier_score = 2
                    elif name.lower() == f"gemini-{ver_match.group(1)}-flash-lite":
                        tier_score = 1
                    else:
                        tier_score = 0
                    scored_models.append((ver_num, tier_score, name))
                elif name.lower() == "gemini-flash-latest":
                    scored_models.append((0.1, 0, name))

            if scored_models:
                scored_models.sort(key=lambda x: (x[0], x[1]), reverse=True)
                _CACHED_MODELS = [item[2] for item in scored_models[:2]]
                print(f"[GEMINI] Future-proof active models locked: {_CACHED_MODELS}")
                return _CACHED_MODELS
    except Exception as e:
        print(f"[WARN] Dynamic model discovery notice: {e}")

    _CACHED_MODELS = ["gemini-flash-latest"]
    return _CACHED_MODELS


def discover_google_hood_queries(published_slugs):
    """
    LAPIS 4: 3-Tier Infinite Keyword Supply:
    Tier A: Seed List -> Tier B: Google Suggest US -> Tier C: Combinatorial Stove Width × BTU Permutator.
    """
    discovered = []
    seeds = [
        "what size range hood cfm for ",
        "zline range hood ",
        "hauslane range hood ",
        "make up air damper for "
    ]
    for seed in seeds:
        try:
            url = f"http://suggestqueries.google.com/complete/search?client=firefox&hl=en&gl=us&q={urllib.parse.quote(seed)}"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                for suggestion in data[1]:
                    cleaned = suggestion.lower()
                    for pref in seeds:
                        if "what size" in pref or "for " in pref:
                            cleaned = cleaned.replace(pref, "")
                    cleaned = re.sub(
                        r"\b(calculator|size|sizing|cfm|chart|manual|review|reddit|for)\b",
                        "",
                        cleaned
                    ).strip()
                    if 5 <= len(cleaned) <= 42:
                        w_m = re.search(r"\b(30|36|42|48|60)\b", cleaned)
                        w_in = int(w_m.group(1)) if w_m else 36
                        btu_v = 48000 if w_in == 30 else (65000 if w_in == 36 else 95000)
                        cfm_v = int(round((btu_v / 100.0) * 1.15, -1))
                        d_in = 6 if cfm_v <= 450 else (8 if cfm_v <= 900 else 10)
                        discovered.append((cleaned.title(), w_in, btu_v, w_in, cfm_v, d_in, "Wall-Mount Pro"))
        except Exception as e:
            print(f"[WARN] Google Suggest notice: {e}")

    # Tier C Fallback: Combinatorial Permutator (Anti-Habis Lintas Tahun)
    widths = [30, 36, 42, 48]
    btu_tiers = [45000, 55000, 65000, 78000, 92000, 110000]
    mount_styles = ["Wall-Mount Chimney", "Under-Cabinet Pro", "Kitchen Island Mount", "Custom Wood Hood Insert"]
    for w_in in widths:
        for btu_v in btu_tiers:
            if w_in == 30 and btu_v > 65000:
                continue
            if w_in == 48 and btu_v < 70000:
                continue
            for m_style in mount_styles:
                combo_title = f"{w_in}-Inch {btu_v:,} BTU Gas Range ({m_style})"
                test_slug = slugify(f"{combo_title}-cfm-duct-calculator")
                if test_slug not in published_slugs:
                    isl_mult = 1.35 if "Island" in m_style else 1.15
                    rec_c = int(round((btu_v / 100.0) * isl_mult, -1))
                    d_dia = 6 if rec_c <= 450 else (8 if rec_c <= 900 else 10)
                    h_wid = w_in + 6 if "Island" in m_style else w_in
                    discovered.append((combo_title, w_in, btu_v, h_wid, rec_c, d_dia, m_style))
                    if len(discovered) >= 25:
                        return discovered
    return discovered


def build_deterministic_hood_data(hood_tuple):
    """
    LAPIS 3: Mesin Fisika HVI / NKBA Thermal Plume, Equivalent Duct Length & IRC M1503.4 (100% Bebas Gagal).
    """
    model_name, stove_in, gas_btu, hood_in, rec_cfm, duct_in, mount_type = hood_tuple

    is_island = "island" in mount_type.lower() or "island" in model_name.lower()
    # Standar HVI / NKBA:
    # 1. Berdasarkan BTU Gas: 100 CFM per 10,000 BTU (Gas_BTU / 100)
    # 2. Berdasarkan Lebar Kompor: 100 CFM per linear foot wall-mount, 150 CFM per linear foot untuk Island
    btu_based_cfm = int(round(gas_btu / 100.0))
    width_based_cfm = int(round((stove_in / 12.0) * (150.0 if is_island else 100.0)))
    base_capture_cfm = max(btu_based_cfm, width_based_cfm)

    # Tambahkan kompensasi Equivalent Duct Length (EL):
    # Rata-rata 15 ft pipa lurus + (2x siku 90° = 50 ft EL) + Roof/Wall Cap (30 ft EL) = 95 ft Equivalent Length (~18% static pressure loss)
    equiv_duct_ft = 95
    recommended_blower_cfm = max(rec_cfm, int(round(base_capture_cfm * 1.20, -1)))

    # Diameter Pipa Ducting agar Kecepatan Udara (FPM) berada di zona tenang 1,200 - 1,800 FPM
    if recommended_blower_cfm <= 420:
        opt_duct_in = 6
    elif recommended_blower_cfm <= 900:
        opt_duct_in = 8
    else:
        opt_duct_in = 10

    duct_area_sqft = round(math.pi * (((opt_duct_in / 2.0) / 12.0) ** 2), 3)
    duct_velocity_fpm = int(round(recommended_blower_cfm / duct_area_sqft))

    # Aturan Kode Bangunan IRC Section M1503.4 (Make-Up Air wajib jika > 400 CFM):
    needs_mua = recommended_blower_cfm > 400
    mua_damper_in = opt_duct_in
    mua_verdict = (
        f"MANDATORY (Exceeds 400 CFM IRC M1503.4 limit — install an {mua_damper_in}-inch motorized Make-Up Air damper)"
        if needs_mua else "Exempt (400 CFM or below)"
    )

    return {
        "hood_name": model_name,
        "mount_type": mount_type,
        "seo_title": f"{model_name} CFM, Duct Size & Make-Up Air Calculator (2026)",
        "meta_description": f"Calculate exact range hood exhaust flow ({recommended_blower_cfm:,} CFM for {gas_btu:,} BTU), {opt_duct_in}-inch rigid duct velocity ({duct_velocity_fpm:,} FPM), and IRC M1503.4 Make-Up Air damper sizing for {model_name}.",
        "specs": {
            "stove_width_inches": stove_in,
            "recommended_hood_width_in": hood_in,
            "total_gas_btu": gas_btu,
            "base_capture_cfm": base_capture_cfm,
            "recommended_blower_cfm": recommended_blower_cfm,
            "equivalent_duct_length_ft": equiv_duct_ft,
            "recommended_duct_inches": opt_duct_in,
            "duct_velocity_fpm": duct_velocity_fpm,
            "irc_makeup_air_status": mua_verdict,
            "mount_type": mount_type
        },
        "hvi_verdict": f"For {model_name} ({stove_in}\" range rated at {gas_btu:,} BTU/hr), the HVI/NKBA thermal plume formula ($\\text{{BTU}} \\div 100$) requires {base_capture_cfm:,} net capture CFM. Accounting for {equiv_duct_ft} Equivalent Feet of duct static pressure (two 90° elbows + exterior backdraft roof/wall cap), select a {hood_in}-inch {mount_type} range hood rated at {recommended_blower_cfm:,} CFM vented through {opt_duct_in}-inch rigid smooth-walled metal ducting ({duct_velocity_fpm:,} FPM air velocity). Under International Residential Code (IRC) Section M1503.4, Make-Up Air is: {mua_verdict}.",
        "hardware_bundle": [
            {
                "badge": f"{ hood_in }\" / {recommended_blower_cfm} CFM Hood",
                "title": f"{hood_in}-Inch {recommended_blower_cfm} CFM Pro Stainless Steel Range Hood w/ Dishwasher-Safe Baffle Filters",
                "price_range": "$329 - $1,499",
                "amazon_query": f"{hood_in} Inch {recommended_blower_cfm} CFM Stainless Steel Range Hood Baffle Filter",
                "hood_note": f"Deep capture canopy and commercial stainless steel baffle filters trap grease plumes from {gas_btu:,} BTU burners."
            },
            {
                "badge": f"{mua_damper_in}\" IRC Make-Up Air Kit",
                "title": f"{mua_damper_in}-Inch Universal Motorized Make-Up Air (MUA) Damper Kit with Automatic Current/Pressure Sensor",
                "price_range": "$149 - $349",
                "amazon_query": f"Broan {mua_damper_in} Inch Universal Make Up Air Damper Range Hood",
                "hood_note": "Automatically opens fresh replacement air intake whenever the range hood turns on above 400 CFM—preventing carbon monoxide backdrafting."
            },
            {
                "badge": f"{opt_duct_in}\" Roof/Wall Hood Cap",
                "title": f"{opt_duct_in}-Inch Heavy-Duty Galvanized Steel Roof/Wall Exhaust Vent Cap with Spring Backdraft Damper",
                "price_range": "$59 - $149",
                "amazon_query": f"{opt_duct_in} Inch Range Hood Roof Wall Exhaust Vent Cap Backdraft Damper",
                "hood_note": f"Full-bore {opt_duct_in}\" throat keeps air velocity near {duct_velocity_fpm:,} FPM to eliminate high-pitched duct roar."
            },
            {
                "badge": "Inline Blower & Foil Tape",
                "title": f"{opt_duct_in}-Inch High-Static Inline Duct Blower / Silencer + UL-181B-FX Aluminum Foil Mastic Tape",
                "price_range": "$69 - $279",
                "amazon_query": f"{opt_duct_in} Inch Inline Duct Blower Fan Range Hood UL181 Foil Tape",
                "hood_note": "Seals all rigid metal duct seams air-tight (never use cloth duct tape on grease exhaust!) and cuts kitchen sone noise by 50%."
            }
        ],
        "code_checklist": [
            f"Size your Range Hood Canopy Width at least equal to your stove ({stove_in}\"), or 6 inches wider ({stove_in + 6}\") if mounted over an open kitchen island where cross-drafts disperse smoke.",
            f"Comply with IRC Section M1503.4: any residential range hood capable of exhausting more than 400 CFM MUST be paired with a mechanical or interlocked motorized Make-Up Air (MUA) damper ({mua_damper_in}\" duct) so negative house pressure never backdrafts gas water heaters, furnaces, or wood fireplaces.",
            f"Use only smooth-walled 26-to-28 gauge Rigid Galvanized Steel or Aluminum Round Duct ({opt_duct_in}\" diameter); never use flexible ribbed dryer transition hose, which traps flammable cooking grease and cuts CFM by 35%.",
            "Mount the bottom of the range hood canopy 28 to 34 inches above the gas cooking grates; mounting higher than 36 inches allows the rising thermal plume to expand wider than the hood intake."
        ],
        "faqs": [
            {
                "q": f"How many CFM do I need for {model_name} ({gas_btu:,} BTU)?",
                "a": f"Using the HVI/NKBA professional gas formula, divide your total burner output ({gas_btu:,} BTU) by 100 to get {btu_based_cfm:,} base CFM. Adding a 20% static pressure buffer for elbows and the exterior roof/wall cap gives {recommended_blower_cfm:,} recommended blower CFM."
            },
            {
                "q": f"Why does a {recommended_blower_cfm:,} CFM range hood require an {opt_duct_in}-inch duct and Make-Up Air?",
                "a": f"Pushing {recommended_blower_cfm:,} CFM through an undersized 6-inch pipe forces air velocity above 2,800 FPM—creating deafening turbulence and choking blower output. An {opt_duct_in}-inch rigid duct keeps velocity at {duct_velocity_fpm:,} FPM. Furthermore, IRC code M1503.4 mandates a Make-Up Air damper for any hood exceeding 400 CFM."
            },
            {
                "q": f"How much CFM do 90-degree elbows subtract from my range hood?",
                "a": f"Every sharp 90-degree elbow adds 25 Equivalent Feet of resistance (two 45-degree elbows add only 15 Equivalent Feet), and an exterior roof/wall cap adds 30 Equivalent Feet. Keep total Equivalent Duct Length under 100 feet."
            }
        ]
    }


def generate_hood_data(hood_tuple):
    """
    LAPIS 2: Memanggil model Gemini stabil dengan proteksi Cooldown HTTP 429 & Fallback Otomatis.
    """
    if not GEMINI_API_KEY:
        return build_deterministic_hood_data(hood_tuple)

    model_name, stove_in, gas_btu, hood_in, rec_cfm, duct_in, mount_type = hood_tuple
    det_fallback = build_deterministic_hood_data(hood_tuple)
    sp = det_fallback["specs"]

    prompt = f"""
You are a Certified NKBA Kitchen Ventilation Engineer & IRC Mechanical Code Inspector (Section M1503.4 Specialist). Create an accurate 2026 kitchen range hood CFM, gas stove BTU thermal plume, rigid duct diameter, and Make-Up Air (MUA) damper sizing guide for: "{model_name}".
Baseline specs: Stove Width={stove_in} Inches ({gas_btu} BTU), Recommended Hood={hood_in} Inches ({mount_type}), Base Capture={sp['base_capture_cfm']} CFM, Recommended Blower={sp['recommended_blower_cfm']} CFM (with {sp['equivalent_duct_length_ft']} ft Equivalent Duct Length), Rigid Duct={sp['recommended_duct_inches']} Inches ({sp['duct_velocity_fpm']} FPM), IRC M1503.4 Make-Up Air={sp['irc_makeup_air_status']}.
Return ONLY a valid JSON object matching this exact schema:
{{
  "hood_name": "{model_name}",
  "mount_type": "{mount_type}",
  "seo_title": "{model_name} CFM, Duct Size & Make-Up Air Calculator (2026)",
  "meta_description": "Calculate exact range hood CFM for gas BTU output, rigid duct diameter, Equivalent Duct Length loss, and IRC M1503.4 Make-Up Air damper requirements for {model_name}.",
  "specs": {{
    "stove_width_inches": {stove_in},
    "recommended_hood_width_in": {hood_in},
    "total_gas_btu": {gas_btu},
    "base_capture_cfm": {sp['base_capture_cfm']},
    "recommended_blower_cfm": {sp['recommended_blower_cfm']},
    "equivalent_duct_length_ft": {sp['equivalent_duct_length_ft']},
    "recommended_duct_inches": {sp['recommended_duct_inches']},
    "duct_velocity_fpm": {sp['duct_velocity_fpm']},
    "irc_makeup_air_status": "{sp['irc_makeup_air_status']}",
    "mount_type": "{mount_type}"
  }},
  "hvi_verdict": "3-sentence technical summary stating gas BTU divide-by-100 CFM rule, Equivalent Duct Length static loss, required rigid duct diameter in inches, and IRC M1503.4 400-CFM Make-Up Air requirement.",
  "hardware_bundle": [
    {{
      "badge": "{hood_in}\" / {sp['recommended_blower_cfm']} CFM Hood",
      "title": "{hood_in}-Inch {sp['recommended_blower_cfm']} CFM Pro Stainless Steel Range Hood w/ Baffle Filters",
      "price_range": "$329 - $1,499",
      "amazon_query": "{hood_in} Inch {sp['recommended_blower_cfm']} CFM Stainless Steel Range Hood",
      "hood_note": "1-sentence thermal plume capture and stainless baffle note"
    }},
    {{
      "badge": "{sp['recommended_duct_inches']}\" Make-Up Air Damper",
      "title": "{sp['recommended_duct_inches']}-Inch Universal Motorized Make-Up Air Damper Kit (IRC M1503.4)",
      "price_range": "$149 - $349",
      "amazon_query": "Broan {sp['recommended_duct_inches']} Inch Universal Make Up Air Damper Range Hood",
      "hood_note": "1-sentence backdraft prevention and pressure interlock note"
    }},
    {{
      "badge": "{sp['recommended_duct_inches']}\" Roof/Wall Vent Cap",
      "title": "{sp['recommended_duct_inches']}-Inch Heavy-Duty Steel Roof/Wall Exhaust Cap w/ Backdraft Damper",
      "price_range": "$59 - $149",
      "amazon_query": "{sp['recommended_duct_inches']} Inch Range Hood Roof Wall Exhaust Vent Cap",
      "hood_note": "1-sentence FPM air velocity and sone noise reduction note"
    }},
    {{
      "badge": "Inline Blower & UL-181 Tape",
      "title": "{sp['recommended_duct_inches']}-Inch Inline Remote Duct Blower + UL-181B-FX Aluminum Foil Tape",
      "price_range": "$69 - $279",
      "amazon_query": "{sp['recommended_duct_inches']} Inch Inline Duct Blower Fan Range Hood Foil Tape",
      "hood_note": "1-sentence grease-tight seam sealing and quiet remote exhaust note"
    }}
  ],
  "code_checklist": [
    "Step 1 regarding hood width overhang (+6 inches for kitchen islands) and 30-34 inch mounting height",
    "Step 2 regarding IRC M1503.4 mandatory Make-Up Air damper above 400 CFM",
    "Step 3 regarding smooth rigid galvanized round duct vs prohibited flex hose",
    "Step 4 regarding minimizing 90-degree elbows (25 Equivalent Feet each)"
  ],
  "faqs": [
    {{"q": "How many CFM do I need for {model_name}?", "a": "Exact BTU/100 calculation plus 20% duct static loss buffer."}},
    {{"q": "What size duct and Make-Up Air damper do I need for {sp['recommended_blower_cfm']} CFM?", "a": "Exact duct diameter in inches, FPM velocity, and IRC M1503.4 rule."}},
    {{"q": "How do I calculate Equivalent Duct Length for my range hood?", "a": "Exact straight feet plus 25 ft per 90-degree elbow and 30 ft for the roof/wall cap."}}
  ]
}}
"""

    for model_id in get_active_gemini_model(GEMINI_API_KEY):
        for attempt in range(2):
            try:
                endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent?key={GEMINI_API_KEY}"
                payload = {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": 0.2,
                        "responseMimeType": "application/json"
                    }
                }
                req = urllib.request.Request(
                    endpoint,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=40) as resp:
                    result = json.loads(resp.read().decode("utf-8"))
                    raw_text = result["candidates"][0]["content"]["parts"][0]["text"].strip()
                    raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
                    raw_text = re.sub(r"\s*```$", "", raw_text)
                    parsed = json.loads(raw_text)
                    if "specs" in parsed and "hardware_bundle" in parsed:
                        time.sleep(6)
                        return parsed
            except urllib.error.HTTPError as he:
                if he.code == 429:
                    print(f"[RATE-LIMIT] HTTP 429 on {model_id} (attempt {attempt + 1}). Cooling down 20s...")
                    time.sleep(20)
                else:
                    print(f"[WARN] HTTP {he.code} on {model_id} for '{model_name}': {he}")
                    break
            except Exception as e:
                print(f"[WARN] Gemini ({model_id}) notice for '{model_name}': {e}")
                break

    return det_fallback


def build_hood_html_page(data, slug, mon_cfg):
    hood_name = data.get("hood_name", "Kitchen Range Hood System")
    sp = data.get("specs", {})
    stove_in = int(safe_float(sp.get("stove_width_inches", 36), 36))
    hood_in = int(safe_float(sp.get("recommended_hood_width_in", 36), 36))
    gas_btu = int(safe_float(sp.get("total_gas_btu", 65000), 65000))
    rec_cfm = int(safe_float(sp.get("recommended_blower_cfm", 780), 780))
    duct_in = int(safe_float(sp.get("recommended_duct_inches", 8), 8))
    fpm = int(safe_float(sp.get("duct_velocity_fpm", 2230), 2230))
    mount_t = sp.get("mount_type", "Wall-Mount Pro")

    header_cta = mon_cfg.get("header_cta", {})
    header_cta_url = build_amazon_url(header_cta.get("search_query", "Stainless+Steel+Range+Hood+Make+Up+Air+Damper"), mon_cfg)

    schema_graph = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "SoftwareApplication",
                "name": f"{hood_name} CFM, Duct Size & Make-Up Air Calculator",
                "applicationCategory": "UtilitiesApplication",
                "operatingSystem": "Web Browser",
                "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"}
            },
            {
                "@type": "FAQPage",
                "mainEntity": [
                    {
                        "@type": "Question",
                        "name": f.get("q", ""),
                        "acceptedAnswer": {"@type": "Answer", "text": f.get("a", "")}
                    } for f in data.get("faqs", [])
                ]
            }
        ]
    }

    bundle_html = ""
    for item in data.get("hardware_bundle", []):
        amz_url = build_amazon_url(item.get("amazon_query", item.get("title", "Stainless Steel Range Hood")), mon_cfg)
        bundle_html += f"""
        <div class="bg-slate-900 border border-slate-800 rounded-xl p-5 flex flex-col justify-between hover:border-teal-500/60 transition">
          <div>
            <div class="flex items-center justify-between gap-2 mb-2">
              <span class="text-xs font-bold uppercase tracking-wider bg-teal-500/10 text-teal-400 border border-teal-500/20 px-2.5 py-0.5 rounded">{item.get('badge', 'Kitchen HVAC')}</span>
              <span class="text-sm font-bold text-emerald-400">{item.get('price_range', '$69+')}</span>
            </div>
            <h3 class="text-base font-bold text-white mt-2">{item.get('title', '')}</h3>
            <p class="text-xs text-slate-400 mt-2 leading-relaxed">🍳 {item.get('hood_note', '')}</p>
          </div>
          <a href="{amz_url}" target="_blank" rel="nofollow sponsored" class="mt-5 block text-center bg-teal-500 hover:bg-teal-400 text-slate-950 font-extrabold py-2.5 px-4 rounded-lg text-sm transition shadow-lg">
            Check Price on Amazon →
          </a>
        </div>"""

    # Build Stove BTU & Width vs CFM, Duct Diameter & Make-Up Air Reference Matrix Table
    hood_tiers = [
        ("30\" Range (≤40,000 BTU / Induction)", "350 – 400 CFM", "6\" Rigid Round Duct", "Exempt (≤400 CFM)", "30\" Wall / Under-Cab"),
        ("30\" Pro Gas Range (55,000 BTU)", "600 – 700 CFM", "6\" or 8\" Rigid Duct", "6\" Motorized MUA Damper", "30\"–36\" Canopy"),
        ("36\" Pro Gas Range (65,000 BTU)", "750 – 900 CFM", "8\" Rigid Round Duct", "8\" Motorized MUA Damper", "36\"–42\" Canopy"),
        ("36\" Island Gas Cooktop (60,000 BTU)", "850 – 1,000 CFM", "8\" or 10\" Rigid Duct", "8\" Motorized MUA Damper", "42\" Island Canopy"),
        ("48\" Pro Gas Range (100,000+ BTU)", "1,100 – 1,300 CFM", "10\" Rigid Round Duct", "10\" Motorized MUA Damper", "48\"–54\" Pro Canopy")
    ]
    matrix_rows_html = ""
    for st_lbl, cf_lbl, du_lbl, mu_lbl, ca_lbl in hood_tiers:
        matrix_rows_html += f"""
        <tr class="border-b border-slate-800 hover:bg-slate-800/40">
          <td class="py-3 px-4 font-bold text-white">{st_lbl}</td>
          <td class="py-3 px-4 font-bold text-teal-400">{cf_lbl}</td>
          <td class="py-3 px-4 text-emerald-400 font-semibold">{du_lbl}</td>
          <td class="py-3 px-4 text-slate-300">{mu_lbl}</td>
          <td class="py-3 px-4 text-xs text-slate-300">{ca_lbl}</td>
        </tr>"""

    checklist_html = ""
    for idx, step_text in enumerate(data.get("code_checklist", []), start=1):
        checklist_html += f"""
        <label class="flex items-start gap-3.5 bg-slate-900 border border-slate-800 rounded-xl p-4 cursor-pointer hover:border-slate-700 transition">
          <input type="checkbox" class="mt-1 w-5 h-5 accent-teal-500 rounded cursor-pointer hood-check">
          <span class="text-sm text-slate-200 leading-relaxed"><strong>IRC Code Step {idx}:</strong> {step_text}</span>
        </label>"""

    faqs_html = "".join([
        f"<div class='bg-slate-900 border border-slate-800 rounded-xl p-5'><h3 class='font-bold text-white text-base mb-2'>{f.get('q', '')}</h3><p class='text-sm text-slate-300 leading-relaxed'>{f.get('a', '')}</p></div>"
        for f in data.get("faqs", [])
    ])

    canonical_url = f"{SITE_BASE_URL}/{slug}.html"
    amz_domain = mon_cfg.get("marketplace_domain", "www.amazon.com")
    amz_tag = mon_cfg.get("amazon_associate_tag", "YOUR_AMAZON_TAG-20")

    html = f"""<!DOCTYPE html>
<html lang="en" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{data.get('seo_title', hood_name)}</title>
  <meta name="description" content="{data.get('meta_description', '')}">
  <link rel="canonical" href="{canonical_url}">
  <meta property="og:title" content="{data.get('seo_title', hood_name)}">
  <meta property="og:description" content="{data.get('meta_description', '')}">
  <meta property="og:type" content="article">
  <meta property="og:url" content="{canonical_url}">
  <script src="https://cdn.tailwindcss.com"></script>
  <script type="application/ld+json">{json.dumps(schema_graph)}</script>
</head>
<body class="bg-slate-950 text-slate-100 antialiased min-h-screen flex flex-col">
  <header class="border-b border-slate-800 bg-slate-900/80 backdrop-blur sticky top-0 z-30">
    <div class="max-w-5xl mx-auto px-4 py-3.5 flex items-center justify-between">
      <a href="index.html" class="text-lg font-black tracking-tight text-white flex items-center gap-2">
        <span class="bg-teal-500 text-slate-950 px-2 py-0.5 rounded font-black">HOOD</span>CFMIndex
      </a>
      <a href="{header_cta_url}" target="_blank" rel="nofollow sponsored" class="text-xs sm:text-sm bg-teal-500 hover:bg-teal-400 text-slate-950 font-extrabold px-3.5 py-2 rounded-lg transition">
        {header_cta.get('cta_text', 'Shop Range Hoods & Make-Up Air →')}
      </a>
    </div>
  </header>

  <main class="max-w-5xl mx-auto px-4 py-10 flex-1 w-full">
    <div class="mb-8">
      <div class="flex flex-wrap items-center gap-2.5 mb-3">
        <span class="text-xs font-extrabold uppercase tracking-widest bg-teal-500 text-slate-950 px-3 py-1 rounded-full">{rec_cfm:,} CFM ({hood_in}" Canopy)</span>
        <span class="text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-3 py-1 rounded-full">{gas_btu:,} BTU Stove | {duct_in}" Rigid Duct</span>
        <span class="text-xs font-semibold bg-slate-800 text-slate-300 px-3 py-1 rounded-full">IRC M1503.4: {"MUA Required" if rec_cfm > 400 else "MUA Exempt"} | {mount_t}</span>
      </div>
      <h1 class="text-3xl sm:text-4xl font-black text-white leading-tight">{data.get('seo_title', hood_name)}</h1>
      <div class="mt-4 bg-slate-900 border-l-4 border-teal-500 p-4 rounded-r-xl text-sm text-slate-200 leading-relaxed">
        <strong>HVI / NKBA & IRC M1503.4 Engineering Verdict:</strong> {data.get('hvi_verdict', '')}
      </div>
    </div>

    <!-- INTERACTIVE RANGE HOOD CFM, EQUIVALENT DUCT LENGTH & MAKE-UP AIR CALCULATOR -->
    <section class="bg-slate-900 border border-slate-800 rounded-2xl p-6 sm:p-8 mb-12 shadow-2xl">
      <h2 class="text-xl font-extrabold text-white mb-2">Interactive {hood_name} CFM, Duct & Make-Up Air Calculator</h2>
      <p class="text-xs text-slate-400 mb-6">Adjust your gas stove total BTU rating, stove width, mounting style (Wall vs. Island), and duct elbows to compute required Blower CFM, rigid duct diameter, and IRC M1503.4 Make-Up Air damper status.</p>

      <div class="grid md:grid-cols-2 gap-8 items-center">
        <div class="space-y-5">
          <div>
            <div class="flex justify-between text-sm font-medium mb-1.5">
              <label for="btuSlider" class="text-slate-300">Total Gas Stove Burner Output (BTU/hr)</label>
              <span class="text-teal-400 font-bold"><span id="btuVal">{gas_btu:,}</span> BTU</span>
            </div>
            <input id="btuSlider" type="range" min="30000" max="140000" step="5000" value="{gas_btu}" class="w-full accent-teal-500 cursor-pointer">
          </div>

          <div class="grid grid-cols-2 gap-3">
            <div>
              <label for="widthSelect" class="block text-xs font-medium text-slate-400 mb-1">Range / Cooktop Width</label>
              <select id="widthSelect" class="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-teal-500">
                <option value="30" {"selected" if stove_in == 30 else ""}>30-Inch Range (2.5 ft)</option>
                <option value="36" {"selected" if stove_in == 36 else ""}>36-Inch Pro Range (3.0 ft)</option>
                <option value="48" {"selected" if stove_in == 48 else ""}>48-Inch Pro Range (4.0 ft)</option>
                <option value="60" {"selected" if stove_in == 60 else ""}>60-Inch Estate Range (5.0 ft)</option>
              </select>
            </div>
            <div>
              <label for="mountSelect" class="block text-xs font-medium text-slate-400 mb-1">Hood Mounting Location</label>
              <select id="mountSelect" class="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-teal-500">
                <option value="1.00|0" selected>Against Wall (100 CFM/ft)</option>
                <option value="1.35|6">Kitchen Island (150 CFM/ft + 6" Width)</option>
              </select>
            </div>
          </div>

          <div>
            <div class="flex justify-between text-sm font-medium mb-1.5">
              <label for="elbowSlider" class="text-slate-300">Number of 90° Duct Elbows (+25 Equivalent Feet Each)</label>
              <span class="text-teal-400 font-bold"><span id="elbowVal">2</span> × 90° Elbows</span>
            </div>
            <input id="elbowSlider" type="range" min="0" max="4" step="1" value="2" class="w-full accent-teal-500 cursor-pointer">
          </div>
        </div>

        <div class="grid grid-cols-2 gap-4">
          <div class="bg-slate-950 border border-teal-500/30 rounded-xl p-4">
            <span class="text-xs uppercase text-teal-400 font-bold">Required Blower CFM</span>
            <div class="text-2xl sm:text-3xl font-black text-white mt-1"><span id="cfmOut">{rec_cfm:,}</span> <span class="text-xs font-normal text-slate-400">CFM</span></div>
            <p id="canopyNoteOut" class="text-xs text-teal-400 font-semibold mt-1">Min Canopy Width: {hood_in}"</p>
          </div>

          <div class="bg-slate-950 border border-emerald-500/30 rounded-xl p-4">
            <span class="text-xs uppercase text-emerald-400 font-bold">Duct & IRC Make-Up Air</span>
            <div id="ductOut" class="text-xl sm:text-2xl font-black text-emerald-400 mt-1">{duct_in}" Rigid Duct</div>
            <p id="muaNoteOut" class="text-xs text-amber-400 font-bold mt-1">⚠️ Need {duct_in}" MUA Damper</p>
          </div>
        </div>
      </div>

      <div class="mt-6 bg-teal-950/40 border border-teal-500/30 rounded-xl p-4 flex flex-col sm:flex-row items-center justify-between gap-4">
        <div id="hoodAdviceBanner" class="text-sm text-teal-100 font-medium"></div>
        <a id="dynamicHoodBtn" href="{header_cta_url}" target="_blank" rel="nofollow sponsored" class="shrink-0 bg-teal-500 hover:bg-teal-400 text-slate-950 font-extrabold px-4 py-2.5 rounded-lg text-xs uppercase tracking-wider transition">
          Shop Matched Range Hood & MUA Kit on Amazon →
        </a>
      </div>
    </section>

    <section class="mb-12">
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-2xl font-extrabold text-white">Complete {hood_name} Hood, MUA Damper & Ducting Bundle</h2>
        <span class="text-xs text-slate-400">HVI-2100 & IRC Section M1503.4 Compliant</span>
      </div>
      <div class="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">{bundle_html}</div>
    </section>

    <section class="mb-12">
      <h2 class="text-2xl font-extrabold text-white mb-4">Gas Stove BTU, Range Hood CFM, Rigid Duct Size & IRC Make-Up Air Chart</h2>
      <div class="overflow-x-auto bg-slate-900 border border-slate-800 rounded-xl">
        <table class="w-full text-left border-collapse text-sm">
          <thead>
            <tr class="border-b border-slate-800 bg-slate-950/60 text-slate-400 uppercase text-xs">
              <th class="py-3.5 px-4">Stove Size & BTU</th>
              <th class="py-3.5 px-4 text-teal-400">Recommended Blower CFM</th>
              <th class="py-3.5 px-4 text-emerald-400">Rigid Round Duct</th>
              <th class="py-3.5 px-4">IRC M1503.4 Make-Up Air</th>
              <th class="py-3.5 px-4">Canopy Width</th>
            </tr>
          </thead>
          <tbody>{matrix_rows_html}</tbody>
        </table>
      </div>
    </section>

    <section class="mb-12">
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-2xl font-extrabold text-white">NKBA & IRC M1503.4 Kitchen Exhaust & Backdraft Safety Checklist</h2>
        <span id="hoodBadge" class="text-xs font-bold bg-slate-800 text-teal-400 px-3 py-1 rounded-full">0 / 4 Completed</span>
      </div>
      <div class="space-y-3">{checklist_html}</div>
    </section>

    <section class="mb-12">
      <h2 class="text-2xl font-extrabold text-white mb-5">Frequently Asked Questions ({hood_name})</h2>
      <div class="space-y-4">{faqs_html}</div>
    </section>
  </main>

  <footer class="border-t border-slate-800 py-8 text-center text-xs text-slate-500 px-4">
    <p>© {datetime.now(timezone.utc).year} HoodCFMIndex. Independent Kitchen Ventilation & IRC M1503.4 Engineering Database. As an Amazon Associate, we earn from qualifying purchases.</p>
  </footer>

  <script>
    const amzDomain = "{amz_domain}";
    const amzTag = "{amz_tag}";

    const btuSlider = document.getElementById('btuSlider');
    const widthSelect = document.getElementById('widthSelect');
    const mountSelect = document.getElementById('mountSelect');
    const elbowSlider = document.getElementById('elbowSlider');
    const btuVal = document.getElementById('btuVal');
    const elbowVal = document.getElementById('elbowVal');
    const cfmOut = document.getElementById('cfmOut');
    const canopyNoteOut = document.getElementById('canopyNoteOut');
    const ductOut = document.getElementById('ductOut');
    const muaNoteOut = document.getElementById('muaNoteOut');
    const hoodAdviceBanner = document.getElementById('hoodAdviceBanner');
    const dynamicHoodBtn = document.getElementById('dynamicHoodBtn');

    function recalculateHood() {{
      const btu = parseInt(btuSlider.value, 10);
      const stoveIn = parseInt(widthSelect.value, 10);
      const mountParts = mountSelect.value.split('|');
      const mountMult = parseFloat(mountParts[0]);
      const extraWidthIn = parseInt(mountParts[1], 10);
      const elbows = parseInt(elbowSlider.value, 10);

      btuVal.textContent = btu.toLocaleString();
      elbowVal.textContent = elbows;

      const btuCfm = btu / 100.0;
      const widthCfm = (stoveIn / 12.0) * 100.0;
      const baseCfm = Math.max(btuCfm, widthCfm) * mountMult;

      // Equivalent Duct Length: 15ft straight + (elbows * 25ft) + 30ft roof cap
      const equivFt = 45 + (elbows * 25);
      const lossMult = 1.0 + (equivFt * 0.0022);
      const finalCfm = Math.ceil((baseCfm * lossMult) / 50) * 50;

      const canopyIn = stoveIn + extraWidthIn;
      let ductDia = 6;
      if (finalCfm <= 420) ductDia = 6;
      else if (finalCfm <= 900) ductDia = 8;
      else ductDia = 10;

      cfmOut.textContent = finalCfm.toLocaleString();
      canopyNoteOut.textContent = `Min Canopy Width: ${{canopyIn}}" (${{equivFt}} ft EL)`;
      ductOut.textContent = `${{ductDia}}" Rigid Duct`;

      if (finalCfm > 400) {{
        muaNoteOut.textContent = `⚠️ Need ${{ductDia}}" MUA Damper (>400 CFM)`;
        muaNoteOut.className = "text-xs text-amber-400 font-bold mt-1";
      }} else {{
        muaNoteOut.textContent = "✅ MUA Exempt (≤400 CFM Code)";
        muaNoteOut.className = "text-xs text-emerald-400 font-semibold mt-1";
      }}

      hoodAdviceBanner.innerHTML = `🍳 <strong>NKBA & IRC Spec:</strong> A ${{btu.toLocaleString()}} BTU range with ${{elbows}}× 90° elbows (${{equivFt}} ft Equivalent Length) requires a <strong>${{canopyIn}}-Inch ${{finalCfm.toLocaleString()}} CFM Stainless Range Hood</strong> vented via <strong>${{ductDia}}-Inch Rigid Metal Duct</strong>${{finalCfm > 400 ? ' + an <strong>IRC M1503.4 Motorized Make-Up Air Damper</strong>' : ''}}.`;
      dynamicHoodBtn.href = `https://${{amzDomain}}/s?k=${{canopyIn}}+Inch+${{finalCfm}}+CFM+Stainless+Range+Hood+${{ductDia}}+Inch+Make+Up+Air+Damper&tag=${{amzTag}}`;
    }}

    btuSlider.addEventListener('input', recalculateHood);
    widthSelect.addEventListener('change', recalculateHood);
    mountSelect.addEventListener('change', recalculateHood);
    elbowSlider.addEventListener('input', recalculateHood);
    recalculateHood();

    const checks = document.querySelectorAll('.hood-check');
    const badge = document.getElementById('hoodBadge');
    checks.forEach(ch => {{
      ch.addEventListener('change', () => {{
        const done = Array.from(checks).filter(c => c.checked).length;
        badge.textContent = `${{done}} / ${{checks.length}} Completed`;
      }});
    }});
  </script>
</body>
</html>"""

    os.makedirs(DOCS_DIR, exist_ok=True)
    with open(os.path.join(DOCS_DIR, f"{slug}.html"), "w", encoding="utf-8") as f:
        f.write(html)


def rebuild_portal_sitemap_and_rss(published, mon_cfg):
    header_cta = mon_cfg.get("header_cta", {})
    header_cta_url = build_amazon_url(header_cta.get("search_query", "Stainless+Steel+Range+Hood+Make+Up+Air+Damper"), mon_cfg)

    cards_html = ""
    for item in reversed(published):
        cards_html += f"""
        <a href="{item['slug']}.html" class="block bg-slate-900 border border-slate-800 hover:border-teal-500/60 rounded-xl p-5 transition group">
          <div class="flex items-center justify-between mb-2">
            <span class="text-xs font-black uppercase bg-teal-500 text-slate-950 px-2.5 py-0.5 rounded">{item.get('cfm', 750):,} CFM ({item.get('hood_in', 36)}")</span>
            <span class="text-xs text-slate-400">{item.get('btu', 65000) // 1000}k BTU | {item.get('duct_in', 8)}" Duct</span>
          </div>
          <h2 class="text-base font-bold text-white group-hover:text-teal-400 transition">{item['hood_name']}</h2>
          <p class="text-xs text-slate-400 mt-2 line-clamp-2">{item['description']}</p>
          <span class="inline-block mt-4 text-xs font-extrabold text-teal-400">Calculate CFM, Duct & Make-Up Air →</span>
        </a>"""

    index_html = f"""<!DOCTYPE html>
<html lang="en" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>HoodCFMIndex — Kitchen Range Hood CFM, Gas BTU, Duct Size & Make-Up Air Calculator (2026)</title>
  <meta name="description" content="Calculate exact kitchen range hood CFM for gas stove BTU output, rigid duct diameter, Equivalent Duct Length static loss, and IRC M1503.4 400-CFM Make-Up Air damper sizing for ZLINE, Vent-A-Hood, Hauslane, Broan, Wolf, and Thor ranges.">
  <link rel="canonical" href="{SITE_BASE_URL}/">
  <link rel="alternate" type="application/rss+xml" title="HoodCFMIndex RSS Feed" href="{SITE_BASE_URL}/rss.xml">
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen flex flex-col">
  <header class="border-b border-slate-800 bg-slate-900/80 sticky top-0 z-30 backdrop-blur">
    <div class="max-w-5xl mx-auto px-4 py-3.5 flex items-center justify-between">
      <div class="text-lg font-black text-white flex items-center gap-2">
        <span class="bg-teal-500 text-slate-950 px-2 py-0.5 rounded font-black">HOOD</span>CFMIndex
      </div>
      <a href="{header_cta_url}" target="_blank" rel="nofollow sponsored" class="text-xs sm:text-sm bg-teal-500 hover:bg-teal-400 text-slate-950 font-extrabold px-3.5 py-2 rounded-lg transition">
        {header_cta.get('cta_text', 'Shop Range Hoods & Make-Up Air →')}
      </a>
    </div>
  </header>

  <main class="max-w-5xl mx-auto px-4 py-12 flex-1 w-full">
    <div class="text-center max-w-2xl mx-auto mb-10">
      <h1 class="text-3xl sm:text-5xl font-black text-white tracking-tight">Range Hood CFM, Gas BTU, Duct Size & Make-Up Air Database</h1>
      <p class="text-slate-400 mt-3 text-base sm:text-lg">Select your range hood model or gas stove BTU rating below to calculate HVI/NKBA exhaust CFM, rigid round duct diameter (6"/8"/10"), and IRC M1503.4 motorized Make-Up Air damper requirements.</p>
      <div class="mt-6">
        <input id="filterInput" type="text" placeholder="Search range hood or stove size (e.g. ZLINE 36, Hauslane, Vent-A-Hood, Wolf 48, 60000 BTU, Make Up Air...)" class="w-full bg-slate-900 border border-slate-700 rounded-xl px-4 py-3.5 text-sm text-white focus:outline-none focus:border-teal-500">
      </div>
    </div>

    <div id="hoodGrid" class="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">{cards_html}</div>
  </main>

  <footer class="border-t border-slate-800 py-8 text-center text-xs text-slate-500">
    <p>© {datetime.now(timezone.utc).year} HoodCFMIndex. As an Amazon Associate, we earn from qualifying purchases.</p>
  </footer>

  <script>
    const filterInput = document.getElementById('filterInput');
    const cards = Array.from(document.getElementById('hoodGrid').children);
    filterInput.addEventListener('input', (e) => {{
      const q = e.target.value.toLowerCase();
      cards.forEach(c => {{
        c.style.display = c.textContent.toLowerCase().includes(q) ? 'block' : 'none';
      }});
    }});
  </script>
</body>
</html>"""

    os.makedirs(DOCS_DIR, exist_ok=True)
    with open(os.path.join(DOCS_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(index_html)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    urls_xml = f"""  <url>
    <loc>{SITE_BASE_URL}/</loc>
    <lastmod>{today}</lastmod>
    <changefreq>daily</changefreq>
    <priority>1.0</priority>
  </url>\n"""

    for item in published:
        urls_xml += f"""  <url>
    <loc>{SITE_BASE_URL}/{item['slug']}.html</loc>
    <lastmod>{item.get('date', today)}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.9</priority>
  </url>\n"""

    with open(os.path.join(DOCS_DIR, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write(f"""<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{urls_xml}</urlset>""")

    rss_items = ""
    for item in list(reversed(published))[:30]:
        rss_items += f"""    <item>
      <title>{item['title']}</title>
      <link>{SITE_BASE_URL}/{item['slug']}.html</link>
      <guid>{SITE_BASE_URL}/{item['slug']}.html</guid>
      <description>{item['description']}</description>
    </item>\n"""

    rss_xml = f"""<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>HoodCFMIndex Kitchen Range Hood & Make-Up Air Sizing Database</title>
    <link>{SITE_BASE_URL}/</link>
    <description>Interactive Range Hood CFM, Gas Stove BTU, Rigid Duct & IRC M1503.4 Make-Up Air Calculators</description>
    <atom:link href="{SITE_BASE_URL}/rss.xml" rel="self" type="application/rss+xml" />
    <atom:link href="https://pubsubhubbub.appspot.com/" rel="hub" />
{rss_items}  </channel>
</rss>"""

    with open(os.path.join(DOCS_DIR, "rss.xml"), "w", encoding="utf-8") as f:
        f.write(rss_xml)

    with open(os.path.join(DOCS_DIR, "robots.txt"), "w", encoding="utf-8") as f:
        f.write(f"User-agent: *\nAllow: /\nSitemap: {SITE_BASE_URL}/sitemap.xml\n")

    with open(os.path.join(DOCS_DIR, f"{INDEXNOW_KEY}.txt"), "w", encoding="utf-8") as f:
        f.write(INDEXNOW_KEY)


def notify_search_engines(new_urls):
    """Multi-Endpoint Search Engine Pinger (IndexNow Global + Bing + Google WebSub)."""
    if not SITE_BASE_URL or not new_urls:
        return
    parsed_host = urllib.parse.urlparse(SITE_BASE_URL).netloc
    payload = {
        "host": parsed_host,
        "key": INDEXNOW_KEY,
        "keyLocation": f"{SITE_BASE_URL}/{INDEXNOW_KEY}.txt",
        "urlList": new_urls
    }
    for idx_endpoint in ["https://api.indexnow.org/indexnow", "https://www.bing.com/indexnow"]:
        try:
            req = urllib.request.Request(
                idx_endpoint,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json; charset=utf-8"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                print(f"[INDEXNOW] Pushed {len(new_urls)} URLs to {idx_endpoint} (HTTP {resp.status})")
                break
        except Exception as e:
            print(f"[WARN] IndexNow ({idx_endpoint}) notice: {e}")

    try:
        hub_data = urllib.parse.urlencode({
            "hub.mode": "publish",
            "hub.url": f"{SITE_BASE_URL}/rss.xml"
        }).encode("utf-8")
        req_hub = urllib.request.Request(
            "https://pubsubhubbub.appspot.com/",
            data=hub_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST"
        )
        with urllib.request.urlopen(req_hub, timeout=15) as resp_hub:
            print(f"[WEBSUB] Google PubSubHubbub ping status: {resp_hub.status}")
    except Exception as e:
        print(f"[WARN] WebSub ping notice: {e}")


def main():
    published = load_json(PUBLISHED_FILE, [])
    mon_cfg = load_json(MONETIZATION_FILE, {})
    published_slugs = {item["slug"] for item in published if "slug" in item}

    candidates = []
    if CUSTOM_HOOD:
        candidates.append((CUSTOM_HOOD.strip(), 36, 65000, 36, 780, 8, "Wall-Mount Pro"))
    candidates.extend(SEED_HOODS)
    candidates.extend(discover_google_hood_queries(published_slugs))

    new_urls = []
    count = 0

    for hood_tuple in candidates:
        if count >= PAGES_PER_RUN:
            break
        h_name = hood_tuple[0]
        slug = slugify(f"{h_name}-cfm-duct-calculator")
        if slug in published_slugs:
            continue

        print(f"[ENGINE] Generating range hood CFM & Make-Up Air calculator for: {h_name}...")
        try:
            data = generate_hood_data(hood_tuple)
            build_hood_html_page(data, slug, mon_cfg)
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            sp = data.get("specs", {})

            published.append({
                "hood_name": data.get("hood_name", h_name),
                "slug": slug,
                "title": data.get("seo_title", f"{h_name} Range Hood Calculator"),
                "description": data.get("meta_description", ""),
                "hood_in": int(safe_float(sp.get("recommended_hood_width_in", hood_tuple[3]), hood_tuple[3])),
                "btu": int(safe_float(sp.get("total_gas_btu", hood_tuple[2]), hood_tuple[2])),
                "cfm": int(safe_float(sp.get("recommended_blower_cfm", hood_tuple[4]), hood_tuple[4])),
                "duct_in": int(safe_float(sp.get("recommended_duct_inches", hood_tuple[5]), hood_tuple[5])),
                "date": today
            })
            published_slugs.add(slug)
            if SITE_BASE_URL:
                new_urls.append(f"{SITE_BASE_URL}/{slug}.html")
            count += 1
            if count < PAGES_PER_RUN:
                time.sleep(15)
        except Exception as e:
            print(f"[ERROR] Failed building {h_name}: {e}")

    save_json(PUBLISHED_FILE, published)
    rebuild_portal_sitemap_and_rss(published, mon_cfg)
    if new_urls and SITE_BASE_URL:
        new_urls.append(f"{SITE_BASE_URL}/")
        notify_search_engines(new_urls)
    print(f"[DONE] Published {count} new kitchen range hood CFM & Make-Up Air calculator pages.")


if __name__ == "__main__":
    main()
