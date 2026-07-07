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

def hash_password(password: str) -> str:
    return bcrypt.hash(password)

def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.verify(password, hashed)
    except Exception:
        return False

def bootstrap_superadmin():
    sb = supabase_client()
    if sb is None:
        return

    result = sb.table("app_users").select("id").eq("role", "super_admin").limit(1).execute()
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
    query = sb.table("app_users").select("*").eq("active", True)

    if "@" in identifier_norm:
        query = query.ilike("email", identifier_norm)
    else:
        query = query.ilike("full_name", identifier_norm)

    if role and role != "Todos":
        query = query.eq("role", role)

    res = query.limit(5).execute()
    users = res.data or []

    for user in users:
        if verify_password(password, user.get("password_hash", "")):
            return user

    return None

def require_login():
    if "user" not in st.session_state:
        st.session_state["user"] = None

    if st.session_state["user"]:
        return st.session_state["user"]

    # Tela inicial / splash visual do aplicativo
    splash_path = Path(__file__).resolve().parent / "assets" / "irreal_splash_home.png"

    st.markdown("""
    <style>
    .block-container {
        padding-top: 1.0rem;
        padding-bottom: 2rem;
        max-width: 980px;
    }
    div[data-testid="stImage"] img {
        border-radius: 22px;
        box-shadow: 0 0 32px rgba(0, 255, 180, 0.22);
    }
    .irreal-login-title {
        text-align: center;
        font-size: 1.3rem;
        font-weight: 700;
        margin-top: 0.7rem;
        margin-bottom: 0.1rem;
        color: #E5F9FF;
    }
    .irreal-login-subtitle {
        text-align: center;
        font-size: 0.95rem;
        color: #A7F3D0;
        margin-bottom: 1rem;
    }
    </style>
    """, unsafe_allow_html=True)

    if splash_path.exists():
        st.image(str(splash_path), use_container_width=True)

    st.markdown('<div class="irreal-login-title">Acesso ao IRREAL App</div>', unsafe_allow_html=True)
    st.markdown('<div class="irreal-login-subtitle">Entre com seu perfil para acessar missões, desafios, IRREAIS e entregáveis.</div>', unsafe_allow_html=True)

    sb = supabase_client()
    if sb is None:
        st.error("Configuração incompleta. Defina SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY em Secrets.")
        st.stop()

    bootstrap_superadmin()

    with st.form("login_form"):
        role = st.selectbox("Perfil", ["Todos", "student", "professor", "super_admin"], format_func=lambda x: {
            "Todos": "Detectar automaticamente",
            "student": "Aluno",
            "professor": "Professor",
            "super_admin": "Controle geral"
        }[x])
        identifier = st.text_input("Nome completo ou e-mail")
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
    return user and user.get("role") == "super_admin"

def is_professor(user):
    return user and user.get("role") == "professor"

def is_student(user):
    return user and user.get("role") == "student"
