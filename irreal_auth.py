import re
from pathlib import Path

import streamlit as st
from passlib.hash import bcrypt
from supabase import create_client


def get_secret(name, default=None):
    try:
        return st.secrets.get(name, default)
    except Exception:
        return default


@st.cache_resource
def supabase_client():
    url = get_secret("SUPABASE_URL")
    key = get_secret("SUPABASE_SERVICE_ROLE_KEY")

    if not url or not key:
        return None

    return create_client(url, key)


def normalize_text(value: str) -> str:
    value = (value or "").strip().lower()
    value = re.sub(r"\s+", " ", value)
    return value


def _bcrypt_safe_password(password: str) -> str:
    password = password or ""
    encoded = password.encode("utf-8")[:72]
    return encoded.decode("utf-8", errors="ignore")


def hash_password(password: str) -> str:
    return bcrypt.hash(_bcrypt_safe_password(password))


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.verify(_bcrypt_safe_password(password), hashed)
    except Exception:
        return False


def bootstrap_superadmin():
    sb = supabase_client()

    if sb is None:
        return

    result = (
        sb.table("app_users")
        .select("id")
        .eq("role", "super_admin")
        .limit(1)
        .execute()
    )

    if result.data:
        return

    full_name = get_secret("BOOTSTRAP_ADMIN_FULL_NAME")
    email = get_secret("BOOTSTRAP_ADMIN_EMAIL")
    password = get_secret("BOOTSTRAP_ADMIN_PASSWORD")

    if not full_name or not password:
        return

    sb.table("app_users").insert({
        "full_name": full_name.strip(),
        "email": (email or "").strip() or None,
        "role": "super_admin",
        "password_hash": hash_password(password),
        "active": True,
    }).execute()


def authenticate(identifier: str, password: str, role: str | None = None):
    sb = supabase_client()

    if sb is None:
        return None

    identifier_norm = normalize_text(identifier)

    def run_query(field: str):
        query = (
            sb.table("app_users")
            .select("*")
            .eq("active", True)
        )
        if role and role != "Todos":
            query = query.eq("role", role)
        return query.ilike(field, identifier_norm).limit(5).execute().data or []

    if "@" in identifier_norm:
        users = run_query("email")
    else:
        users = run_query("full_name")
        if not users:
            try:
                users = run_query("ra")
            except Exception:
                users = []

    for user in users:
        if verify_password(password, user.get("password_hash", "")):
            return user

    return None


