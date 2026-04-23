"""
╔══════════════════════════════════════════════════════════════════════════════╗
║   DASHBOARD TRS/OEE – SIMED  v7.0 (PROFESSIONNEL AMÉLIORÉ)                 ║
║   Authentification + Base SQLite + Import intelligent + Prévisions          ║
║   Design premium, animations, KPIs enrichis, heatmap, waterfall OEE        ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import numpy as np
from datetime import datetime, timedelta, date
import sqlite3, os, io, warnings, hashlib, secrets
from sklearn.linear_model import LinearRegression
warnings.filterwarnings('ignore')

# ══════════════════════════════════════════════════════════════
# PAGE CONFIG
# ══════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="TRS/OEE – SIMED",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ══════════════════════════════════════════════════════════════
# BASE DE DONNÉES SQLITE
# ══════════════════════════════════════════════════════════════
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "simed_database.db")

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    with get_conn() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS production (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            date_jour            TEXT    NOT NULL,
            semaine              INTEGER,
            ligne                TEXT,
            code_machine         TEXT,
            type_machine         TEXT,
            operateur            TEXT,
            code_probleme        TEXT,
            categorie_panne      TEXT,
            categorie_iso        TEXT,
            departement_resp     TEXT,
            description_probleme TEXT,
            temps_arret          REAL DEFAULT 0,
            produit              TEXT,
            quantite             REAL DEFAULT 0,
            rebuts               REAL DEFAULT 0,
            created_at           TEXT DEFAULT (datetime('now'))
        )""")
        conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            salt          TEXT NOT NULL,
            role          TEXT DEFAULT 'user',
            created_at    TEXT DEFAULT (datetime('now'))
        )""")
        cursor = conn.execute("SELECT COUNT(*) FROM users")
        if cursor.fetchone()[0] == 0:
            salt = secrets.token_hex(16)
            pwd = "SIMED2025"
            hash_obj = hashlib.pbkdf2_hmac('sha256', pwd.encode(), salt.encode(), 100000)
            password_hash = hash_obj.hex()
            conn.execute("INSERT INTO users (username, password_hash, salt, role) VALUES (?, ?, ?, ?)",
                         ("admin", password_hash, salt, "admin"))
            conn.commit()
init_db()
# ══════════════════════════════════════════════════════════════
# LOGO
# ══════════════════════════════════════════════════════════════
LOGO_PATH = "simed-200x200-1.png"

def afficher_logo(emplacement="sidebar", largeur=120):
    if os.path.exists(LOGO_PATH):
        if emplacement == "sidebar":
            st.sidebar.image(LOGO_PATH, width=largeur)
        else:
            st.image(LOGO_PATH, width=largeur)

# ══════════════════════════════════════════════════════════════
# AUTHENTIFICATION
# ══════════════════════════════════════════════════════════════
def hash_password(password, salt):
    return hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000).hex()

def verify_password(username, password):
    with get_conn() as conn:
        row = conn.execute("SELECT password_hash, salt FROM users WHERE username = ?", (username,)).fetchone()
        if row is None:
            return False
        return hash_password(password, row[1]) == row[0]

def register_user(username, password):
    if not username or not password:
        return False, "Nom d'utilisateur et mot de passe requis."
    if len(password) < 6:
        return False, "Le mot de passe doit contenir au moins 6 caractères."
    with get_conn() as conn:
        if conn.execute("SELECT username FROM users WHERE username = ?", (username,)).fetchone():
            return False, "Ce nom d'utilisateur existe déjà."
        salt = secrets.token_hex(16)
        conn.execute("INSERT INTO users (username, password_hash, salt) VALUES (?, ?, ?)",
                     (username, hash_password(password, salt), salt))
        conn.commit()
        return True, "Inscription réussie !"

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

def login_signup_page():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&display=swap');
    .stApp { background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #0f172a 100%); }
    .login-card {
        background: rgba(255,255,255,0.05);
        backdrop-filter: blur(20px);
        border: 1px solid rgba(255,255,255,0.1);
        border-radius: 24px;
        padding: 2.5rem;
        max-width: 460px;
        margin: 5% auto;
        box-shadow: 0 25px 50px rgba(0,0,0,0.5);
    }
    .login-logo {
        text-align: center;
        font-size: 3rem;
        margin-bottom: 0.5rem;
    }
    .login-title {
        text-align: center;
        font-size: 1.6rem;
        font-weight: 700;
        color: white;
        margin-bottom: 0.25rem;
        font-family: 'Space Grotesk', sans-serif;
    }
    .login-sub {
        text-align: center;
        color: #94a3b8;
        font-size: 0.85rem;
        margin-bottom: 2rem;
    }
    </style>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown('<div class="login-card">', unsafe_allow_html=True)
        if os.path.exists(LOGO_PATH):
            _, lc, _ = st.columns([1,2,1])
            lc.image(LOGO_PATH, width=120)
        else:
            st.markdown('<div class="login-logo">⚙️</div>', unsafe_allow_html=True)
        st.markdown('<div class="login-title">SIMED TRS Dashboard</div>', unsafe_allow_html=True)
        st.markdown('<div class="login-sub">Système de suivi de performance industrielle</div>', unsafe_allow_html=True)

        tab1, tab2 = st.tabs(["🔑 Connexion", "📝 Inscription"])
        with tab1:
            with st.form("login_form"):
                username = st.text_input("Identifiant", placeholder="admin")
                password = st.text_input("Mot de passe", type="password", placeholder="••••••••")
                c1, c2 = st.columns(2)
                submitted = c1.form_submit_button("Se connecter", use_container_width=True, type="primary")
                demo = c2.form_submit_button("Mode démo", use_container_width=True)
                if submitted:
                    if verify_password(username, password):
                        st.session_state.update({"authenticated": True, "username": username})
                        st.rerun()
                    else:
                        st.error("❌ Identifiants incorrects")
                if demo:
                    st.session_state.update({"authenticated": True, "username": "invité"})
                    st.rerun()

        with tab2:
            with st.form("signup_form"):
                new_user = st.text_input("Nom d'utilisateur", placeholder="ex: jean.dupont")
                new_pass = st.text_input("Mot de passe", type="password")
                confirm = st.text_input("Confirmer", type="password")
                if st.form_submit_button("Créer le compte", use_container_width=True, type="primary"):
                    if new_pass != confirm:
                        st.error("❌ Mots de passe différents")
                    else:
                        ok, msg = register_user(new_user, new_pass)
                        st.success(msg) if ok else st.error(f"❌ {msg}")
        st.markdown('</div>', unsafe_allow_html=True)

if not st.session_state["authenticated"]:
    login_signup_page()
    st.stop()

# ══════════════════════════════════════════════════════════════
# FONCTIONS PRODUCTION
# ══════════════════════════════════════════════════════════════
def load_db():
    with get_conn() as conn:
        df = pd.read_sql("SELECT * FROM production ORDER BY date_jour DESC", conn)
    if not df.empty:
        df['date_jour'] = pd.to_datetime(df['date_jour'])
    return df

def insert_row(row: dict):
    cols = [c for c in row if c != 'id']
    sql = f"INSERT INTO production ({', '.join(cols)}) VALUES ({', '.join(['?']*len(cols))})"
    with get_conn() as conn:
        conn.execute(sql, [row[c] for c in cols])
        conn.commit()

def import_df_to_db(df: pd.DataFrame):
    df2 = df.copy()
    df2['date_jour'] = pd.to_datetime(df2['date_jour']).dt.strftime('%Y-%m-%d')
    if 'semaine' not in df2.columns:
        df2['semaine'] = pd.to_datetime(df2['date_jour']).apply(
            lambda d: int(datetime.strptime(d,'%Y-%m-%d').isocalendar()[1]))
    needed = ['date_jour','semaine','ligne','code_machine','type_machine','operateur',
              'code_probleme','categorie_panne','categorie_iso','departement_resp',
              'description_probleme','temps_arret','produit','quantite','rebuts']
    for c in needed:
        if c not in df2.columns:
            df2[c] = 'N/A' if c not in ['temps_arret','quantite','rebuts','semaine'] else 0
    with get_conn() as conn:
        df2[needed].to_sql('production', conn, if_exists='append', index=False)
    return len(df2)

def detect_header_row(df_raw, required_cols):
    for i, row in df_raw.iterrows():
        cells = [str(cell).strip().lower() for cell in row.values]
        if all(col.lower() in cells for col in required_cols):
            return i
    return None

def load_uploaded_file(uploaded_file):
    try:
        if uploaded_file.name.endswith('.csv'):
            df_raw = pd.read_csv(uploaded_file, header=None)
        else:
            df_raw = pd.read_excel(uploaded_file, header=None)
        header_row = detect_header_row(df_raw, ['date_jour', 'quantite', 'temps_arret'])
        if header_row is None:
            return None, "Impossible de trouver la ligne d'en-tête requise."
        uploaded_file.seek(0)
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file, skiprows=header_row)
        else:
            df = pd.read_excel(uploaded_file, skiprows=header_row)
        return df, None
    except Exception as e:
        return None, str(e)

def validate_and_clean(df):
    errs, warns = [], []
    required = ['date_jour', 'quantite', 'temps_arret']
    missing = [c for c in required if c not in df.columns]
    if missing:
        errs.append(f"Colonnes manquantes : {missing}")
        return df, errs, warns
    df['date_jour'] = pd.to_datetime(df['date_jour'], errors='coerce')
    nb_bad = df['date_jour'].isna().sum()
    if nb_bad:
        warns.append(f"{nb_bad} date(s) invalide(s) ignorée(s)")
        df = df.dropna(subset=['date_jour'])
    for col in ['quantite', 'temps_arret']:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).clip(lower=0)
    if 'rebuts' not in df.columns:
        df['rebuts'] = 0
        warns.append("Colonne 'rebuts' absente → 0")
    else:
        df['rebuts'] = pd.to_numeric(df['rebuts'], errors='coerce').fillna(0).clip(lower=0)
        df['rebuts'] = df[['rebuts', 'quantite']].min(axis=1)
    defaults = {
        'ligne':'Non défini','code_machine':'N/A','type_machine':'N/A','operateur':'N/A',
        'code_probleme':'N/A','categorie_panne':'N/A','categorie_iso':'N/A',
        'departement_resp':'N/A','description_probleme':'N/A','produit':'N/A'
    }
    for col, default in defaults.items():
        if col not in df.columns:
            df[col] = default
    if 'semaine' not in df.columns:
        df['semaine'] = df['date_jour'].dt.isocalendar().week.astype(int)
    return df, errs, warns



# ══════════════════════════════════════════════════════════════
# CSS PREMIUM
# ══════════════════════════════════════════════════════════════
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap');

:root {
    --bg-primary: #0f172a;
    --bg-secondary: #1e293b;
    --bg-card: #ffffff;
    --accent-blue: #3b82f6;
    --accent-green: #10b981;
    --accent-amber: #f59e0b;
    --accent-red: #ef4444;
    --accent-purple: #8b5cf6;
    --text-primary: #0f172a;
    --text-muted: #64748b;
    --border: #e2e8f0;
}

html, body, [class*="css"] {
    font-family: 'Space Grotesk', sans-serif;
    color: var(--text-primary);
}

.stApp { background: #f1f5f9; }

/* SIDEBAR */
section[data-testid="stSidebar"] {
    background: #0f172a !important;
    border-right: none;
}
section[data-testid="stSidebar"] * { color: #e2e8f0 !important; }
section[data-testid="stSidebar"] .stMarkdown h5 {
    color: #94a3b8 !important;
    font-size: 0.65rem !important;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    margin-top: 1rem;
}
section[data-testid="stSidebar"] .stSelectbox label,
section[data-testid="stSidebar"] .stMultiSelect label,
section[data-testid="stSidebar"] .stNumberInput label,
section[data-testid="stSidebar"] .stRadio label { color: #cbd5e1 !important; font-size: 0.8rem !important; }

/* METRICS */
div[data-testid="metric-container"] {
    background: #ffffff;
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 1.25rem 1rem !important;
    position: relative;
    overflow: hidden;
    transition: box-shadow 0.2s;
}
div[data-testid="metric-container"]:hover {
    box-shadow: 0 8px 25px rgba(0,0,0,0.1);
}
div[data-testid="metric-container"]::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
    background: linear-gradient(90deg, var(--accent-blue), var(--accent-purple));
}
div[data-testid="metric-container"] label {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.7rem !important;
    color: var(--text-muted) !important;
    text-transform: uppercase;
    letter-spacing: 0.08em;
}
div[data-testid="metric-container"] [data-testid="stMetricValue"] {
    font-size: 1.9rem !important;
    font-weight: 700;
    color: var(--text-primary);
    line-height: 1.1;
}

/* SECTION HEADERS */
.sh {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.7rem;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--accent-blue);
    border-bottom: 2px solid #e2e8f0;
    padding-bottom: 10px;
    margin: 2rem 0 1rem;
    display: flex;
    align-items: center;
    gap: 8px;
}
.sh::before {
    content: '';
    display: inline-block;
    width: 3px; height: 14px;
    background: var(--accent-blue);
    border-radius: 2px;
}

/* BADGES */
.badge-ok   { background:#dcfce7; color:#15803d; border:1px solid #86efac; padding:5px 14px; border-radius:20px; font-weight:600; font-size:0.8rem; }
.badge-warn { background:#fef9c3; color:#854d0e; border:1px solid #fde047; padding:5px 14px; border-radius:20px; font-weight:600; font-size:0.8rem; }
.badge-alert{ background:#fee2e2; color:#b91c1c; border:1px solid #fca5a5; padding:5px 14px; border-radius:20px; font-weight:600; font-size:0.8rem; }

/* INFO BOXES */
.ib  { background:#f1f5f9; border-left:4px solid var(--accent-blue);   color:#1e293b; border-radius:8px; padding:12px 16px; margin:8px 0; font-size:0.88rem; }
.wb  { background:#fffbeb; border-left:4px solid var(--accent-amber);   color:#78350f; border-radius:8px; padding:12px 16px; margin:8px 0; font-size:0.88rem; }
.ab  { background:#fef2f2; border-left:4px solid var(--accent-red);     color:#7f1d1d; border-radius:8px; padding:12px 16px; margin:8px 0; font-size:0.88rem; }
.sb  { background:#dcfce7; border-left:4px solid var(--accent-green);   color:#14532d; border-radius:8px; padding:12px 16px; margin:8px 0; font-size:0.88rem; }

/* KPI CARD */
.kpi-card {
    background: white;
    border-radius: 16px;
    padding: 1.5rem;
    border: 1px solid var(--border);
    box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    transition: all 0.2s;
    text-align: center;
}
.kpi-card:hover { box-shadow: 0 8px 24px rgba(0,0,0,0.1); transform: translateY(-2px); }
.kpi-value { font-size: 2.2rem; font-weight: 700; line-height: 1; }
.kpi-label { font-size: 0.75rem; color: #64748b; text-transform: uppercase; letter-spacing: 0.06em; margin-top: 4px; }

/* TABS */
.stTabs [data-baseweb="tab-list"] {
    background: white;
    border-bottom: 2px solid var(--border);
    gap: 0;
}
.stTabs [data-baseweb="tab"] {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.72rem;
    font-weight: 500;
    color: #475569;
    padding: 12px 16px;
    border-bottom: 2px solid transparent;
    border-radius: 0;
}
.stTabs [aria-selected="true"] {
    color: var(--accent-blue) !important;
    border-bottom: 2px solid var(--accent-blue) !important;
    background: rgba(59,130,246,0.05) !important;
}

/* MACHINE STATUS */
.machine-card {
    background: white;
    border-radius: 12px;
    padding: 1rem;
    border: 1px solid var(--border);
    text-align: center;
    transition: all 0.2s;
}
.machine-running { border-top: 3px solid var(--accent-green); }
.machine-stopped { border-top: 3px solid var(--accent-red); }
.machine-partial  { border-top: 3px solid var(--accent-amber); }

/* HEADER */
.dash-header {
    background: linear-gradient(135deg, #0f172a 0%, #1e3a5f 100%);
    border-radius: 20px;
    padding: 1.5rem 2rem;
    margin-bottom: 1.5rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
    color: white;
}

.stDataFrame { border-radius: 12px; overflow: hidden; }
.stDownloadButton > button { border-radius: 20px !important; font-family: 'JetBrains Mono', monospace !important; font-size: 0.78rem !important; }
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
# THÈME PLOTLY
# ══════════════════════════════════════════════════════════════
PL = dict(
    paper_bgcolor='#ffffff', plot_bgcolor='#f8fafc',
    font=dict(family='Space Grotesk, sans-serif', color='#1e293b', size=12),
    xaxis=dict(gridcolor='#e2e8f0', linecolor='#cbd5e1', tickfont=dict(size=11)),
    yaxis=dict(gridcolor='#e2e8f0', linecolor='#cbd5e1', tickfont=dict(size=11)),
    legend=dict(bgcolor='rgba(255,255,255,0.9)', bordercolor='#e2e8f0', borderwidth=1),
    margin=dict(l=40, r=20, t=50, b=35),
    title_font=dict(size=14, color='#0f172a', family='Space Grotesk, sans-serif'),
)
C = {
    'trs':'#3b82f6', 'dispo':'#10b981', 'perf':'#f59e0b',
    'qual':'#8b5cf6', 'rebut':'#ef4444', 'alert':'#f97316',
    'neutral':'#94a3b8'
}

# ══════════════════════════════════════════════════════════════
# RÉFÉRENCES
# ══════════════════════════════════════════════════════════════
LIGNES = ['Ligne A','Ligne B','Ligne C']
MACHINES = ['M01','M02','M03','MA01','MA02','MB01','MB02','MC01','MC02']
TYPES_MACH = ['Presse','Remplisseuse','Mélangeuse','Encapsuleuse','Scelleuse','Étiqueteuse','Compression','Conditionnement']
CODES_PROB = {
    'E01':('Électrique','Défaut capteur','Breakdown','Maintenance'),
    'E02':('Électrique','Bande transporteuse bloquée','Breakdown','Maintenance'),
    'M02':('Mécanique','Surcharge moteur','Breakdown','Maintenance'),
    'M03':('Mécanique','Usure palier roulement','Breakdown','Maintenance'),
    'P03':('Process','Problème thermique','Process','Production'),
    'P04':('Process','Hors-spécification temp.','Process','Qualité'),
    'R04':('Réglage','Réglage outil','Setup','Production'),
    'R05':('Réglage','Changement format produit','Setup','Production'),
    'Q06':('Qualité','Contrôle IPC non-conforme','Quality','Qualité'),
    'A05':('Appro','Manque matière','Material','Logistique'),
    'A07':('Appro','Rupture matière première','Material','Logistique'),
    'U08':('Utilités','Air comprimé faible','Breakdown','Maintenance'),
}
PRODUITS = ['Comprimé 500mg','Sirop 125mg/5mL','Gélule 250mg','Pommade 1%','Sirop Y','Gélule Z','Pommade W']
OPERATEURS = ['Karim B.','Amira T.','Sami L.','Nadia M.','Youssef R.','Sophie','Jean','Marie','Pierre','Ahmed']

# ══════════════════════════════════════════════════════════════
# CALCULS TRS
# ══════════════════════════════════════════════════════════════
def compute_trs(df_in, TO, cadence):
    Tc = 1.0 / max(0.001, cadence)
    g = df_in.groupby(['date_jour','ligne','code_machine','produit','operateur']).agg(
        total_arret=('temps_arret','sum'),
        quantite_totale=('quantite','sum'),
        rebuts_totaux=('rebuts','sum'),
        nb_incidents=('temps_arret', lambda x: (x>0).sum())
    ).reset_index()
    g['TF'] = (TO - g['total_arret']).clip(lower=0)
    g['disponibilite'] = (g['TF'] / TO).clip(0, 1)
    g['performance'] = ((g['quantite_totale'] * Tc) / g['TF'].clip(lower=1)).clip(0, 1)
    g['conformes'] = (g['quantite_totale'] - g['rebuts_totaux']).clip(lower=0)
    g['qualite'] = np.where(g['quantite_totale'] > 0, g['conformes'] / g['quantite_totale'], 1.0).clip(0, 1)
    g['trs'] = (g['disponibilite'] * g['performance'] * g['qualite']).clip(0, 1)
    g['perte_dispo'] = (1 - g['disponibilite']) * TO
    g['perte_perf'] = g['disponibilite'] * (1 - g['performance']) * TO
    g['perte_qual'] = g['disponibilite'] * g['performance'] * (1 - g['qualite']) * TO
    return g

def compute_kpis(df_in, daily, TO, cadence):
    sm = lambda s: s.mean() if len(s) > 0 else 0
    tp = df_in['quantite'].sum()
    tr = df_in['rebuts'].sum()
    ta = df_in['temps_arret'].sum()
    nj = max(1, df_in['date_jour'].nunique())
    ni = (df_in['temps_arret'] > 0).sum()
    TF = max(0, nj * TO - ta)
    dpmo = (tr / max(1, tp)) * 1_000_000
    sigma = max(0, min(6, 0.8406 + np.sqrt(29.37 - 2.221 * np.log(max(1, dpmo)))))
    return {
        'trs': sm(daily['trs']), 'dispo': sm(daily['disponibilite']),
        'perf': sm(daily['performance']), 'qual': sm(daily['qualite']),
        'total_produit': tp, 'total_rebuts': tr,
        'taux_rebut': (tr / tp * 100) if tp > 0 else 0,
        'total_arret': ta, 'nb_incidents': ni, 'nb_jours': nj,
        'mtbf': TF / ni if ni > 0 else 0,
        'mttr': ta / ni if ni > 0 else 0,
        'taux_panne': ni / nj if nj > 0 else 0,
        'prod_horaire': max(0, tp - tr) / max(0.001, TF / 60),
        'sigma': sigma, 'dpmo': dpmo,
        'perte_dispo': sm(daily['perte_dispo']),
        'perte_perf': sm(daily['perte_perf']),
        'perte_qual': sm(daily['perte_qual']),
    }

def forecast_trs(daily_trs, jours=7):
    if len(daily_trs) < 3:
        return None, None
    X = np.arange(len(daily_trs)).reshape(-1, 1)
    model = LinearRegression().fit(X, daily_trs.values)
    future_X = np.arange(len(daily_trs), len(daily_trs) + jours).reshape(-1, 1)
    return model.predict(future_X), model

def generer_rapport_html(kpis, daily, sd, ed, src_label):
    rows = ""
    for _, row in daily.iterrows():
        trs_color = "#15803d" if row['trs'] >= 0.8 else ("#854d0e" if row['trs'] >= 0.6 else "#b91c1c")
        rows += f"""<tr>
            <td>{row['date_jour'].date()}</td>
            <td style="color:{trs_color};font-weight:600">{row['trs']*100:.1f}%</td>
            <td>{row['disponibilite']*100:.1f}%</td>
            <td>{row['performance']*100:.1f}%</td>
            <td>{row['qualite']*100:.1f}%</td>
        </tr>"""
    return f"""<html><head><meta charset="UTF-8"><title>Rapport TRS SIMED</title>
    <style>body{{font-family:Space Grotesk,sans-serif;background:#f1f5f9;color:#0f172a;padding:30px}}
    h1{{color:#0f172a;border-bottom:3px solid #3b82f6;padding-bottom:10px}}
    .grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin:20px 0}}
    .card{{background:white;border-radius:12px;padding:16px;border-top:3px solid #3b82f6;text-align:center}}
    .val{{font-size:2rem;font-weight:700;color:#0f172a}} .lbl{{color:#64748b;font-size:0.8rem}}
    table{{border-collapse:collapse;width:100%;background:white;border-radius:12px;overflow:hidden}}
    th{{background:#0f172a;color:white;padding:12px;text-align:left}}
    td{{padding:10px 12px;border-bottom:1px solid #e2e8f0}}</style></head>
    <body><h1>📊 Rapport TRS — SIMED</h1>
    <p>Période : <b>{sd}</b> → <b>{ed}</b> | Source : {src_label} | {kpis['nb_jours']} jours</p>
    <div class="grid">
    <div class="card"><div class="val">{kpis['trs']*100:.1f}%</div><div class="lbl">TRS Global</div></div>
    <div class="card"><div class="val">{kpis['dispo']*100:.1f}%</div><div class="lbl">Disponibilité</div></div>
    <div class="card"><div class="val">{kpis['perf']*100:.1f}%</div><div class="lbl">Performance</div></div>
    <div class="card"><div class="val">{kpis['qual']*100:.1f}%</div><div class="lbl">Qualité</div></div>
    <div class="card"><div class="val">{kpis['total_produit']:,.0f}</div><div class="lbl">Production totale</div></div>
    <div class="card"><div class="val">{kpis['taux_rebut']:.2f}%</div><div class="lbl">Taux de rebut</div></div>
    <div class="card"><div class="val">{kpis['sigma']:.2f}σ</div><div class="lbl">Niveau Sigma</div></div>
    <div class="card"><div class="val">{kpis['mtbf']:.0f}min</div><div class="lbl">MTBF</div></div>
    </div>
    <h2>Évolution quotidienne</h2>
    <table><tr><th>Date</th><th>TRS</th><th>Disponibilité</th><th>Performance</th><th>Qualité</th></tr>
    {rows}</table></body></html>"""

# ══════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════
with st.sidebar:
    afficher_logo("sidebar", 140)
    st.markdown("### ⚙️ TRS / OEE", unsafe_allow_html=True)
    st.markdown(f'<div style="font-family:JetBrains Mono,monospace;font-size:0.7rem;color:#94a3b8;padding:4px 0;">👤 {st.session_state["username"]}</div>', unsafe_allow_html=True)

    if st.button("🔓 Déconnexion", use_container_width=True):
        st.session_state.update({"authenticated": False})
        st.session_state.pop("username", None)
        st.rerun()

    st.markdown("---", unsafe_allow_html=True)
    df_db = load_db()
    nb_db = len(df_db)
    box_cls = "sb" if nb_db > 0 else "wb"
    st.markdown(f'<div class="{box_cls}">{"✅" if nb_db>0 else "⚠️"} <b>{nb_db:,} enreg.</b><br><span style="font-size:0.72rem;">simed_database.db</span></div>', unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    if c1.button("↺ Refresh", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    if nb_db > 0:
        c2.download_button("📥 Export", df_db.to_csv(index=False).encode('utf-8'), "simed_db.csv", "text/csv")

    st.markdown("---", unsafe_allow_html=True)
    st.markdown("##### 📂 IMPORT FICHIER", unsafe_allow_html=True)
    uploaded = st.file_uploader("Excel ou CSV", type=["xlsx","xls","csv"])
    if uploaded:
        if st.button("➕ Importer", use_container_width=True):
            with st.spinner("Import en cours..."):
                df_imp, err = load_uploaded_file(uploaded)
                if err:
                    st.error(f"❌ {err}")
                else:
                    df_imp, errs, warns = validate_and_clean(df_imp)
                    for e in errs: st.error(f"❌ {e}")
                    for w in warns: st.warning(f"⚠️ {w}")
                    if not errs:
                        n = import_df_to_db(df_imp)
                        st.success(f"✅ {n} lignes importées")
                        st.rerun()

    csv_template = """date_jour,ligne,code_machine,operateur,produit,quantite,rebuts,temps_arret,code_probleme,description_probleme
2026-04-21,Ligne A,M01,Jean,Comprimé 500mg,12500,150,45,E01,Défaut capteur
2026-04-22,Ligne B,MB02,Marie,Sirop 125mg/5mL,8200,98,30,P03,Problème thermique"""
    st.download_button("📎 Modèle CSV", csv_template, "modele.csv", "text/csv")

    st.markdown("---", unsafe_allow_html=True)
    st.markdown("##### ⚙️ PARAMÈTRES TRS", unsafe_allow_html=True)
    TO = st.number_input("Temps d'ouverture (min/j)", 60, 1440, 480, 30)
    CAD = st.number_input("Cadence nominale (u/min)", 1, 9999, 50, 5)
    Tc = 1.0 / max(0.001, CAD)
    st.markdown(f'<div class="ib" style="font-size:0.78rem;">Tc = {Tc:.4f} min/u &nbsp;|&nbsp; Max = {TO*CAD:,.0f} u</div>', unsafe_allow_html=True)

    st.markdown("---", unsafe_allow_html=True)
    st.markdown("##### 🚨 SEUILS", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    S_TRS   = c1.number_input("TRS min (%)", 0, 100, 60)
    S_DISPO = c2.number_input("Dispo min (%)", 0, 100, 70)
    S_ARRET = st.number_input("Arrêts max/j (min)", 0, 1440, 120)
    S_REBUT = st.number_input("Rebut max (%)", 0.0, 100.0, 3.0, 0.5)

    st.markdown("---", unsafe_allow_html=True)
    st.markdown("##### 🔍 SOURCE & FILTRES", unsafe_allow_html=True)
    source = st.radio("Source", ["🗄️ Base de données", "🔵 Données démo"], horizontal=True)

    if source == "🗄️ Base de données":
        df_raw = df_db.copy()
        src_label = f"🗄️ DB ({nb_db} enreg.)"
        if df_raw.empty:
            st.warning("Base vide — utilisez démo ou importez")
    else:
        @st.cache_data
        def load_demo():
            np.random.seed(42)
            dates = pd.date_range('2026-01-01','2026-04-20', freq='D')
            rows = []
            for d in dates:
                for _ in range(np.random.randint(4, 10)):
                    lg = np.random.choice(LIGNES)
                    mc = np.random.choice(MACHINES[:6])
                    cp = np.random.choice(list(CODES_PROB.keys()))
                    cat, desc, iso, dept = CODES_PROB[cp]
                    arr = np.random.randint(5, 90)
                    tf_ = max(1, 480 - arr)
                    q = max(0, int(np.random.uniform(0.80, 0.97) * 50 * tf_))
                    reb = int(q * np.random.uniform(0.005, 0.04)) if q > 0 else 0
                    rows.append({
                        'date_jour': d, 'semaine': d.isocalendar().week,
                        'ligne': lg, 'code_machine': mc,
                        'type_machine': np.random.choice(TYPES_MACH),
                        'operateur': np.random.choice(OPERATEURS),
                        'code_probleme': cp, 'categorie_panne': cat,
                        'categorie_iso': iso, 'departement_resp': dept,
                        'description_probleme': desc, 'temps_arret': arr,
                        'produit': np.random.choice(PRODUITS),
                        'quantite': q, 'rebuts': reb
                    })
            return pd.DataFrame(rows)
        df_raw = load_demo()
        src_label = "🔵 DÉMO"

    sd, ed = date.today(), date.today()
    df_filt = pd.DataFrame()

    if not df_raw.empty:
        df_raw['date_jour'] = pd.to_datetime(df_raw['date_jour'])
        mn_d = df_raw['date_jour'].min().date()
        mx_d = df_raw['date_jour'].max().date()
        peri = st.selectbox("Période", ["Tout","7 derniers jours","Ce mois","Trimestre","Personnalisé"])
        today_ = date.today()
        if peri == "7 derniers jours": sd, ed = mx_d - timedelta(6), mx_d
        elif peri == "Ce mois":        sd, ed = today_.replace(day=1), today_
        elif peri == "Trimestre":      sd, ed = today_ - timedelta(90), today_
        elif peri == "Personnalisé":
            cc1, cc2 = st.columns(2)
            sd = cc1.date_input("Début", mn_d, min_value=mn_d, max_value=mx_d)
            ed = cc2.date_input("Fin",   mx_d, min_value=mn_d, max_value=mx_d)
        else: sd, ed = mn_d, mx_d
        mask = (df_raw['date_jour'].dt.date >= sd) & (df_raw['date_jour'].dt.date <= ed)
        df_filt = df_raw[mask].copy()

        col1, col2 = st.columns(2)
        with col1:
            lo = sorted(df_filt['ligne'].unique())
            sl = st.multiselect("Lignes", lo, default=lo)
            df_filt = df_filt[df_filt['ligne'].isin(sl)]
            mo = sorted(df_filt['code_machine'].unique())
            sm = st.multiselect("Machines", mo, default=mo)
            df_filt = df_filt[df_filt['code_machine'].isin(sm)]
        with col2:
            oo = sorted(df_filt['operateur'].unique())
            so = st.multiselect("Opérateurs", oo, default=oo)
            df_filt = df_filt[df_filt['operateur'].isin(so)]
            po = sorted(df_filt['produit'].unique())
            sp = st.multiselect("Produits", po, default=po)
            df_filt = df_filt[df_filt['produit'].isin(sp)]

# ══════════════════════════════════════════════════════════════
# TABS
# ══════════════════════════════════════════════════════════════
tabs = st.tabs([
    "📊 TABLEAU DE BORD", "📈 VUE GLOBALE", "📉 ANALYSE TRS",
    "⛔ PANNES", "📦 PRODUCTION", "🔬 QUALITÉ", "🔧 MAINTENANCE",
    "🏷️ PAR PRODUIT", "👥 PAR OPÉRATEUR", "➕ SAISIE", "📋 BASE"
])

NO_DATA = '<div class="wb">⚠️ Aucune donnée. Utilisez <b>➕ SAISIE</b> ou importez un fichier.</div>'

# Calculs globaux si données
if not df_filt.empty:
    daily = compute_trs(df_filt, TO, CAD)
    kpis  = compute_kpis(df_filt, daily, TO, CAD)
    period_len = max(1, (ed - sd).days)
    prev_sd = sd - timedelta(days=period_len)
    prev_ed = sd - timedelta(days=1)
    df_prev = df_raw[(df_raw['date_jour'].dt.date >= prev_sd) & (df_raw['date_jour'].dt.date <= prev_ed)]
    kpis_prev = {}
    if not df_prev.empty:
        dp = compute_trs(df_prev, TO, CAD)
        kpis_prev = compute_kpis(df_prev, dp, TO, CAD)
    def delta(key):
        if not kpis_prev or key not in kpis_prev: return None
        d = kpis[key] - kpis_prev[key]
        if key in ['trs','dispo','perf','qual']: return f"{d*100:+.1f}pp"
        if key == 'taux_rebut': return f"{d:+.2f}%"
        return f"{d:+,.0f}"
    alertes = []
    if kpis['trs']   < S_TRS/100:   alertes.append(('CRIT', f"TRS {kpis['trs']*100:.1f}% < seuil {S_TRS}%"))
    if kpis['dispo'] < S_DISPO/100: alertes.append(('CRIT', f"Dispo {kpis['dispo']*100:.1f}% < seuil {S_DISPO}%"))
    if kpis['taux_rebut'] > S_REBUT: alertes.append(('WARN', f"Rebut {kpis['taux_rebut']:.2f}% > {S_REBUT}%"))
    ov = df_filt.groupby('date_jour')['temps_arret'].sum()
    if (ov > S_ARRET).any(): alertes.append(('WARN', f"{(ov>S_ARRET).sum()} jour(s) > {S_ARRET} min d'arrêts"))

    # HEADER PRINCIPAL
    nb_crit = sum(1 for a in alertes if a[0] == 'CRIT')
    nb_warn = sum(1 for a in alertes if a[0] == 'WARN')
    status_html = ""
    if nb_crit: status_html += f'<span class="badge-alert">⛔ {nb_crit} CRITIQUE(S)</span> '
    if nb_warn: status_html += f'<span class="badge-warn">⚠️ {nb_warn} AVERT.</span> '
    if not alertes: status_html = '<span class="badge-ok">✅ NOMINAL</span>'

    ct, cs = st.columns([4, 1])
    with ct:
        col_logo, col_titre = st.columns([1, 7])
        with col_logo:
            afficher_logo("main", 55)
        with col_titre:
            st.markdown(f'''<div>
                <span style="font-size:1.4rem;font-weight:700;color:#0f172a;">⚙️ SIMED — TRS / OEE DASHBOARD</span>
                <span style="font-size:0.65rem;color:#64748b;margin-left:12px;font-family:JetBrains Mono,monospace;">ISO 22400-2:2014 | v7.0</span>
            </div>
            <div style="font-size:0.82rem;color:#475569;">📅 {sd} → {ed} &nbsp;|&nbsp; {src_label} &nbsp;|&nbsp; {kpis["nb_jours"]} jours analysés</div>
            ''', unsafe_allow_html=True)
    with cs:
        st.markdown(f'<div style="text-align:right;margin-top:8px;">{status_html}</div>', unsafe_allow_html=True)
    st.markdown("---", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
# ONGLET 0 : TABLEAU DE BORD
# ══════════════════════════════════════════════════════════════
with tabs[0]:
    st.markdown('<div class="sh">📊 TABLEAU DE BORD TEMPS RÉEL</div>', unsafe_allow_html=True)
    if df_filt.empty:
        st.info("ℹ️ Aucune donnée. Importez des données ou activez le mode démo.")
    else:
        trs_v = kpis['trs'] * 100
        # JAUGE OEE premium
        fig_gauge = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=trs_v,
            title={'text': "OEE / TRS GLOBAL", 'font': {'size': 16, 'family': 'Space Grotesk', 'color': '#0f172a'}},
            delta={'reference': 80, 'increasing': {'color': "#10b981"}, 'decreasing': {'color': "#ef4444"}, 'font': {'size': 14}},
            number={'suffix': '%', 'font': {'size': 42, 'family': 'Space Grotesk', 'color': '#0f172a'}},
            gauge={
                'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': "#64748b", 'ticksuffix': '%'},
                'bar': {'color': C['trs'], 'thickness': 0.25},
                'bgcolor': "white",
                'borderwidth': 0,
                'steps': [
                    {'range': [0, 60],  'color': '#fef2f2'},
                    {'range': [60, 80], 'color': '#fefce8'},
                    {'range': [80, 100],'color': '#f0fdf4'},
                ],
                'threshold': {
                    'line': {'color': "#ef4444", 'width': 3},
                    'thickness': 0.8,
                    'value': S_TRS
                }
            }
        ))
        fig_gauge.update_layout(height=280, paper_bgcolor='#ffffff', font={'family': 'Space Grotesk, sans-serif'}, margin=dict(l=30, r=30, t=40, b=20))

        col_gauge, col_pills = st.columns([2, 3])
        with col_gauge:
            st.plotly_chart(fig_gauge, use_container_width=True)
        with col_pills:
            st.markdown("**Composantes OEE**", unsafe_allow_html=True)
            for label, key, color, icon in [
                ("Disponibilité", 'dispo', C['dispo'], "🟢"),
                ("Performance",   'perf',  C['perf'],  "🟡"),
                ("Qualité",       'qual',  C['qual'],  "🟣"),
            ]:
                val = kpis[key] * 100
                bar = int(val)
                st.markdown(f"""
                <div style="margin:10px 0;">
                    <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
                        <span style="font-size:0.85rem;">{icon} {label}</span>
                        <span style="font-weight:700;font-size:0.9rem;color:{color};">{val:.1f}%</span>
                    </div>
                    <div style="background:#e2e8f0;border-radius:8px;height:10px;">
                        <div style="background:{color};width:{bar}%;height:10px;border-radius:8px;transition:width 0.5s;"></div>
                    </div>
                </div>""", unsafe_allow_html=True)

        # KPI ROW
        st.markdown('<div class="sh">📐 INDICATEURS CLÉS</div>', unsafe_allow_html=True)
        k1, k2, k3, k4, k5, k6 = st.columns(6)
        k1.metric("🏭 Production", f"{kpis['total_produit']:,.0f} u")
        k2.metric("❌ Rebuts", f"{kpis['total_rebuts']:,.0f}", delta=f"{kpis['taux_rebut']:.2f}%")
        k3.metric("⏱️ Arrêts", f"{kpis['total_arret']:.0f} min")
        k4.metric("🔁 Incidents", f"{kpis['nb_incidents']}")
        k5.metric("⏳ MTBF", f"{kpis['mtbf']:.0f} min")
        k6.metric("🔧 MTTR", f"{kpis['mttr']:.1f} min")

        # WATERFALL OEE
        st.markdown('<div class="sh">⚖️ CASCADE DES PERTES OEE</div>', unsafe_allow_html=True)
        perte_d = kpis['perte_dispo']
        perte_p = kpis['perte_perf']
        perte_q = kpis['perte_qual']
        prod_nette = TO - perte_d - perte_p - perte_q
        fig_wf = go.Figure(go.Waterfall(
            orientation="v",
            measure=["absolute", "relative", "relative", "relative", "total"],
            x=["Temps ouverture", "Pertes Dispo", "Pertes Perf.", "Pertes Qualité", "Temps utile"],
            y=[TO, -perte_d, -perte_p, -perte_q, 0],
            connector={"line": {"color": "#e2e8f0"}},
            increasing={"marker": {"color": C['dispo']}},
            decreasing={"marker": {"color": C['rebut']}},
            totals={"marker": {"color": C['trs']}},
            text=[f"{TO:.0f}", f"-{perte_d:.0f}", f"-{perte_p:.0f}", f"-{perte_q:.0f}", f"{prod_nette:.0f}"],
            textposition="outside"
        ))
        fig_wf.update_layout(**PL, height=300, title="Cascade des pertes (min/jour moyen)")
        st.plotly_chart(fig_wf, use_container_width=True)

        # STATUT MACHINES
        st.markdown('<div class="sh">🖥️ STATUT DES MACHINES</div>', unsafe_allow_html=True)
        dernier_jour = df_filt['date_jour'].max()
        arrets_mach = df_filt[df_filt['date_jour'] == dernier_jour].groupby('code_machine').agg(
            total_arret=('temps_arret', 'sum'),
            nb_incidents=('temps_arret', lambda x: (x > 0).sum())
        )
        trs_mach = daily.groupby('code_machine')['trs'].mean()
        machines_uniques = sorted(df_filt['code_machine'].unique())
        cols_m = st.columns(min(len(machines_uniques), 5))
        for i, machine in enumerate(machines_uniques):
            with cols_m[i % 5]:
                arret = arrets_mach['total_arret'].get(machine, 0)
                trs_m = trs_mach.get(machine, 0) * 100
                if arret == 0:
                    statut, color, cls = "🟢 En marche", "#10b981", "machine-running"
                elif arret < 60:
                    statut, color, cls = "🟡 Arrêt partiel", "#f59e0b", "machine-partial"
                else:
                    statut, color, cls = "🔴 En arrêt", "#ef4444", "machine-stopped"
                st.markdown(f"""
                <div class="machine-card {cls}">
                    <div style="font-weight:700;font-size:1rem;margin-bottom:4px;">{machine}</div>
                    <div style="color:{color};font-size:0.82rem;font-weight:600;">{statut}</div>
                    <div style="color:#64748b;font-size:0.75rem;margin-top:6px;">TRS moy: <b>{trs_m:.1f}%</b></div>
                    <div style="color:#64748b;font-size:0.72rem;">Arrêt: {arret:.0f} min</div>
                </div>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
# ONGLET 1 : VUE GLOBALE
# ══════════════════════════════════════════════════════════════
with tabs[1]:
    if df_filt.empty:
        st.markdown(NO_DATA, unsafe_allow_html=True)
    else:
        for lvl, msg in alertes:
            st.markdown(f'<div class="{"ab" if lvl=="CRIT" else "wb"}">{"⛔" if lvl=="CRIT" else "⚠️"} <b>{lvl}</b> — {msg}</div>', unsafe_allow_html=True)

        st.markdown('<div class="sh">INDICATEURS TRS</div>', unsafe_allow_html=True)
        k1,k2,k3,k4 = st.columns(4)
        k1.metric("TRS GLOBAL",      f"{kpis['trs']*100:.1f}%",  delta(('trs')))
        k2.metric("DISPONIBILITÉ",   f"{kpis['dispo']*100:.1f}%", delta('dispo'))
        k3.metric("PERFORMANCE",     f"{kpis['perf']*100:.1f}%",  delta('perf'))
        k4.metric("QUALITÉ",         f"{kpis['qual']*100:.1f}%",  delta('qual'))

        st.markdown('<div class="sh">PRODUCTION & SIX SIGMA</div>', unsafe_allow_html=True)
        k1,k2,k3,k4,k5 = st.columns(5)
        k1.metric("PRODUCTION",    f"{kpis['total_produit']:,.0f}")
        k2.metric("REBUTS",        f"{kpis['total_rebuts']:,.0f}")
        k3.metric("TAUX REBUT",    f"{kpis['taux_rebut']:.2f}%")
        k4.metric("PROD/H",        f"{kpis['prod_horaire']:,.0f} u")
        k5.metric("NIVEAU SIGMA",  f"{kpis['sigma']:.2f} σ")

        # PRÉVISION
        st.markdown('<div class="sh">🔮 PRÉVISION TRS (7 jours)</div>', unsafe_allow_html=True)
        dj = daily.groupby('date_jour')[['trs','disponibilite','performance','qualite']].mean().reset_index().sort_values('date_jour')
        pred, model = forecast_trs(dj['trs'], 7)
        if pred is not None:
            future_dates = [dj['date_jour'].max() + timedelta(days=i+1) for i in range(7)]
            fig_fc = go.Figure()
            fig_fc.add_trace(go.Scatter(x=dj['date_jour'], y=dj['trs']*100, mode='lines+markers', name='Historique', line=dict(color=C['trs'], width=2)))
            fig_fc.add_trace(go.Scatter(
                x=future_dates, y=pred*100, mode='lines+markers', name='Prévision',
                line=dict(color='#f97316', dash='dot', width=2),
                marker=dict(symbol='diamond', size=7)
            ))
            fig_fc.add_hline(y=S_TRS, line_dash="dash", line_color="#ef4444", annotation_text=f"Seuil {S_TRS}%")
            fig_fc.update_layout(**PL, height=360, title="Projection TRS sur 7 jours")
            st.plotly_chart(fig_fc, use_container_width=True)
            tend = "📈 Hausse" if model.coef_[0] > 0 else "📉 Baisse"
            st.caption(f"Tendance : {tend} de {abs(model.coef_[0]*100):.2f}% par jour")
        else:
            st.info("Pas assez de données (≥3 jours requis).")

        # CLASSEMENT
        st.markdown('<div class="sh">🏆 CLASSEMENT MACHINES</div>', unsafe_allow_html=True)
        mt = daily.groupby('code_machine')['trs'].mean().sort_values(ascending=False).reset_index()
        col_b, col_w = st.columns(2)
        with col_b:
            st.markdown("**✅ Top 3 meilleures**", unsafe_allow_html=True)
            for _, r in mt.head(3).iterrows():
                col = "#10b981" if r['trs'] >= 0.8 else "#f59e0b"
                st.markdown(f"🏅 **{r['code_machine']}** — <span style='color:{col};font-weight:700;'>{r['trs']*100:.1f}%</span>", unsafe_allow_html=True)
        with col_w:
            st.markdown("**⚠️ À améliorer**", unsafe_allow_html=True)
            for _, r in mt.tail(3).iterrows():
                col = "#ef4444" if r['trs'] < 0.6 else "#f59e0b"
                st.markdown(f"⚡ **{r['code_machine']}** — <span style='color:{col};font-weight:700;'>{r['trs']*100:.1f}%</span>", unsafe_allow_html=True)

        # EXPORT
        st.markdown('<div class="sh">📥 EXPORT RAPPORT</div>', unsafe_allow_html=True)
        rapport_html = generer_rapport_html(kpis, dj, sd, ed, src_label)
        st.download_button("📄 Télécharger rapport HTML", rapport_html, "rapport_trs.html", "text/html")

# ══════════════════════════════════════════════════════════════
# ONGLET 2 : ANALYSE TRS
# ══════════════════════════════════════════════════════════════
with tabs[2]:
    if df_filt.empty:
        st.markdown(NO_DATA, unsafe_allow_html=True)
    else:
        # Évolution + MA7
        st.markdown('<div class="sh">ÉVOLUTION TRS + MOYENNE MOBILE 7j</div>', unsafe_allow_html=True)
        td = daily.groupby('date_jour')[['trs','disponibilite','performance','qualite']].mean().reset_index()
        td['MA7'] = td['trs'].rolling(7, min_periods=1).mean()
        fig_ev = go.Figure()
        fig_ev.add_trace(go.Scatter(x=td['date_jour'], y=td['trs']*100, mode='lines', name='TRS', line=dict(color=C['trs'], width=2.5), fill='tozeroy', fillcolor='rgba(59,130,246,0.07)'))
        fig_ev.add_trace(go.Scatter(x=td['date_jour'], y=td['MA7']*100, mode='lines', name='Moy. 7j', line=dict(color='#f97316', width=2, dash='dot')))
        fig_ev.add_trace(go.Scatter(x=td['date_jour'], y=td['disponibilite']*100, mode='lines', name='Dispo', line=dict(color=C['dispo'], width=1.5, dash='dash')))
        fig_ev.add_trace(go.Scatter(x=td['date_jour'], y=td['performance']*100,   mode='lines', name='Perf',  line=dict(color=C['perf'],  width=1.5, dash='dash')))
        fig_ev.add_trace(go.Scatter(x=td['date_jour'], y=td['qualite']*100,       mode='lines', name='Qual',  line=dict(color=C['qual'],  width=1.5, dash='dash')))
        fig_ev.add_hline(y=S_TRS, line_dash="dash", line_color="red", annotation_text=f"Seuil {S_TRS}%", annotation_position="bottom right")
        fig_ev.update_layout(**PL, height=380, title="TRS quotidien et composantes")
        st.plotly_chart(fig_ev, use_container_width=True)

        # HEATMAP hebdomadaire
        st.markdown('<div class="sh">🗓️ HEATMAP TRS PAR SEMAINE / MACHINE</div>', unsafe_allow_html=True)
        if 'semaine' not in df_filt.columns:
            df_filt['semaine'] = df_filt['date_jour'].dt.isocalendar().week.astype(int)
        hm_data = daily.copy()
        hm_data['semaine'] = hm_data['date_jour'].dt.isocalendar().week.astype(int)
        pivot_hm = hm_data.groupby(['semaine','code_machine'])['trs'].mean().reset_index()
        pivot_hm = pivot_hm.pivot(index='code_machine', columns='semaine', values='trs')
        fig_hm = px.imshow(
            pivot_hm * 100,
            labels=dict(x="Semaine", y="Machine", color="TRS (%)"),
            color_continuous_scale=[[0,'#fef2f2'],[0.5,'#fef9c3'],[1,'#dcfce7']],
            zmin=0, zmax=100,
            text_auto=".1f",
            aspect="auto"
        )
        fig_hm.update_layout(**PL, height=300, title="TRS (%) par semaine et par machine", coloraxis_colorbar=dict(title="TRS %"))
        st.plotly_chart(fig_hm, use_container_width=True)

        # TRS par machine
        st.markdown('<div class="sh">TRS PAR MACHINE</div>', unsafe_allow_html=True)
        tm = daily.groupby('code_machine')[['trs','disponibilite','performance','qualite']].mean().reset_index().sort_values('trs')
        fm = go.Figure()
        for col_, nm_, clr_ in [('disponibilite','Dispo',C['dispo']),('performance','Perf',C['perf']),('qualite','Qualité',C['qual'])]:
            fm.add_trace(go.Bar(y=tm['code_machine'], x=tm[col_]*100, name=nm_, orientation='h', marker_color=clr_, opacity=0.85))
        fm.add_trace(go.Scatter(y=tm['code_machine'], x=tm['trs']*100, mode='markers+text', name='TRS',
            marker=dict(symbol='diamond', size=12, color='#0f172a'),
            text=[f"{v*100:.1f}%" for v in tm['trs']], textposition='middle right'))
        fm.add_vline(x=S_TRS, line_dash="dash", line_color="red")
        fm.update_layout(**PL, height=350, barmode='group', title="Composantes TRS par machine")
        st.plotly_chart(fm, use_container_width=True)

# ══════════════════════════════════════════════════════════════
# ONGLET 3 : PANNES
# ══════════════════════════════════════════════════════════════
with tabs[3]:
    if df_filt.empty:
        st.markdown(NO_DATA, unsafe_allow_html=True)
    else:
        st.markdown('<div class="sh">PARETO DES PANNES</div>', unsafe_allow_html=True)
        pa = df_filt.groupby(['code_probleme','description_probleme','categorie_panne']).agg(
            duree_totale=('temps_arret','sum'), nb_occ=('temps_arret','count')
        ).reset_index().sort_values('duree_totale', ascending=False)
        pa['cumul'] = 100 * pa['duree_totale'].cumsum() / pa['duree_totale'].sum()

        fp = make_subplots(specs=[[{"secondary_y": True}]])
        fp.add_trace(go.Bar(x=pa['code_probleme'], y=pa['duree_totale'], name="Durée (min)", marker_color=C['dispo'], text=pa['nb_occ'].apply(lambda x: f"{x} occ."), textposition='outside'), secondary_y=False)
        fp.add_trace(go.Scatter(x=pa['code_probleme'], y=pa['cumul'], mode='lines+markers', name="Cumul %", line=dict(color=C['rebut'], width=2)), secondary_y=True)
        fp.add_hline(y=80, line_dash="dot", line_color=C['alert'], secondary_y=True, annotation_text="80%")
        fp.update_layout(**PL, height=400, title="Pareto des arrêts (Durée + Cumul)")
        fp.update_yaxes(title_text="Minutes", secondary_y=False)
        fp.update_yaxes(title_text="Cumul (%)", range=[0,110], ticksuffix="%", secondary_y=True)
        st.plotly_chart(fp, use_container_width=True)

        # Répartition par catégorie
        st.markdown('<div class="sh">RÉPARTITION PAR CATÉGORIE</div>', unsafe_allow_html=True)
        cat_data = df_filt.groupby('categorie_panne')['temps_arret'].sum().reset_index()
        col_pie, col_bar = st.columns(2)
        with col_pie:
            fig_pie = go.Figure(go.Pie(labels=cat_data['categorie_panne'], values=cat_data['temps_arret'],
                hole=0.5, marker_colors=[C['trs'],C['dispo'],C['perf'],C['qual'],C['rebut'],C['alert']]))
            fig_pie.update_layout(**PL, height=280, title="Par catégorie ISO", showlegend=True)
            st.plotly_chart(fig_pie, use_container_width=True)
        with col_bar:
            dept_data = df_filt.groupby('departement_resp')['temps_arret'].sum().sort_values().reset_index()
            fig_dept = go.Figure(go.Bar(y=dept_data['departement_resp'], x=dept_data['temps_arret'],
                orientation='h', marker_color=C['alert']))
            fig_dept.update_layout(**PL, height=280, title="Par département")
            st.plotly_chart(fig_dept, use_container_width=True)

# ══════════════════════════════════════════════════════════════
# ONGLET 4 : PRODUCTION
# ══════════════════════════════════════════════════════════════
with tabs[4]:
    if df_filt.empty:
        st.markdown(NO_DATA, unsafe_allow_html=True)
    else:
        pj = df_filt.groupby('date_jour').agg(quantite=('quantite','sum'), rebuts=('rebuts','sum')).reset_index()
        pj['bonne'] = pj['quantite'] - pj['rebuts']
        pj['taux_rebut'] = (pj['rebuts'] / pj['quantite'] * 100).fillna(0)

        fig_prod = go.Figure()
        fig_prod.add_trace(go.Bar(x=pj['date_jour'], y=pj['bonne'],   name="Bonne production", marker_color=C['dispo']))
        fig_prod.add_trace(go.Bar(x=pj['date_jour'], y=pj['rebuts'],  name="Rebuts",           marker_color=C['rebut']))
        fig_prod.add_hline(y=TO*CAD, line_dash="dot", line_color="gray", annotation_text="Capacité max")
        fig_prod.update_layout(**PL, barmode='stack', height=360, title="Production quotidienne (Bonne + Rebuts)")
        st.plotly_chart(fig_prod, use_container_width=True)

        # Production par ligne
        prod_ligne = df_filt.groupby(['date_jour','ligne'])['quantite'].sum().reset_index()
        fig_lig = px.area(prod_ligne, x='date_jour', y='quantite', color='ligne',
            color_discrete_map={'Ligne A': C['trs'], 'Ligne B': C['dispo'], 'Ligne C': C['perf']},
            title="Production par ligne")
        fig_lig.update_layout(**PL, height=320)
        st.plotly_chart(fig_lig, use_container_width=True)

# ══════════════════════════════════════════════════════════════
# ONGLET 5 : QUALITÉ
# ══════════════════════════════════════════════════════════════
with tabs[5]:
    if df_filt.empty:
        st.markdown(NO_DATA, unsafe_allow_html=True)
    else:
        cs1, cs2 = st.columns([1, 2])
        with cs1:
            sigma_color = "#10b981" if kpis['sigma'] >= 4 else ("#f59e0b" if kpis['sigma'] >= 3 else "#ef4444")
            st.markdown(f"""
            <div style="background:white;border-radius:16px;padding:2rem;text-align:center;border:1px solid #e2e8f0;border-top:4px solid {sigma_color};">
                <div style="font-size:0.7rem;color:#64748b;text-transform:uppercase;letter-spacing:0.1em;">Niveau Sigma</div>
                <div style="font-size:3.5rem;font-weight:700;color:{sigma_color};line-height:1.1;">{kpis['sigma']:.2f}σ</div>
                <div style="color:#64748b;font-size:0.85rem;margin-top:8px;">DPMO = {kpis['dpmo']:,.0f}</div>
                <div style="color:#64748b;font-size:0.8rem;">Rebuts : {kpis['total_rebuts']:,.0f}</div>
                <div style="color:#64748b;font-size:0.8rem;">Taux : {kpis['taux_rebut']:.2f}%</div>
            </div>""", unsafe_allow_html=True)
        with cs2:
            trj = df_filt.groupby('date_jour').agg(q=('quantite','sum'), r=('rebuts','sum')).reset_index()
            trj['taux'] = (trj['r'] / trj['q'] * 100).fillna(0)
            fig_q = go.Figure()
            fig_q.add_trace(go.Scatter(x=trj['date_jour'], y=trj['taux'], mode='lines', fill='tozeroy',
                line=dict(color=C['rebut'], width=2), fillcolor='rgba(239,68,68,0.1)', name='Taux rebut'))
            fig_q.add_hline(y=S_REBUT, line_dash="dash", line_color='#f97316', annotation_text=f"Seuil {S_REBUT}%")
            fig_q.update_layout(**PL, height=280, title="Taux de rebut journalier (%)", yaxis_title="%")
            st.plotly_chart(fig_q, use_container_width=True)

        # Rebuts par produit
        st.markdown('<div class="sh">REBUTS PAR PRODUIT</div>', unsafe_allow_html=True)
        rp = df_filt.groupby('produit').agg(total_rebuts=('rebuts','sum'), total_prod=('quantite','sum')).reset_index()
        rp['taux'] = (rp['total_rebuts'] / rp['total_prod'] * 100).fillna(0)
        fig_rp = go.Figure(go.Bar(x=rp['produit'], y=rp['taux'], marker_color=[
            C['rebut'] if t > S_REBUT else C['dispo'] for t in rp['taux']
        ], text=rp['taux'].apply(lambda x: f"{x:.2f}%"), textposition='outside'))
        fig_rp.add_hline(y=S_REBUT, line_dash="dash", line_color='orange')
        fig_rp.update_layout(**PL, height=320, title="Taux de rebut par produit (%)")
        st.plotly_chart(fig_rp, use_container_width=True)

# ══════════════════════════════════════════════════════════════
# ONGLET 6 : MAINTENANCE
# ══════════════════════════════════════════════════════════════
with tabs[6]:
    if df_filt.empty:
        st.markdown(NO_DATA, unsafe_allow_html=True)
    else:
        mn = df_filt[df_filt['temps_arret'] > 0].groupby('code_machine').agg(
            nb_pannes=('temps_arret','count'),
            temps_total=('temps_arret','sum')
        ).reset_index()
        mn['MTBF'] = (kpis['nb_jours'] * TO - mn['temps_total']) / mn['nb_pannes']
        mn['MTTR'] = mn['temps_total'] / mn['nb_pannes']
        mn['Disponibilité'] = (1 - mn['temps_total'] / (kpis['nb_jours'] * TO)).clip(0, 1) * 100
        mn = mn.sort_values('MTBF', ascending=False)

        # KPIs maintenance
        col1, col2, col3 = st.columns(3)
        col1.metric("MTBF Global", f"{kpis['mtbf']:.1f} min", help="Mean Time Between Failures")
        col2.metric("MTTR Global", f"{kpis['mttr']:.1f} min", help="Mean Time To Repair")
        col3.metric("Taux de panne", f"{kpis['taux_panne']:.1f} /jour")

        fig_mm = make_subplots(rows=1, cols=2, subplot_titles=("MTBF par machine (min)", "MTTR par machine (min)"))
        fig_mm.add_trace(go.Bar(y=mn['code_machine'], x=mn['MTBF'], orientation='h', marker_color=C['dispo'], name='MTBF'), row=1, col=1)
        fig_mm.add_trace(go.Bar(y=mn['code_machine'], x=mn['MTTR'], orientation='h', marker_color=C['alert'], name='MTTR'), row=1, col=2)
        fig_mm.update_layout(**PL, height=360, showlegend=False, title="Indicateurs de maintenabilité")
        st.plotly_chart(fig_mm, use_container_width=True)

        # Évolution arrêts dans le temps
        st.markdown('<div class="sh">📅 ÉVOLUTION DES ARRÊTS</div>', unsafe_allow_html=True)
        arr_time = df_filt.groupby(['date_jour','categorie_panne'])['temps_arret'].sum().reset_index()
        fig_arr = px.bar(arr_time, x='date_jour', y='temps_arret', color='categorie_panne',
            title="Durée d'arrêts par catégorie",
            color_discrete_sequence=[C['trs'],C['dispo'],C['perf'],C['qual'],C['rebut'],C['alert']])
        fig_arr.update_layout(**PL, height=320)
        st.plotly_chart(fig_arr, use_container_width=True)

# ══════════════════════════════════════════════════════════════
# ONGLET 7 : PAR PRODUIT
# ══════════════════════════════════════════════════════════════
with tabs[7]:
    if df_filt.empty:
        st.markdown(NO_DATA, unsafe_allow_html=True)
    else:
        st.markdown('<div class="sh">TRS PAR PRODUIT</div>', unsafe_allow_html=True)
        pt = daily.groupby('produit')['trs'].mean().sort_values(ascending=False).reset_index()
        fig_pt = go.Figure(go.Bar(
            x=pt['produit'], y=pt['trs']*100,
            marker_color=[C['dispo'] if v >= S_TRS/100 else C['rebut'] for v in pt['trs']],
            text=[f"{v*100:.1f}%" for v in pt['trs']], textposition='outside'
        ))
        fig_pt.add_hline(y=S_TRS, line_dash="dash", line_color="red", annotation_text=f"Seuil {S_TRS}%")
        fig_pt.update_layout(**PL, height=380, title="TRS moyen par produit (%)")
        st.plotly_chart(fig_pt, use_container_width=True)

        st.markdown('<div class="sh">HEATMAP PRODUIT × DATE</div>', unsafe_allow_html=True)
        prod_d = daily.groupby(['date_jour','produit'])['trs'].mean().reset_index()
        pivot_p = prod_d.pivot(index='produit', columns='date_jour', values='trs')
        fig_hp = px.imshow(pivot_p * 100, color_continuous_scale=[[0,'#fef2f2'],[0.6,'#fef9c3'],[1,'#dcfce7']],
            zmin=0, zmax=100, aspect='auto', text_auto='.0f')
        fig_hp.update_layout(**PL, height=300, title="TRS (%) par produit et par jour")
        st.plotly_chart(fig_hp, use_container_width=True)

# ══════════════════════════════════════════════════════════════
# ONGLET 8 : PAR OPÉRATEUR
# ══════════════════════════════════════════════════════════════
with tabs[8]:
    if df_filt.empty:
        st.markdown(NO_DATA, unsafe_allow_html=True)
    else:
        st.markdown('<div class="sh">TRS PAR OPÉRATEUR</div>', unsafe_allow_html=True)
        ot = daily.groupby('operateur')['trs'].mean().sort_values(ascending=False).reset_index()
        fig_ot = go.Figure(go.Bar(
            x=ot['operateur'], y=ot['trs']*100,
            marker_color=[C['dispo'] if v >= S_TRS/100 else C['rebut'] for v in ot['trs']],
            text=[f"{v*100:.1f}%" for v in ot['trs']], textposition='outside'
        ))
        fig_ot.add_hline(y=S_TRS, line_dash="dash", line_color="red")
        fig_ot.update_layout(**PL, height=380, title="TRS moyen par opérateur (%)")
        st.plotly_chart(fig_ot, use_container_width=True)

        # Radar par opérateur
        st.markdown('<div class="sh">🕸️ RADAR MULTI-OPÉRATEURS</div>', unsafe_allow_html=True)
        op_detail = daily.groupby('operateur')[['trs','disponibilite','performance','qualite']].mean().reset_index()
        fig_rad = go.Figure()
        categories = ['TRS','Disponibilité','Performance','Qualité','TRS']
        colors = [C['trs'],C['dispo'],C['perf'],C['qual'],C['alert']]
        for i, (_, row) in enumerate(op_detail.iterrows()):
            vals = [row['trs']*100, row['disponibilite']*100, row['performance']*100, row['qualite']*100, row['trs']*100]
            fig_rad.add_trace(go.Scatterpolar(r=vals, theta=categories, name=row['operateur'], fill='toself', opacity=0.6))
        fig_rad.update_layout(polar=dict(radialaxis=dict(range=[0,100])), height=400, paper_bgcolor='white', title="Radar des compétences TRS")
        st.plotly_chart(fig_rad, use_container_width=True)

# ══════════════════════════════════════════════════════════════
# ONGLET 9 : SAISIE
# ══════════════════════════════════════════════════════════════
with tabs[9]:
    st.markdown('<div class="sh">SAISIE D\'UN NOUVEL ENREGISTREMENT</div>', unsafe_allow_html=True)
    with st.form("saisie_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            date_s    = st.date_input("📅 Date", value=date.today())
            ligne_s   = st.selectbox("🏭 Ligne", LIGNES)
            machine_s = st.selectbox("⚙️ Machine", MACHINES)
            oper_s    = st.selectbox("👷 Opérateur", OPERATEURS)
            prod_s    = st.selectbox("📦 Produit", PRODUITS)
        with col2:
            qte_s    = st.number_input("📊 Quantité produite", min_value=0, step=100)
            rebut_s  = st.number_input("❌ Rebuts", min_value=0, step=10)
            arret_s  = st.number_input("⏱️ Temps d'arrêt (min)", min_value=0, step=5)
            code_p   = st.selectbox("⛔ Code panne", list(CODES_PROB.keys()))
            desc_p   = st.text_input("📝 Description libre")
        submitted = st.form_submit_button("💾 Enregistrer", type="primary", use_container_width=True)
        if submitted:
            if rebut_s > qte_s:
                st.error("❌ Les rebuts ne peuvent pas dépasser la quantité produite.")
            else:
                cat, desc, iso, dept = CODES_PROB[code_p]
                insert_row({
                    'date_jour': date_s.strftime('%Y-%m-%d'),
                    'semaine': date_s.isocalendar()[1],
                    'ligne': ligne_s, 'code_machine': machine_s,
                    'type_machine': 'N/A', 'operateur': oper_s,
                    'code_probleme': code_p, 'categorie_panne': cat,
                    'categorie_iso': iso, 'departement_resp': dept,
                    'description_probleme': desc_p or desc,
                    'temps_arret': arret_s, 'produit': prod_s,
                    'quantite': qte_s, 'rebuts': rebut_s,
                })
                st.success("✅ Enregistrement ajouté avec succès !")
                st.rerun()

# ══════════════════════════════════════════════════════════════
# ONGLET 10 : BASE
# ══════════════════════════════════════════════════════════════
with tabs[10]:
    st.markdown('<div class="sh">CONTENU DE LA BASE DE DONNÉES</div>', unsafe_allow_html=True)
    df_view = load_db()
    if df_view.empty:
        st.info("📭 La base est vide.")
    else:
        # Recherche
        search = st.text_input("🔍 Rechercher", placeholder="Machine, opérateur, produit...")
        if search:
            mask_s = df_view.astype(str).apply(lambda row: row.str.contains(search, case=False)).any(axis=1)
            df_view = df_view[mask_s]
        st.markdown(f"**{len(df_view):,} enregistrements affichés**", unsafe_allow_html=True)
        st.dataframe(df_view, use_container_width=True, height=400)

        col_d1, col_d2 = st.columns([1, 3])
        with col_d1:
            if st.button("🗑️ Vider la base", type="secondary"):
                with get_conn() as conn:
                    conn.execute("DELETE FROM production")
                st.success("✅ Base vidée")
                st.rerun()

# ══════════════════════════════════════════════════════════════
# FOOTER
# ══════════════════════════════════════════════════════════════
st.markdown("---", unsafe_allow_html=True)
st.markdown(
    f'<div style="text-align:center;font-size:0.68rem;color:#94a3b8;font-family:JetBrains Mono,monospace;">'
    f'SIMED TRS DASHBOARD v7.0 &nbsp;|&nbsp; ISO 22400-2:2014 &nbsp;|&nbsp; '
    f'{datetime.now().strftime("%Y-%m-%d %H:%M")}'
    f'</div>',
    unsafe_allow_html=True
)