def apply_login_style():
    st.markdown("""
    <style>
    .stApp {
        background:
            radial-gradient(circle at top left, rgba(255, 199, 44, 0.22) 0%, transparent 30%),
            radial-gradient(circle at bottom right, rgba(0, 255, 180, 0.20) 0%, transparent 34%),
            linear-gradient(135deg, #160B2E 0%, #0B1020 52%, #05070D 100%);
        color: #F8FAFC;
    }

    .block-container {
        padding-top: 1.0rem;
        padding-bottom: 2rem;
        max-width: 980px;
    }

    div[data-testid="stImage"] img {
        border-radius: 24px;
        box-shadow: 0 0 36px rgba(255, 199, 44, 0.30);
        border: 1px solid rgba(255, 255, 255, 0.16);
    }

    div[data-testid="stForm"] {
        background: rgba(15, 23, 42, 0.88);
        border: 1px solid rgba(0, 255, 180, 0.28);
        border-radius: 18px;
        padding: 1.2rem;
        box-shadow: 0 12px 35px rgba(0, 0, 0, 0.35);
    }

    div[data-testid="stFormSubmitButton"] button,
    div.stButton > button,
    button[kind="primary"],
    button[kind="secondary"] {
        background: linear-gradient(135deg, #16A34A 0%, #22C55E 55%, #86EFAC 100%) !important;
        color: #04130A !important;
        font-weight: 800 !important;
        border: 1px solid rgba(134, 239, 172, 0.75) !important;
        border-radius: 12px !important;
        min-height: 42px !important;
        box-shadow: 0 0 18px rgba(34, 197, 94, 0.35) !important;
    }

    div[data-testid="stFormSubmitButton"] button:hover,
    div.stButton > button:hover {
        background: linear-gradient(135deg, #22C55E 0%, #86EFAC 100%) !important;
        color: #020617 !important;
        border-color: #BBF7D0 !important;
    }



    input,
    textarea,
    [data-baseweb="input"] input,
    [data-baseweb="textarea"] textarea,
    [data-baseweb="select"] > div,
    [data-baseweb="base-input"] {
        background-color: #111827 !important;
        color: #F8FAFC !important;
        -webkit-text-fill-color: #F8FAFC !important;
        border-color: rgba(148, 163, 184, 0.45) !important;
        caret-color: #22C55E !important;
    }

    input::placeholder,
    textarea::placeholder,
    [data-baseweb="input"] input::placeholder,
    [data-baseweb="textarea"] textarea::placeholder {
        color: #CBD5E1 !important;
        opacity: 0.85 !important;
        -webkit-text-fill-color: #CBD5E1 !important;
    }

    [data-baseweb="select"] span,
    [data-baseweb="select"] div {
        color: #F8FAFC !important;
    }

    .irreal-login-title {
        text-align: center;
        font-size: 1.45rem;
        font-weight: 800;
        margin-top: 0.8rem;
        margin-bottom: 0.15rem;
        color: #FFFFFF;
        text-shadow: 0 2px 10px rgba(0, 0, 0, 0.45);
    }

    .irreal-login-subtitle {
        text-align: center;
        font-size: 1rem;
        color: #A7F3D0;
        margin-bottom: 1rem;
        font-weight: 600;
    }

    label, p, span {
        color: #F8FAFC;
    }
    </style>
    """, unsafe_allow_html=True)


def get_splash_path():
    base = Path(__file__).resolve().parent

    candidates = [
        base / "assets" / "irreal_splash_professora.png",
        base / "assets" / "irreal_splash_professora.jpg",
        base / "assets" / "irreal_splash_home.png",
        base / "assets" / "irreal_splash.png",
    ]

    for path in candidates:
        if path.exists():
            return path

    return None


def require_login():
    if "user" not in st.session_state:
        st.session_state["user"] = None

    if st.session_state["user"]:
        return st.session_state["user"]

    apply_login_style()

    splash_path = get_splash_path()

    if splash_path:
        st.image(str(splash_path), use_container_width=True)

    st.markdown(
        '<div class="irreal-login-title">Acesso ao IRREAL App</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="irreal-login-subtitle">Entre com seu perfil para acessar missões, desafios, IRREAIS e entregáveis.</div>',
        unsafe_allow_html=True
    )

    sb = supabase_client()

    if sb is None:
        st.error("Configuração incompleta. Defina SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY em Secrets.")
        st.stop()

    bootstrap_superadmin()

    with st.form("login_form"):
        role = st.selectbox(
            "Perfil",
            ["Todos", "student", "professor", "super_admin"],
            format_func=lambda x: {
                "Todos": "Detectar automaticamente",
                "student": "Aluno",
                "professor": "Professor",
                "super_admin": "Controle geral",
            }[x],
        )

        identifier = st.text_input("Nome completo, e-mail ou RA")
        password = st.text_input("Senha", type="password")

        submitted = st.form_submit_button("Entrar")

    if submitted:
        user = authenticate(identifier, password, role)

        if user:
            st.session_state["user"] = user
            st.rerun()
        else:
            st.error("Acesso negado. Confira nome/e-mail, senha e perfil.")

    st.stop()


def logout_button():
    user = st.session_state.get("user")

    if not user:
        return

    with st.sidebar:
        st.caption(f"Usuário: {user['full_name']}")
        st.caption(f"Perfil: {user['role']}")

        if st.button("Sair"):
            st.session_state.clear()
            st.rerun()


def is_super_admin(user):
    return bool(user and user.get("role") == "super_admin")


def is_professor(user):
    return bool(user and user.get("role") == "professor")


def is_student(user):
    return bool(user and user.get("role") == "student")


