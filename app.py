import streamlit as st
import pandas as pd
from datetime import date, datetime
from urllib.parse import quote
from irreal_auth import (
    require_login,
    logout_button,
    is_super_admin,
    is_professor,
    is_student,
    hash_password,
    supabase_client,
)
from data_service import (
    get_rows,
    insert_row,
    update_row,
    deactivate_user,
    create_user,
    balance_for_student,
    get_professor_classes,
    get_student_classes,
    challenge_multiplier,
    difficulty_label,
    type_label,
    create_challenge_event,
)
from email_service import send_deliverable_email

st.set_page_config(page_title="IRREAL App Cloud V8.1", page_icon="🎮", layout="wide")


def get_query_param(name: str) -> str:
    """Lê parâmetro da URL no Streamlit Cloud."""
    try:
        value = st.query_params.get(name, "")
    except Exception:
        return ""
    if isinstance(value, list):
        return value[0] if value else ""
    return value or ""


def apply_public_registration_style():
    st.markdown("""
    <style>
    .stApp {
        background:
            radial-gradient(circle at top left, rgba(255, 199, 44, 0.24) 0%, transparent 30%),
            radial-gradient(circle at bottom right, rgba(0, 255, 180, 0.22) 0%, transparent 34%),
            linear-gradient(135deg, #160B2E 0%, #0B1020 52%, #031B1B 100%);
        color: #F8FAFC;
    }
    .block-container { max-width: 860px; padding-top: 2rem; }
    div[data-testid="stForm"] {
        background: rgba(15, 23, 42, 0.90);
        border: 1px solid rgba(0, 255, 180, 0.30);
        border-radius: 18px;
        padding: 1.2rem;
        box-shadow: 0 12px 35px rgba(0, 0, 0, 0.36);
    }
    div.stButton > button,
    div[data-testid="stFormSubmitButton"] button {
        background: linear-gradient(135deg, #16A34A 0%, #22C55E 55%, #86EFAC 100%) !important;
        color: #04130A !important;
        font-weight: 800 !important;
        border: 1px solid rgba(134, 239, 172, 0.75) !important;
        border-radius: 12px !important;
        min-height: 42px !important;
        box-shadow: 0 0 18px rgba(34, 197, 94, 0.35) !important;
    }


    /* Correção de contraste para campos digitáveis no desktop e no celular */
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

    div[data-testid="stTextInput"] input:focus,
    div[data-testid="stTextArea"] textarea:focus,
    div[data-testid="stNumberInput"] input:focus {
        border: 1px solid #22C55E !important;
        box-shadow: 0 0 0 1px rgba(34, 197, 94, 0.75) !important;
    }

    h1, h2, h3, label, p, span { color: #F8FAFC; }
    </style>
    """, unsafe_allow_html=True)


def render_public_student_registration():
    """Cadastro público de aluno por link da turma: nome completo + RA."""
    apply_public_registration_style()
    st.title("🎮 Cadastro de aluno — IRREAL App")

    class_code = (
        get_query_param("cadastro_turma")
        or get_query_param("turma")
        or get_query_param("class_code")
    ).strip()

    if not class_code:
        st.error("Link de cadastro inválido. Peça ao professor o link correto da turma.")
        st.stop()

    sb_public = supabase_client()
    if sb_public is None:
        st.error("Configuração incompleta do Supabase. Avise o professor.")
        st.stop()

    try:
        class_rows = (
            sb_public.table("classes")
            .select("id, name, shift, class_code, active, professor_id, courses(name), app_users(full_name, email)")
            .eq("class_code", class_code)
            .eq("active", True)
            .limit(1)
            .execute()
            .data
            or []
        )
    except Exception as e:
        st.error(f"Não foi possível localizar a turma. Erro: {e}")
        st.stop()

    if not class_rows:
        st.error("Turma não encontrada ou inativa. Confira o link enviado pelo professor.")
        st.stop()

    cls = class_rows[0]
    course = cls.get("courses") or {}
    professor = cls.get("app_users") or {}

    st.info(
        f"Turma: {cls.get('name')} | Turno: {cls.get('shift')} | "
        f"Curso: {course.get('name') or '-'} | Professor: {professor.get('full_name') or '-'}"
    )

    with st.form("public_student_registration_form"):
        full_name = st.text_input("Nome completo")
        ra = st.text_input("RA / Registro acadêmico")
        email = st.text_input("E-mail [opcional]")
        submitted = st.form_submit_button("Cadastrar meu acesso")

    if submitted:
        full_name = (full_name or "").strip()
        ra = (ra or "").strip()
        email = (email or "").strip() or None

        if not full_name or not ra:
            st.error("Nome completo e RA são obrigatórios.")
            st.stop()

        try:
            existing = (
                sb_public.table("app_users")
                .select("*")
                .eq("ra", ra)
                .limit(1)
                .execute()
                .data
                or []
            )
        except Exception as e:
            st.error("A coluna RA ainda não existe no banco. Execute a migration V7 no Supabase.")
            st.caption(str(e))
            st.stop()

        if existing:
            student = existing[0]
            if student.get("role") != "student":
                st.error("Este RA já está vinculado a outro tipo de usuário. Avise o professor.")
                st.stop()
            update_payload = {"full_name": full_name, "active": True}
            if email:
                update_payload["email"] = email
            sb_public.table("app_users").update(update_payload).eq("id", student["id"]).execute()
            student_id = student["id"]
        else:
            created = (
                sb_public.table("app_users")
                .insert({
                    "full_name": full_name,
                    "email": email,
                    "ra": ra,
                    "role": "student",
                    "password_hash": hash_password(ra),
                    "active": True,
                })
                .execute()
                .data
                or []
            )
            student_id = created[0]["id"]

        enrollment = (
            sb_public.table("enrollments")
            .select("id")
            .eq("class_id", cls["id"])
            .eq("student_id", student_id)
            .limit(1)
            .execute()
            .data
            or []
        )

        if enrollment:
            sb_public.table("enrollments").update({"active": True}).eq("id", enrollment[0]["id"]).execute()
        else:
            sb_public.table("enrollments").insert({
                "class_id": cls["id"],
                "student_id": student_id,
                "team_name": "",
                "active": True,
            }).execute()

        st.success("Cadastro realizado com sucesso.")
        st.markdown("**Como entrar no app:** use seu nome completo ou RA. A senha inicial é o próprio RA.")
        st.link_button("Ir para o login", "https://irreal-app.streamlit.app/")
        st.stop()


if get_query_param("cadastro_turma") or get_query_param("turma") or get_query_param("class_code"):
    render_public_student_registration()
    st.stop()

user = require_login()
logout_button()
sb = supabase_client()

BUCKET_NAME = "deliverables"
ALLOWED_UPLOAD_TYPES = ["pdf", "png", "jpg", "jpeg", "docx", "xlsx", "txt", "csv"]
APP_PUBLIC_URL = "https://irreal-app.streamlit.app"


# ==========================================================
# VISUAL GLOBAL DO APP
# ==========================================================
st.markdown("""
<style>
.stApp {
    background:
        radial-gradient(circle at top left, rgba(255, 199, 44, 0.20) 0%, transparent 28%),
        radial-gradient(circle at bottom right, rgba(0, 255, 180, 0.20) 0%, transparent 34%),
        linear-gradient(135deg, #160B2E 0%, #0B1020 52%, #031B1B 100%);
    color: #F8FAFC;
}

.block-container {
    padding-top: 1.2rem;
    padding-bottom: 2rem;
    max-width: 1220px;
}

[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #1B1035 0%, #0B1020 55%, #05070D 100%);
    border-right: 1px solid rgba(255, 255, 255, 0.08);
}

div[data-testid="stForm"] {
    background: rgba(15, 23, 42, 0.86);
    border: 1px solid rgba(255, 255, 255, 0.14);
    border-radius: 18px;
    padding: 1.1rem;
    box-shadow: 0 12px 35px rgba(0, 0, 0, 0.32);
}

div.stButton > button,
div[data-testid="stFormSubmitButton"] button,
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

div.stButton > button:hover,
div[data-testid="stFormSubmitButton"] button:hover {
    background: linear-gradient(135deg, #22C55E 0%, #86EFAC 100%) !important;
    color: #020617 !important;
    border-color: #BBF7D0 !important;
}


    /* Correção de contraste para campos digitáveis no desktop e no celular */
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

    div[data-testid="stTextInput"] input:focus,
    div[data-testid="stTextArea"] textarea:focus,
    div[data-testid="stNumberInput"] input:focus {
        border: 1px solid #22C55E !important;
        box-shadow: 0 0 0 1px rgba(34, 197, 94, 0.75) !important;
    }

h1, h2, h3 {
    color: #FFFFFF;
    text-shadow: 0 2px 10px rgba(0, 0, 0, 0.35);
}

label, p, span {
    color: #F8FAFC;
}

[data-testid="stMetric"] {
    background: rgba(15, 23, 42, 0.78);
    border: 1px solid rgba(148, 163, 184, 0.24);
    border-radius: 16px;
    padding: 1rem;
}

.irreal-card {
    background: rgba(15, 23, 42, 0.78);
    border: 1px solid rgba(148, 163, 184, 0.24);
    border-radius: 16px;
    padding: 1rem;
    margin-bottom: 0.75rem;
}

.irreal-danger {
    color: #FCA5A5 !important;
    font-weight: 700;
}
</style>
""", unsafe_allow_html=True)


# ==========================================================
# HELPERS GERAIS
# ==========================================================
def role_label(role):
    return {
        "super_admin": "Controle geral",
        "professor": "Professor",
        "student": "Aluno",
    }.get(role, role)


def class_label(c):
    course = c.get("courses") or {}
    return f"{c.get('name')} | {c.get('shift')} | {course.get('name','')} | {c.get('class_code')}"


def select_row(label, rows, label_fn, key=None):
    if not rows:
        st.warning(f"Nenhum registro disponível: {label}")
        return None
    options = {label_fn(r): r for r in rows}
    return options[st.selectbox(label, list(options.keys()), key=key)]


def safe_filename(name: str) -> str:
    name = name or "arquivo"
    return "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in name)


def upload_file_to_storage(uploaded, folder: str):
    """Envia arquivo para o bucket 'deliverables' e retorna (file_name, file_path)."""
    if uploaded is None:
        return "", ""

    file_name = safe_filename(uploaded.name)
    file_path = f"{folder}/{datetime.now().strftime('%Y%m%d%H%M%S')}_{file_name}"
    content_type = uploaded.type or "application/octet-stream"

    try:
        try:
            sb.storage.from_(BUCKET_NAME).upload(
                file_path,
                uploaded.getvalue(),
                file_options={"content-type": content_type},
            )
        except TypeError:
            sb.storage.from_(BUCKET_NAME).upload(
                file_path,
                uploaded.getvalue(),
                {"content-type": content_type},
            )
        return file_name, file_path
    except Exception as e:
        st.warning(f"Não foi possível enviar o arquivo ao Storage. Erro: {e}")
        return file_name, ""


def signed_url_for(file_path: str, expires_in: int = 3600) -> str:
    if not file_path:
        return ""
    try:
        res = sb.storage.from_(BUCKET_NAME).create_signed_url(file_path, expires_in)
        if isinstance(res, dict):
            return (
                res.get("signedURL")
                or res.get("signed_url")
                or res.get("signedUrl")
                or (res.get("data") or {}).get("signedURL")
                or (res.get("data") or {}).get("signedUrl")
                or ""
            )
    except Exception:
        return ""
    return ""


def show_file_link(label: str, file_name: str, file_path: str):
    if not file_path:
        return
    url = signed_url_for(file_path)
    if url:
        st.markdown(f"📎 [{label}: {file_name or 'arquivo'}]({url})")
    else:
        st.caption(f"{label}: {file_name or file_path} — link temporário indisponível.")


def show_material(prefix: str, row: dict):
    if row.get("attachment_external_link"):
        st.markdown(f"🔗 [{prefix}: abrir link/material]({row.get('attachment_external_link')})")
    if row.get("attachment_file_path"):
        show_file_link(prefix, row.get("attachment_file_name") or "arquivo", row.get("attachment_file_path"))


def delete_row(table: str, row_id: str):
    return sb.table(table).delete().eq("id", row_id).execute()


def get_app_public_url() -> str:
    try:
        return st.secrets.get("APP_PUBLIC_URL", APP_PUBLIC_URL).rstrip("/")
    except Exception:
        return APP_PUBLIC_URL


def class_registration_link(c: dict) -> str:
    code = (c.get("class_code") or "").strip()
    if not code:
        return ""
    return f"{get_app_public_url()}/?cadastro_turma={quote(code)}"


def show_class_registration_link(c: dict):
    link = class_registration_link(c)
    if not link:
        return
    st.markdown("**Link de cadastro para enviar aos alunos:**")
    st.code(link, language="text")
    st.link_button("Abrir link de cadastro", link)
    st.caption("O aluno informa somente Nome completo e RA. A senha inicial será o próprio RA.")


def get_available_classes(include_inactive=False):
    select = "id, name, shift, class_code, active, professor_id, courses(name)"
    q = sb.table("classes").select(select).order("name")

    if is_professor(user):
        q = q.eq("professor_id", user["id"])

    if not include_inactive:
        q = q.eq("active", True)

    return q.execute().data or []


def get_class_enrollment_rows(class_id, active_only=True):
    q = (
        sb.table("enrollments")
        .select("id, active, team_name, app_users(id, full_name, email, ra, active)")
        .eq("class_id", class_id)
    )

    if active_only:
        q = q.eq("active", True)

    enrollments = q.execute().data or []
    return [e for e in enrollments if e.get("app_users") and e["app_users"].get("active", True)]


def get_enrolled_students(class_id):
    enrollments = get_class_enrollment_rows(class_id)
    return [
        {
            "id": e["app_users"]["id"],
            "full_name": e["app_users"]["full_name"],
            "email": e["app_users"].get("email"),
            "team_name": e.get("team_name") or "",
            "active": e["app_users"].get("active", True),
            "enrollment_id": e["id"],
        }
        for e in enrollments
    ]


def get_professor_for_class(c):
    if c.get("professor_id"):
        prof_rows = get_rows("app_users", id=c["professor_id"])
        return prof_rows[0] if prof_rows else None
    return None


def register_deliverable(c, mission, challenge, title, description, external_link, uploaded):
    professor = get_professor_for_class(c)
    file_name, file_path = upload_file_to_storage(uploaded, f"student_deliverables/{c['id']}/{user['id']}")

    deliverable = insert_row(
        "deliverables",
        {
            "class_id": c["id"],
            "mission_id": mission["id"] if mission else None,
            "challenge_id": challenge["id"] if challenge else None,
            "student_id": user["id"],
            "title": title.strip(),
            "description": description.strip(),
            "external_link": external_link.strip(),
            "file_name": file_name,
            "file_path": file_path,
            "sent_to_email": professor.get("email") if professor else "",
            "email_status": "pending",
        },
    )

    ok_email, msg = send_deliverable_email(
        professor.get("email") if professor else "",
        professor.get("full_name") if professor else "",
        user["full_name"],
        c.get("name"),
        mission.get("title") if mission else "",
        title,
        description,
        external_link,
        file_name,
        challenge_title=challenge.get("title") if challenge else "",
    )

    update_row(
        "deliverables",
        deliverable["id"],
        {"email_status": "sent" if ok_email else f"failed: {msg}"},
    )

    return ok_email, msg


def teacher_can_manage_class(c):
    if is_super_admin(user):
        return True
    if is_professor(user) and c.get("professor_id") == user["id"]:
        return True
    return False


def require_class_or_stop():
    selected_class = select_row("Turma", get_available_classes(), class_label)
    if not selected_class:
        st.info("Crie uma turma ou solicite vínculo com uma turma antes de usar esta área.")
        st.stop()
    return selected_class


def delivery_form(form_key, c, mission=None, challenge=None, default_title=""):
    with st.form(form_key):
        title = st.text_input("Título do entregável", value=default_title)
        description = st.text_area("Descrição / resposta / evidências")
        external_link = st.text_input("Link externo [Drive, OneDrive, YouTube, etc.]")
        uploaded = st.file_uploader(
            "Anexar foto ou arquivo [PDF, imagem, DOCX, XLSX, TXT, CSV]",
            type=ALLOWED_UPLOAD_TYPES,
        )
        ok = st.form_submit_button("Enviar entregável")

    if ok:
        if not title:
            st.error("Informe o título.")
        else:
            ok_email, msg = register_deliverable(c, mission, challenge, title, description, external_link, uploaded)
            if ok_email:
                st.success("Entregável registrado e enviado ao professor por e-mail.")
            else:
                st.warning(f"Entregável registrado, mas o e-mail não foi enviado: {msg}")


# ==========================================================
# MENU
# ==========================================================
def menu_for_user(user):
    if is_super_admin(user):
        return [
            "Dashboard geral",
            "Professores",
            "Turmas",
            "Alunos",
            "Equipes",
            "Missões",
            "Desafios e atividades",
            "Liderança",
            "IRREAIS e loja",
            "Entregáveis",
            "Feedback",
            "Retorno feedbacks",
            "Exportações",
            "Configuração",
        ]

    if is_professor(user):
        return [
            "Turmas",
            "Alunos",
            "Equipes",
            "Missões",
            "Desafios e atividades",
            "Liderança",
            "IRREAIS e loja",
            "Entregáveis",
            "Feedback",
        ]

    return [
        "Minha área",
        "Minhas missões",
        "Meus desafios",
        "Enviar entregável",
        "Meu extrato",
    ]


st.sidebar.title("🎮 IRREAL Cloud V8.1")
page = st.sidebar.radio("Menu", menu_for_user(user))
st.title("IRREAL App Cloud V8.1")
st.caption(f"Acesso: {user['full_name']} — {role_label(user['role'])}")


# ==========================================================
# DASHBOARD
# ==========================================================
if page == "Dashboard geral":
    if not is_super_admin(user):
        st.stop()

    teachers = get_rows("app_users", role="professor")
    students = get_rows("app_users", role="student")
    classes = get_rows("classes")
    deliverables = get_rows("deliverables")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Professores", len(teachers))
    c2.metric("Alunos", len(students))
    c3.metric("Turmas", len(classes))
    c4.metric("Entregáveis", len(deliverables))

    st.subheader("Turmas")
    st.dataframe(pd.DataFrame(classes), use_container_width=True, hide_index=True)


# ==========================================================
# PROFESSORES
# ==========================================================
elif page == "Professores":
    if not is_super_admin(user):
        st.stop()

    st.header("Cadastro de professores")

    with st.form("create_teacher"):
        full_name = st.text_input("Nome completo do professor")
        email = st.text_input("E-mail do professor")
        password = st.text_input("Senha inicial", type="password")
        ok = st.form_submit_button("Cadastrar professor")

    if ok:
        if not full_name or not email or not password:
            st.error("Nome, e-mail e senha são obrigatórios.")
        else:
            create_user(full_name, email, "professor", password, created_by=user["id"])
            st.success("Professor cadastrado.")
            st.rerun()

    st.subheader("Professores cadastrados")

    for t in get_rows("app_users", order="full_name", role="professor"):
        with st.expander(f"{t['full_name']} — {t.get('email') or 'sem e-mail'} — {'ativo' if t['active'] else 'inativo'}"):
            new_name = st.text_input("Nome", value=t.get("full_name") or "", key=f"teacher_name_{t['id']}")
            new_email = st.text_input("E-mail", value=t.get("email") or "", key=f"teacher_email_{t['id']}")
            c1, c2, c3 = st.columns(3)

            if c1.button("Salvar professor", key=f"save_teacher_{t['id']}"):
                update_row("app_users", t["id"], {"full_name": new_name.strip(), "email": new_email.strip() or None})
                st.success("Professor atualizado.")
                st.rerun()

            if c2.button("Desativar professor", key=f"deact_teacher_{t['id']}"):
                deactivate_user(t["id"])
                st.rerun()

            new_pass = st.text_input("Nova senha", type="password", key=f"pass_teacher_{t['id']}")
            if c3.button("Trocar senha", key=f"chg_teacher_{t['id']}") and new_pass:
                update_row("app_users", t["id"], {"password_hash": hash_password(new_pass)})
                st.success("Senha atualizada.")


# ==========================================================
# TURMAS
# ==========================================================
elif page == "Turmas":
    st.header("Turmas")

    tab_create, tab_manage = st.tabs(["Criar turma", "Gerenciar turmas"])

    with tab_create:
        st.subheader("Criar nova turma")

        courses = get_rows("courses", order="name", active=True)
        teachers = get_rows("app_users", order="full_name", role="professor", active=True) if is_super_admin(user) else [user]

        with st.form("class_create_form"):
            existing_course = None
            if courses:
                course_options = {"Criar novo curso/área": None}
                course_options.update({r["name"]: r for r in courses})
                selected_course_label = st.selectbox("Curso existente", list(course_options.keys()))
                existing_course = course_options[selected_course_label]

            new_course_name = st.text_input("Novo curso/área [opcional]", placeholder="Ex.: Pós-técnico em Veículos Elétricos")
            new_course_description = st.text_area("Descrição do novo curso/área [opcional]")

            if is_super_admin(user):
                teacher = select_row(
                    "Professor responsável",
                    teachers,
                    lambda r: f"{r['full_name']} — {r.get('email') or ''}",
                    key="class_teacher_select",
                )
            else:
                teacher = user
                st.info(f"Esta turma será vinculada ao professor: {user['full_name']}")

            class_name = st.text_input("Nome da turma", placeholder="Ex.: Turma Segurança AT 2026")
            shift = st.selectbox("Turno", ["Matutino", "Vespertino", "Noturno", "Integral", "Outro"])
            code = st.text_input("Código da turma", placeholder="Ex.: AT-2026-NOITE-A")
            ok = st.form_submit_button("Cadastrar turma")

        if ok:
            if not class_name or not code:
                st.error("Nome da turma e código são obrigatórios.")
            elif not teacher:
                st.error("Selecione o professor responsável.")
            else:
                if new_course_name.strip():
                    course = insert_row(
                        "courses",
                        {
                            "name": new_course_name.strip(),
                            "description": new_course_description.strip(),
                            "active": True,
                        },
                    )
                    course_id = course["id"]
                elif existing_course:
                    course_id = existing_course["id"]
                else:
                    st.error("Selecione um curso existente ou informe um novo curso/área.")
                    st.stop()

                created_class = insert_row(
                    "classes",
                    {
                        "course_id": course_id,
                        "professor_id": teacher["id"],
                        "name": class_name.strip(),
                        "shift": shift,
                        "class_code": code.strip(),
                        "active": True,
                    },
                )
                st.success("Turma cadastrada.")
                show_class_registration_link({"class_code": created_class.get("class_code") or code.strip()})
                st.info("Copie o link acima e envie aos alunos para cadastro com Nome completo e RA.")

    with tab_manage:
        st.subheader("Turmas cadastradas")

        classes = get_available_classes(include_inactive=True)
        if not classes:
            st.info("Nenhuma turma vinculada a este usuário.")
        for c in classes:
            with st.expander(f"{class_label(c)} — {'ativa' if c.get('active') else 'inativa'}"):
                if not teacher_can_manage_class(c):
                    st.warning("Você não possui permissão para editar esta turma.")
                    continue

                new_name = st.text_input("Nome da turma", value=c.get("name") or "", key=f"class_name_{c['id']}")
                new_shift = st.selectbox(
                    "Turno",
                    ["Matutino", "Vespertino", "Noturno", "Integral", "Outro"],
                    index=["Matutino", "Vespertino", "Noturno", "Integral", "Outro"].index(c.get("shift") or "Outro") if (c.get("shift") or "Outro") in ["Matutino", "Vespertino", "Noturno", "Integral", "Outro"] else 4,
                    key=f"class_shift_{c['id']}",
                )
                new_code = st.text_input("Código", value=c.get("class_code") or "", key=f"class_code_{c['id']}")

                show_class_registration_link({"class_code": new_code or c.get("class_code")})

                c1, c2, c3 = st.columns(3)

                if c1.button("Salvar turma", key=f"save_class_{c['id']}"):
                    update_row("classes", c["id"], {"name": new_name.strip(), "shift": new_shift, "class_code": new_code.strip()})
                    st.success("Turma atualizada.")
                    st.rerun()

                if c2.button("Ativar/Desativar", key=f"toggle_class_{c['id']}"):
                    update_row("classes", c["id"], {"active": not bool(c.get("active"))})
                    st.rerun()

                confirm = st.text_input("Para excluir definitivamente, digite EXCLUIR", key=f"delete_class_confirm_{c['id']}")
                if c3.button("Excluir turma", key=f"delete_class_{c['id']}"):
                    if confirm == "EXCLUIR":
                        try:
                            delete_row("classes", c["id"])
                            st.success("Turma excluída.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Não foi possível excluir. Desative a turma ou remova vínculos antes. Erro: {e}")
                    else:
                        st.error("Digite EXCLUIR para confirmar.")


# ==========================================================
# ALUNOS
# ==========================================================
elif page == "Alunos":
    st.header("Gestão de alunos")

    selected_class = require_class_or_stop()
    st.write(f"Turma: **{class_label(selected_class)}**")

    tab_create, tab_list = st.tabs(["Cadastrar aluno", "Lista da turma"])

    with tab_create:
        with st.form("student_form"):
            full_name = st.text_input("Nome completo do aluno")
            ra = st.text_input("RA / Registro acadêmico [opcional]")
            password = st.text_input("Senha inicial do aluno", type="password")
            team_name = st.text_input("Equipe [opcional]")
            email = st.text_input("E-mail do aluno [opcional]")
            ok = st.form_submit_button("Cadastrar e vincular aluno")

        if ok:
            if not full_name or not password:
                st.error("Nome completo e senha são obrigatórios.")
            else:
                student = create_user(full_name, email, "student", password, created_by=user["id"])
                if ra.strip():
                    update_row("app_users", student["id"], {"ra": ra.strip()})
                insert_row(
                    "enrollments",
                    {
                        "class_id": selected_class["id"],
                        "student_id": student["id"],
                        "team_name": team_name.strip(),
                        "active": True,
                    },
                )
                st.success("Aluno cadastrado e vinculado.")
                st.rerun()

    with tab_list:
        enrollments = get_class_enrollment_rows(selected_class["id"], active_only=False)
        if not enrollments:
            st.info("Nenhum aluno cadastrado nesta turma.")

        for e in enrollments:
            aluno = e.get("app_users") or {}
            with st.expander(f"{aluno.get('full_name')} | equipe: {e.get('team_name') or '-'} | {'ativo' if e.get('active') and aluno.get('active') else 'inativo'}"):
                new_name = st.text_input("Nome", value=aluno.get("full_name") or "", key=f"student_name_{aluno.get('id')}")
                new_email = st.text_input("E-mail", value=aluno.get("email") or "", key=f"student_email_{aluno.get('id')}")
                new_ra = st.text_input("RA", value=aluno.get("ra") or "", key=f"student_ra_{aluno.get('id')}")
                new_team = st.text_input("Equipe", value=e.get("team_name") or "", key=f"team_{e['id']}")

                c1, c2, c3, c4 = st.columns(4)

                if c1.button("Salvar aluno", key=f"save_student_{e['id']}"):
                    update_row("app_users", aluno["id"], {"full_name": new_name.strip(), "email": new_email.strip() or None, "ra": new_ra.strip() or None})
                    update_row("enrollments", e["id"], {"team_name": new_team.strip()})
                    st.success("Aluno atualizado.")
                    st.rerun()

                if c2.button("Ativar/Desvincular", key=f"toggle_enroll_{e['id']}"):
                    update_row("enrollments", e["id"], {"active": not bool(e.get("active"))})
                    st.rerun()

                if c3.button("Desativar aluno", key=f"deact_student_{aluno.get('id')}"):
                    deactivate_user(aluno["id"])
                    st.rerun()

                new_pass = st.text_input("Nova senha do aluno", type="password", key=f"newpass_{aluno.get('id')}")
                if c4.button("Trocar senha", key=f"chgpass_{aluno.get('id')}") and new_pass:
                    update_row("app_users", aluno["id"], {"password_hash": hash_password(new_pass)})
                    st.success("Senha alterada.")


# ==========================================================
# EQUIPES
# ==========================================================
elif page == "Equipes":
    st.header("Equipes")

    selected_class = require_class_or_stop()
    st.write(f"Turma: **{class_label(selected_class)}**")
    st.info("Cada equipe pode ter no máximo 6 alunos. A equipe pode ser identificada por nome, número ou ambos.")

    tab_create, tab_manage, tab_new_student, tab_summary = st.tabs([
        "Cadastrar / montar equipe",
        "Gerenciar equipe",
        "Cadastrar aluno na equipe",
        "Resumo",
    ])

    enrollments = get_class_enrollment_rows(selected_class["id"])

    with tab_create:
        if not enrollments:
            st.warning("Cadastre alunos nesta turma antes de montar equipes, ou use a aba 'Cadastrar aluno na equipe'.")
        with st.form("team_create_form"):
            c1, c2, c3 = st.columns([2, 1, 1])
            with c1:
                team_name = st.text_input("Nome da equipe", placeholder="Ex.: Diagnóstico HV")
            with c2:
                team_number = st.text_input("Número da equipe", placeholder="Ex.: 01")
            with c3:
                max_students = st.number_input("Limite", min_value=1, max_value=6, value=6, step=1)

            team_label_parts = []
            if team_number.strip():
                team_label_parts.append(f"Equipe {team_number.strip()}")
            if team_name.strip():
                team_label_parts.append(team_name.strip())

            preview_label = " - ".join(team_label_parts)
            st.caption(f"Identificação da equipe: {preview_label or 'informe nome ou número'}")

            options = {
                f"{e['app_users']['full_name']} | atual: {e.get('team_name') or 'sem equipe'}": e
                for e in enrollments
            }
            selected_students = st.multiselect("Alunos para adicionar", list(options.keys()))
            ok = st.form_submit_button("Salvar equipe e vincular alunos")

        if ok:
            if not preview_label:
                st.error("Informe pelo menos o nome ou o número da equipe.")
            else:
                selected_enrollments = [options[x] for x in selected_students]
                current_members = [
                    e for e in enrollments
                    if (e.get("team_name") or "").strip().lower() == preview_label.strip().lower()
                ]
                selected_ids = {e["id"] for e in selected_enrollments}
                new_count = len([e for e in current_members if e["id"] not in selected_ids]) + len(selected_enrollments)

                if new_count > int(max_students):
                    st.error(f"Limite excedido. Esta equipe ficaria com {new_count} alunos. Máximo permitido: {int(max_students)}.")
                else:
                    for e in selected_enrollments:
                        update_row("enrollments", e["id"], {"team_name": preview_label})
                    st.success(f"Equipe '{preview_label}' atualizada com sucesso.")
                    st.rerun()

    with tab_manage:
        teams = sorted(set((e.get("team_name") or "").strip() for e in enrollments if (e.get("team_name") or "").strip()))
        if not teams:
            st.info("Ainda não há equipes cadastradas nesta turma.")
        else:
            team = st.selectbox("Equipe", teams)
            members = [e for e in enrollments if (e.get("team_name") or "").strip() == team]
            st.metric("Integrantes", f"{len(members)}/6")

            st.subheader("Integrantes")
            for e in members:
                aluno = e.get("app_users") or {}
                c1, c2 = st.columns([3, 1])
                c1.write(f"**{aluno.get('full_name')}** — {aluno.get('email') or 'sem e-mail'}")
                if c2.button("Remover da equipe", key=f"remove_team_{e['id']}"):
                    update_row("enrollments", e["id"], {"team_name": ""})
                    st.rerun()

            st.divider()
            st.subheader("Adicionar aluno existente à equipe")
            candidates = [e for e in enrollments if (e.get("team_name") or "").strip() != team]

            if candidates:
                options = {
                    f"{e['app_users']['full_name']} | atual: {e.get('team_name') or 'sem equipe'}": e
                    for e in candidates
                }
                selected_label = st.selectbox("Aluno", list(options.keys()), key="add_student_to_team")

                if st.button("Adicionar à equipe selecionada"):
                    if len(members) >= 6:
                        st.error("Esta equipe já possui 6 alunos.")
                    else:
                        update_row("enrollments", options[selected_label]["id"], {"team_name": team})
                        st.success("Aluno adicionado à equipe.")
                        st.rerun()

            st.divider()
            st.subheader("Excluir equipe")
            st.caption("Excluir equipe remove apenas o nome da equipe dos alunos. Os alunos continuam cadastrados.")
            confirm = st.text_input("Digite EXCLUIR para remover a equipe", key=f"confirm_delete_team_{team}")

            if st.button("Excluir equipe", key=f"delete_team_{team}"):
                if confirm == "EXCLUIR":
                    for e in members:
                        update_row("enrollments", e["id"], {"team_name": ""})
                    st.success("Equipe removida.")
                    st.rerun()
                else:
                    st.error("Digite EXCLUIR para confirmar.")

    with tab_new_student:
        st.subheader("Cadastrar aluno diretamente em uma equipe")

        teams = sorted(set((e.get("team_name") or "").strip() for e in enrollments if (e.get("team_name") or "").strip()))
        team_mode = st.radio("Destino", ["Equipe existente", "Nova equipe"], horizontal=True)

        with st.form("student_direct_team_form"):
            if team_mode == "Equipe existente" and teams:
                target_team = st.selectbox("Equipe", teams)
                new_team_name = ""
                new_team_number = ""
            else:
                target_team = ""
                c1, c2 = st.columns([2, 1])
                new_team_name = c1.text_input("Nome da nova equipe")
                new_team_number = c2.text_input("Número da nova equipe")

            full_name = st.text_input("Nome completo do aluno")
            ra = st.text_input("RA / Registro acadêmico [opcional]")
            email = st.text_input("E-mail [opcional]")
            password = st.text_input("Senha inicial", type="password")
            ok = st.form_submit_button("Cadastrar aluno na equipe")

        if ok:
            if not full_name or not password:
                st.error("Nome e senha são obrigatórios.")
            else:
                if target_team:
                    final_team = target_team
                else:
                    parts = []
                    if new_team_number.strip():
                        parts.append(f"Equipe {new_team_number.strip()}")
                    if new_team_name.strip():
                        parts.append(new_team_name.strip())
                    final_team = " - ".join(parts)

                if not final_team:
                    st.error("Informe a equipe.")
                else:
                    current_count = len([e for e in enrollments if (e.get("team_name") or "").strip() == final_team])
                    if current_count >= 6:
                        st.error("Esta equipe já possui 6 alunos.")
                    else:
                        student = create_user(full_name, email, "student", password, created_by=user["id"])
                        if ra.strip():
                            update_row("app_users", student["id"], {"ra": ra.strip()})
                        insert_row(
                            "enrollments",
                            {
                                "class_id": selected_class["id"],
                                "student_id": student["id"],
                                "team_name": final_team,
                                "active": True,
                            },
                        )
                        st.success("Aluno cadastrado e vinculado à equipe.")
                        st.rerun()

    with tab_summary:
        rows = []
        for e in enrollments:
            aluno = e.get("app_users") or {}
            rows.append({
                "equipe": e.get("team_name") or "Sem equipe",
                "aluno": aluno.get("full_name"),
                "email": aluno.get("email") or "",
            })

        df = pd.DataFrame(rows)
        st.subheader("Alunos por equipe")
        st.dataframe(df.sort_values(["equipe", "aluno"]) if not df.empty else df, use_container_width=True, hide_index=True)

        if not df.empty:
            st.subheader("Quantidade por equipe")
            st.dataframe(df.groupby("equipe")["aluno"].count().reset_index(name="quantidade"), use_container_width=True, hide_index=True)


# ==========================================================
# MISSÕES
# ==========================================================
elif page == "Missões":
    st.header("Missões")

    selected_class = require_class_or_stop()
    st.write(f"Turma: **{class_label(selected_class)}**")

    tab_units, tab_create, tab_manage = st.tabs(["Unidades curriculares", "Criar missão", "Gerenciar missões"])

    with tab_units:
        with st.form("unit_form"):
            name = st.text_input("Unidade curricular")
            workload = st.number_input("Carga horária", min_value=0, step=1)
            description = st.text_area("Descrição")
            ok = st.form_submit_button("Cadastrar unidade")

        if ok and name:
            insert_row(
                "curricular_units",
                {
                    "class_id": selected_class["id"],
                    "name": name.strip(),
                    "workload_hours": int(workload),
                    "description": description.strip(),
                    "active": True,
                },
            )
            st.success("Unidade cadastrada.")
            st.rerun()

        st.dataframe(
            pd.DataFrame(get_rows("curricular_units", class_id=selected_class["id"], active=True)),
            use_container_width=True,
            hide_index=True,
        )

    with tab_create:
        units = get_rows("curricular_units", class_id=selected_class["id"], active=True)

        with st.form("mission_form"):
            unit = select_row("Unidade curricular [opcional]", units, lambda r: r["name"], key="mission_unit") if units else None
            title = st.text_input("Título da missão")
            description = st.text_area("Descrição / orientação")
            material_link = st.text_input("Link do material da missão [opcional]")
            uploaded = st.file_uploader(
                "Arquivo da missão [PDF, imagem, DOCX, XLSX, TXT, CSV]",
                type=ALLOWED_UPLOAD_TYPES,
                key="mission_upload",
            )
            max_irreais = st.number_input("Valor máximo em IRREAIS", min_value=1, value=100, step=10)
            deadline = st.date_input("Data limite", value=date.today())
            ok = st.form_submit_button("Cadastrar missão")

        if ok:
            if not title:
                st.error("Informe o título da missão.")
            else:
                file_name, file_path = upload_file_to_storage(uploaded, f"mission_materials/{selected_class['id']}/{user['id']}")
                insert_row(
                    "missions",
                    {
                        "class_id": selected_class["id"],
                        "unit_id": unit["id"] if unit else None,
                        "title": title.strip(),
                        "description": description.strip(),
                        "max_irreais": int(max_irreais),
                        "deadline_at": datetime.combine(deadline, datetime.min.time()).isoformat(),
                        "active": True,
                        "attachment_external_link": material_link.strip(),
                        "attachment_file_name": file_name,
                        "attachment_file_path": file_path,
                    },
                )
                st.success("Missão cadastrada.")
                st.rerun()

    with tab_manage:
        missions = get_rows("missions", class_id=selected_class["id"], order="created_at", desc=True)

        if not missions:
            st.info("Nenhuma missão cadastrada.")

        for m in missions:
            with st.expander(f"{m.get('title')} — {'ativa' if m.get('active') else 'inativa'}"):
                st.write(m.get("description") or "-")
                st.write(f"**IRREAIS:** {m.get('max_irreais')} | **Prazo:** {m.get('deadline_at') or '-'}")
                show_material("Material da missão", m)

                new_title = st.text_input("Título", value=m.get("title") or "", key=f"mission_title_{m['id']}")
                new_desc = st.text_area("Descrição", value=m.get("description") or "", key=f"mission_desc_{m['id']}")
                new_link = st.text_input("Link do material", value=m.get("attachment_external_link") or "", key=f"mission_link_{m['id']}")
                new_file = st.file_uploader(
                    "Substituir/anexar arquivo",
                    type=ALLOWED_UPLOAD_TYPES,
                    key=f"mission_file_{m['id']}",
                )

                c1, c2, c3, c4 = st.columns(4)

                if c1.button("Salvar missão", key=f"save_mission_{m['id']}"):
                    payload = {
                        "title": new_title.strip(),
                        "description": new_desc.strip(),
                        "attachment_external_link": new_link.strip(),
                    }
                    if new_file is not None:
                        fn, fp = upload_file_to_storage(new_file, f"mission_materials/{selected_class['id']}/{user['id']}")
                        payload["attachment_file_name"] = fn
                        payload["attachment_file_path"] = fp

                    update_row("missions", m["id"], payload)
                    st.success("Missão atualizada.")
                    st.rerun()

                if c2.button("Excluir arquivo/link", key=f"clear_mission_file_{m['id']}"):
                    update_row("missions", m["id"], {
                        "attachment_external_link": "",
                        "attachment_file_name": "",
                        "attachment_file_path": "",
                    })
                    st.rerun()

                if c3.button("Ativar/Desativar", key=f"toggle_mission_{m['id']}"):
                    update_row("missions", m["id"], {"active": not bool(m.get("active"))})
                    st.rerun()

                confirm = st.text_input("Digite EXCLUIR para excluir missão", key=f"delete_mission_confirm_{m['id']}")
                if c4.button("Excluir missão", key=f"delete_mission_{m['id']}"):
                    if confirm == "EXCLUIR":
                        try:
                            delete_row("missions", m["id"])
                            st.success("Missão excluída.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Não foi possível excluir. Use desativar. Erro: {e}")
                    else:
                        st.error("Digite EXCLUIR para confirmar.")


# ==========================================================
# DESAFIOS E ATIVIDADES
# ==========================================================
elif page == "Desafios e atividades":
    st.header("Desafios e atividades por turma ou aluno")

    selected_class = require_class_or_stop()
    st.write(f"Turma: **{class_label(selected_class)}**")

    tab_create, tab_manage, tab_events = st.tabs(["Criar desafio/atividade", "Gerenciar e retirar", "Histórico"])

    units = get_rows("curricular_units", class_id=selected_class["id"], active=True)
    missions = get_rows("missions", class_id=selected_class["id"], active=True)
    students = get_enrolled_students(selected_class["id"])

    with tab_create:
        st.info("Use 'Turma inteira' para todos. Use 'Aluno específico' para recuperação, nivelamento ou trilha individual.")

        with st.form("challenge_form"):
            c1, c2 = st.columns(2)

            with c1:
                challenge_type = st.selectbox(
                    "Tipo",
                    ["atividade", "desafio", "missao_extra", "diagnostico", "recuperacao"],
                    format_func=type_label,
                )
                difficulty = st.selectbox(
                    "Nível de dificuldade",
                    ["basico", "intermediario", "avancado", "mestre"],
                    format_func=difficulty_label,
                )
                unit = select_row("Unidade curricular [opcional]", units, lambda r: r["name"], key="challenge_unit") if units else None
                mission = select_row("Missão geral [opcional]", missions, lambda r: r["title"], key="challenge_mission") if missions else None

            with c2:
                target_scope_label = st.radio("Aplicação", ["Turma inteira", "Aluno específico"])
                target_student = None
                if target_scope_label == "Aluno específico":
                    target_student = select_row("Aluno", students, lambda r: f"{r['full_name']} | {r.get('team_name') or '-'}", key="challenge_student")

                max_base = st.number_input("IRREAIS base", min_value=1, value=100, step=10)
                multiplier = challenge_multiplier(difficulty)
                st.metric("Multiplicador", f"{multiplier:.2f}x")
                st.metric("IRREAIS sugeridos", int(max_base * multiplier))

            title = st.text_input("Título")
            description = st.text_area("Descrição")
            instructions = st.text_area("Instruções ao aluno")
            expected = st.text_area("Entregável esperado")
            attachment_external_link = st.text_input("Link do material/anexo do professor [opcional]")
            teacher_attachment = st.file_uploader(
                "Anexar arquivo da atividade [PDF, imagem, DOCX, XLSX, TXT, CSV]",
                type=ALLOWED_UPLOAD_TYPES,
                key="teacher_challenge_attachment",
            )
            deadline = st.date_input("Prazo", value=date.today())
            penalty = st.number_input("Penalidade máxima sugerida", min_value=0, value=0, step=5)

            ok = st.form_submit_button("Publicar desafio/atividade")

        if ok:
            if not title:
                st.error("Informe o título.")
            elif target_scope_label == "Aluno específico" and not target_student:
                st.error("Selecione o aluno.")
            else:
                attachment_file_name, attachment_file_path = upload_file_to_storage(
                    teacher_attachment,
                    f"teacher_activity_attachments/{selected_class['id']}/{user['id']}",
                )

                challenge = insert_row(
                    "challenges",
                    {
                        "class_id": selected_class["id"],
                        "unit_id": unit["id"] if unit else None,
                        "mission_id": mission["id"] if mission else None,
                        "created_by": user["id"],
                        "title": title.strip(),
                        "challenge_type": challenge_type,
                        "difficulty": difficulty,
                        "target_scope": "aluno" if target_scope_label == "Aluno específico" else "turma",
                        "target_student_id": target_student["id"] if target_student else None,
                        "description": description.strip(),
                        "instructions": instructions.strip(),
                        "expected_deliverable": expected.strip(),
                        "attachment_external_link": attachment_external_link.strip(),
                        "attachment_file_name": attachment_file_name,
                        "attachment_file_path": attachment_file_path,
                        "max_irreais": int(max_base * multiplier),
                        "penalty_irreais": int(penalty),
                        "deadline_at": datetime.combine(deadline, datetime.min.time()).isoformat(),
                        "active": True,
                    },
                )

                create_challenge_event(challenge["id"], user["id"], "created", "Desafio/atividade criado.")
                st.success("Desafio/atividade publicado.")
                st.rerun()

    with tab_manage:
        st.subheader("Ativos")

        challenges = get_rows("challenges", class_id=selected_class["id"], active=True, order="created_at", desc=True)

        if not challenges:
            st.info("Nenhum desafio ativo.")

        for ch in challenges:
            target = "Turma inteira"
            if ch.get("target_scope") == "aluno" and ch.get("target_student_id"):
                srows = get_rows("app_users", id=ch["target_student_id"])
                target = srows[0]["full_name"] if srows else "Aluno não encontrado"

            with st.expander(f"{type_label(ch['challenge_type'])} | {difficulty_label(ch['difficulty'])} | {ch['title']} | alvo: {target}"):
                st.write(ch.get("description") or "")
                st.write("**Instruções:**", ch.get("instructions") or "-")
                st.write("**Entregável esperado:**", ch.get("expected_deliverable") or "-")
                st.write(f"**IRREAIS:** {ch.get('max_irreais')} | **Prazo:** {ch.get('deadline_at')}")
                show_material("Material da atividade", ch)

                new_title = st.text_input("Título", value=ch.get("title") or "", key=f"challenge_title_{ch['id']}")
                new_desc = st.text_area("Descrição", value=ch.get("description") or "", key=f"challenge_desc_{ch['id']}")
                new_instr = st.text_area("Instruções", value=ch.get("instructions") or "", key=f"challenge_instr_{ch['id']}")
                new_expected = st.text_area("Entregável esperado", value=ch.get("expected_deliverable") or "", key=f"challenge_expected_{ch['id']}")
                new_link = st.text_input("Link do material", value=ch.get("attachment_external_link") or "", key=f"challenge_link_{ch['id']}")
                new_file = st.file_uploader(
                    "Substituir/anexar arquivo",
                    type=ALLOWED_UPLOAD_TYPES,
                    key=f"challenge_file_{ch['id']}",
                )

                c1, c2, c3, c4 = st.columns(4)

                if c1.button("Salvar atividade", key=f"save_ch_{ch['id']}"):
                    payload = {
                        "title": new_title.strip(),
                        "description": new_desc.strip(),
                        "instructions": new_instr.strip(),
                        "expected_deliverable": new_expected.strip(),
                        "attachment_external_link": new_link.strip(),
                    }

                    if new_file is not None:
                        fn, fp = upload_file_to_storage(new_file, f"teacher_activity_attachments/{selected_class['id']}/{user['id']}")
                        payload["attachment_file_name"] = fn
                        payload["attachment_file_path"] = fp

                    update_row("challenges", ch["id"], payload)
                    create_challenge_event(ch["id"], user["id"], "updated", "Atividade atualizada.")
                    st.success("Atividade atualizada.")
                    st.rerun()

                if c2.button("Excluir arquivo/link", key=f"clear_ch_file_{ch['id']}"):
                    update_row("challenges", ch["id"], {
                        "attachment_external_link": "",
                        "attachment_file_name": "",
                        "attachment_file_path": "",
                    })
                    create_challenge_event(ch["id"], user["id"], "material_removed", "Material removido.")
                    st.rerun()

                if c3.button("Retirar/desativar", key=f"remove_ch_{ch['id']}"):
                    update_row(
                        "challenges",
                        ch["id"],
                        {
                            "active": False,
                            "removed_at": datetime.now().isoformat(),
                            "removed_by": user["id"],
                        },
                    )
                    create_challenge_event(ch["id"], user["id"], "removed", "Retirado pelo docente.")
                    st.rerun()

                confirm = st.text_input("Digite EXCLUIR para excluir atividade", key=f"delete_ch_confirm_{ch['id']}")
                if c4.button("Excluir atividade", key=f"delete_ch_{ch['id']}"):
                    if confirm == "EXCLUIR":
                        try:
                            delete_row("challenges", ch["id"])
                            st.success("Atividade excluída.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Não foi possível excluir. Use desativar. Erro: {e}")
                    else:
                        st.error("Digite EXCLUIR para confirmar.")

        st.subheader("Retirados/inativos")
        inactive = get_rows("challenges", class_id=selected_class["id"], active=False, order="created_at", desc=True)

        if inactive:
            st.dataframe(pd.DataFrame(inactive), use_container_width=True, hide_index=True)

        for ch in inactive:
            if st.button(f"Reativar: {ch['title']}", key=f"react_{ch['id']}"):
                update_row("challenges", ch["id"], {"active": True, "removed_at": None, "removed_by": None})
                create_challenge_event(ch["id"], user["id"], "reactivated", "Reativado pelo docente.")
                st.rerun()

    with tab_events:
        events = sb.table("challenge_events").select("*, challenges(title), app_users(full_name)").order("created_at", desc=True).limit(200).execute().data or []
        st.dataframe(pd.DataFrame(events), use_container_width=True, hide_index=True)


# ==========================================================
# LIDERANÇA
# ==========================================================
elif page == "Liderança":
    st.header("Liderança rotativa")

    selected_class = require_class_or_stop()
    st.write(f"Turma: **{class_label(selected_class)}**")

    students = get_enrolled_students(selected_class["id"])

    with st.form("leader_form"):
        class_date = st.date_input("Data da aula", value=date.today())
        student = select_row("Líder do dia", students, lambda r: f"{r['full_name']} | {r.get('team_name') or '-'}", key="leader_student")
        notes = st.text_area("Observações")
        ok = st.form_submit_button("Registrar líder")

    if ok and student:
        insert_row(
            "leaders",
            {
                "class_id": selected_class["id"],
                "class_date": str(class_date),
                "student_id": student["id"],
                "notes": notes.strip(),
            },
        )
        st.success("Líder registrado.")
        st.rerun()

    leaders = sb.table("leaders").select("id, class_date, notes, app_users(id, full_name)").eq("class_id", selected_class["id"]).order("class_date", desc=True).execute().data or []

    st.subheader("Registros de liderança")
    if not leaders:
        st.info("Nenhum líder registrado.")

    for l in leaders:
        aluno = l.get("app_users") or {}
        with st.expander(f"{l.get('class_date')} — {aluno.get('full_name') or '-'}"):
            st.write(l.get("notes") or "-")

            new_notes = st.text_area("Editar observação", value=l.get("notes") or "", key=f"leader_notes_{l['id']}")
            c1, c2 = st.columns(2)

            if c1.button("Salvar observação", key=f"save_leader_{l['id']}"):
                update_row("leaders", l["id"], {"notes": new_notes.strip()})
                st.success("Liderança atualizada.")
                st.rerun()

            if c2.button("Excluir liderança", key=f"delete_leader_{l['id']}"):
                delete_row("leaders", l["id"])
                st.success("Registro excluído.")
                st.rerun()


# ==========================================================
# IRREAIS E LOJA
# ==========================================================
elif page == "IRREAIS e loja":
    st.header("IRREAIS e loja")

    selected_class = require_class_or_stop()
    st.write(f"Turma: **{class_label(selected_class)}**")

    tab1, tab2, tab3 = st.tabs(["Lançar IRREAIS", "Loja", "Ranking"])

    with tab1:
        students = get_enrolled_students(selected_class["id"])
        with st.form("tx_form"):
            student = select_row("Aluno", students, lambda r: f"{r['full_name']} | {r.get('team_name') or '-'}", key="tx_student")
            amount = st.number_input("Valor: positivo = crédito; negativo = débito", value=10, step=5)
            reason = st.text_input("Motivo")
            ok = st.form_submit_button("Registrar transação")

        if ok and student:
            insert_row(
                "transactions",
                {
                    "class_id": selected_class["id"],
                    "student_id": student["id"],
                    "team_name": student.get("team_name") or "",
                    "amount": int(amount),
                    "reason": reason.strip() or "Lançamento manual",
                    "reference_type": "manual",
                    "created_by": user["id"],
                },
            )
            st.success("Transação registrada.")
            st.rerun()

    with tab2:
        with st.form("store_form"):
            name = st.text_input("Item da loja")
            cost = st.number_input("Custo", min_value=1, value=50, step=10)
            desc = st.text_area("Descrição")
            max_per = st.number_input("Limite por aluno [0 = sem limite]", min_value=0, value=1)
            ok = st.form_submit_button("Cadastrar item")

        if ok and name:
            insert_row(
                "store_items",
                {
                    "class_id": selected_class["id"],
                    "name": name.strip(),
                    "cost": int(cost),
                    "description": desc.strip(),
                    "max_per_student": int(max_per),
                    "active": True,
                },
            )
            st.success("Item cadastrado.")
            st.rerun()

        st.dataframe(pd.DataFrame(get_rows("store_items", class_id=selected_class["id"], active=True)), use_container_width=True, hide_index=True)

    with tab3:
        rows = sb.table("transactions").select("student_id, team_name, amount, app_users(full_name)").eq("class_id", selected_class["id"]).execute().data or []

        if rows:
            df = pd.DataFrame([
                {
                    "aluno": (r.get("app_users") or {}).get("full_name"),
                    "equipe": r.get("team_name"),
                    "valor": int(r.get("amount") or 0),
                }
                for r in rows
            ])
            st.subheader("Ranking individual")
            st.dataframe(df.groupby(["aluno", "equipe"], dropna=False)["valor"].sum().reset_index().sort_values("valor", ascending=False), use_container_width=True, hide_index=True)

            st.subheader("Ranking por equipe")
            st.dataframe(df.groupby("equipe", dropna=False)["valor"].sum().reset_index().sort_values("valor", ascending=False), use_container_width=True, hide_index=True)
        else:
            st.info("Sem transações nesta turma.")


# ==========================================================
# ENTREGÁVEIS - PROFESSOR
# ==========================================================
elif page == "Entregáveis":
    st.header("Entregáveis")

    selected_class = require_class_or_stop()
    st.write(f"Turma: **{class_label(selected_class)}**")

    deliverables = sb.table("deliverables").select("*, app_users(full_name, email), missions(title), challenges(title, difficulty, challenge_type)").eq("class_id", selected_class["id"]).order("created_at", desc=True).execute().data or []

    if not deliverables:
        st.info("Nenhum entregável enviado nesta turma.")
    else:
        st.dataframe(pd.DataFrame(deliverables), use_container_width=True, hide_index=True)
        st.subheader("Abrir entregáveis")

        for d in deliverables:
            aluno = d.get("app_users") or {}
            mission = d.get("missions") or {}
            challenge = d.get("challenges") or {}

            with st.expander(f"{d.get('title')} | aluno: {aluno.get('full_name', '-')} | missão/desafio: {mission.get('title') or challenge.get('title') or '-'}"):
                st.write("**Descrição / resposta:**")
                st.write(d.get("description") or "-")

                if d.get("external_link"):
                    st.markdown(f"🔗 [Abrir link externo do aluno]({d.get('external_link')})")

                show_file_link("Baixar arquivo enviado pelo aluno", d.get("file_name") or "arquivo", d.get("file_path"))
                st.caption(f"E-mail: {d.get('email_status') or '-'} | Enviado em: {d.get('created_at') or '-'}")


# ==========================================================
# FEEDBACK / SUPORTE - PROFESSOR E CONTROLE GERAL
# ==========================================================
elif page == "Feedback":
    st.header("Feedback e reporte de problemas")
    st.caption("Use esta área para reportar problemas, dúvidas ou pedidos de melhoria do IRREAL App.")

    available_classes = get_available_classes(include_inactive=True)
    selected_class = None
    if available_classes:
        class_options = {"Sem turma específica": None}
        class_options.update({class_label(c): c for c in available_classes})
        selected_class = class_options[st.selectbox("Turma relacionada [opcional]", list(class_options.keys()))]

    tab_new, tab_history = st.tabs(["Reportar problema", "Meus feedbacks"])

    with tab_new:
        with st.form("feedback_form"):
            category = st.selectbox(
                "Categoria",
                ["Erro no app", "Dificuldade de uso", "Pedido de melhoria", "Problema com aluno/turma", "Outro"],
            )
            priority = st.selectbox("Prioridade", ["baixa", "normal", "alta", "crítica"], index=1)
            title = st.text_input("Título do feedback")
            description = st.text_area("Descreva o problema ou sugestão")
            attachment = st.file_uploader(
                "Anexar print ou arquivo [opcional]",
                type=ALLOWED_UPLOAD_TYPES,
                key="feedback_attachment",
            )
            ok = st.form_submit_button("Enviar feedback")

        if ok:
            if not title or not description:
                st.error("Título e descrição são obrigatórios.")
            else:
                file_name, file_path = upload_file_to_storage(attachment, f"feedback/{user['id']}")
                insert_row(
                    "feedback_reports",
                    {
                        "reporter_id": user["id"],
                        "reporter_role": user.get("role"),
                        "class_id": selected_class["id"] if selected_class else None,
                        "category": category,
                        "priority": priority,
                        "title": title.strip(),
                        "description": description.strip(),
                        "attachment_file_name": file_name,
                        "attachment_file_path": file_path,
                        "status": "aberto",
                    },
                )
                st.success("Feedback enviado.")
                st.rerun()

    with tab_history:
        if is_super_admin(user):
            feedbacks = (
                sb.table("feedback_reports")
                .select("*, reporter:app_users!feedback_reports_reporter_id_fkey(full_name, email), class_info:classes!feedback_reports_class_id_fkey(name, class_code)")
                .order("created_at", desc=True)
                .limit(300)
                .execute()
                .data
                or []
            )
        else:
            feedbacks = (
                sb.table("feedback_reports")
                .select("*, reporter:app_users!feedback_reports_reporter_id_fkey(full_name, email), class_info:classes!feedback_reports_class_id_fkey(name, class_code)")
                .eq("reporter_id", user["id"])
                .order("created_at", desc=True)
                .limit(100)
                .execute()
                .data
                or []
            )

        if not feedbacks:
            st.info("Nenhum feedback registrado.")
        else:
            for fb in feedbacks:
                reporter = fb.get("reporter") or {}
                cls = fb.get("class_info") or {}
                with st.expander(f"{fb.get('priority', '').upper()} | {fb.get('status')} | {fb.get('title')}"):
                    st.write(f"**Categoria:** {fb.get('category')}")
                    st.write(f"**Turma:** {cls.get('name') or '-'} {cls.get('class_code') or ''}")
                    st.write(f"**Autor:** {reporter.get('full_name') or '-'}")
                    st.write("**Descrição:**")
                    st.write(fb.get("description") or "-")
                    show_file_link("Baixar anexo do feedback", fb.get("attachment_file_name") or "arquivo", fb.get("attachment_file_path"))
                    st.caption(f"Criado em: {fb.get('created_at') or '-'}")

                    resposta = fb.get("admin_response") or fb.get("admin_notes") or ""
                    if resposta:
                        st.success(f"Retorno da coordenação: {resposta}")

                    if is_super_admin(user):
                        new_status = st.selectbox(
                            "Status",
                            ["aberto", "em análise", "respondido", "resolvido", "fechado"],
                            index=["aberto", "em análise", "respondido", "resolvido", "fechado"].index(fb.get("status") or "aberto") if (fb.get("status") or "aberto") in ["aberto", "em análise", "respondido", "resolvido", "fechado"] else 0,
                            key=f"fb_status_{fb['id']}",
                        )
                        admin_response = st.text_area("Retorno para o docente", value=resposta, key=f"fb_response_{fb['id']}")
                        admin_notes = st.text_area("Observação interna [opcional]", value=fb.get("admin_notes") or "", key=f"fb_notes_{fb['id']}")
                        if st.button("Responder/atualizar feedback", key=f"fb_update_{fb['id']}"):
                            update_row("feedback_reports", fb["id"], {
                                "status": new_status,
                                "admin_response": admin_response,
                                "admin_notes": admin_notes,
                                "responded_by": user["id"],
                                "responded_at": datetime.now().isoformat(),
                                "updated_at": datetime.now().isoformat(),
                            })
                            st.success("Retorno registrado.")
                            st.rerun()



# ==========================================================
# RETORNO DOS FEEDBACKS - CONTROLE GERAL
# ==========================================================
elif page == "Retorno feedbacks":
    if not is_super_admin(user):
        st.stop()

    st.header("Retorno dos feedbacks dos docentes")
    st.caption("Área do controle geral para acompanhar, responder e encerrar problemas reportados pelos professores.")

    status_filter = st.selectbox("Filtrar por status", ["Todos", "aberto", "em análise", "respondido", "resolvido", "fechado"])
    priority_filter = st.selectbox("Filtrar por prioridade", ["Todas", "baixa", "normal", "alta", "crítica"])

    q = (
        sb.table("feedback_reports")
        .select("*, reporter:app_users!feedback_reports_reporter_id_fkey(full_name, email), class_info:classes!feedback_reports_class_id_fkey(name, class_code)")
        .order("created_at", desc=True)
        .limit(500)
    )
    if status_filter != "Todos":
        q = q.eq("status", status_filter)
    if priority_filter != "Todas":
        q = q.eq("priority", priority_filter)

    feedbacks = q.execute().data or []

    if not feedbacks:
        st.info("Nenhum feedback encontrado para o filtro selecionado.")
    else:
        st.metric("Feedbacks encontrados", len(feedbacks))
        for fb in feedbacks:
            reporter = fb.get("reporter") or {}
            cls = fb.get("class_info") or {}
            titulo = f"{(fb.get('priority') or '').upper()} | {fb.get('status')} | {fb.get('title')} | {reporter.get('full_name') or '-'}"
            with st.expander(titulo):
                c1, c2 = st.columns(2)
                c1.write(f"**Categoria:** {fb.get('category') or '-'}")
                c1.write(f"**Prioridade:** {fb.get('priority') or '-'}")
                c2.write(f"**Docente:** {reporter.get('full_name') or '-'}")
                c2.write(f"**Turma:** {cls.get('name') or '-'} {cls.get('class_code') or ''}")

                st.write("**Descrição do problema/sugestão:**")
                st.write(fb.get("description") or "-")
                show_file_link("Baixar anexo do feedback", fb.get("attachment_file_name") or "arquivo", fb.get("attachment_file_path"))

                with st.form(f"return_feedback_{fb['id']}"):
                    new_status = st.selectbox(
                        "Status",
                        ["aberto", "em análise", "respondido", "resolvido", "fechado"],
                        index=["aberto", "em análise", "respondido", "resolvido", "fechado"].index(fb.get("status") or "aberto") if (fb.get("status") or "aberto") in ["aberto", "em análise", "respondido", "resolvido", "fechado"] else 0,
                        key=f"return_status_{fb['id']}",
                    )
                    admin_response = st.text_area("Retorno para o docente", value=fb.get("admin_response") or fb.get("admin_notes") or "")
                    admin_notes = st.text_area("Observação interna [opcional]", value=fb.get("admin_notes") or "")
                    ok = st.form_submit_button("Salvar retorno")

                if ok:
                    update_row("feedback_reports", fb["id"], {
                        "status": new_status,
                        "admin_response": admin_response,
                        "admin_notes": admin_notes,
                        "responded_by": user["id"],
                        "responded_at": datetime.now().isoformat(),
                        "updated_at": datetime.now().isoformat(),
                    })
                    st.success("Retorno salvo para o docente.")
                    st.rerun()


# ==========================================================
# ÁREA DO ALUNO
# ==========================================================
elif page == "Minha área":
    st.header("Minha área")

    class_rows = get_student_classes(user["id"])
    st.subheader("Minhas turmas")

    if class_rows:
        st.dataframe(pd.DataFrame(class_rows), use_container_width=True, hide_index=True)
    else:
        st.info("Você ainda não está vinculado a nenhuma turma.")

    for e in class_rows:
        c = e.get("classes") or {}
        st.metric(f"Saldo — {c.get('name')}", f"{balance_for_student(user['id'], c.get('id'))} IRREAIS")


elif page == "Minhas missões":
    st.header("Minhas missões")

    class_rows = get_student_classes(user["id"])
    selected = select_row("Turma", [{"class": e.get("classes") or {}} for e in class_rows], lambda r: class_label(r["class"]))
    if not selected:
        st.stop()

    c = selected["class"]
    missions = get_rows("missions", class_id=c["id"], active=True, order="deadline_at")

    if not missions:
        st.info("Nenhuma missão disponível no momento.")

    for m in missions:
        with st.expander(f"Missão | {m.get('title')} | prazo: {m.get('deadline_at') or '-'}"):
            st.write(m.get("description") or "-")
            st.write(f"**IRREAIS máximos:** {m.get('max_irreais')}")
            show_material("Baixar material da missão", m)

            st.divider()
            st.subheader("Enviar entregável desta missão")
            delivery_form(
                f"mission_deliverable_{m['id']}",
                c,
                mission=m,
                challenge=None,
                default_title=f"Entrega - {m['title']}",
            )


elif page == "Meus desafios":
    st.header("Meus desafios e atividades")

    class_rows = get_student_classes(user["id"])
    selected = select_row("Turma", [{"class": e.get("classes") or {}} for e in class_rows], lambda r: class_label(r["class"]))
    if not selected:
        st.stop()

    c = selected["class"]

    turma_ch = sb.table("challenges").select("*").eq("class_id", c["id"]).eq("active", True).eq("target_scope", "turma").execute().data or []
    aluno_ch = sb.table("challenges").select("*").eq("class_id", c["id"]).eq("active", True).eq("target_scope", "aluno").eq("target_student_id", user["id"]).execute().data or []
    challenges = sorted(turma_ch + aluno_ch, key=lambda x: x.get("deadline_at") or "")

    if not challenges:
        st.info("Nenhum desafio/atividade atribuído no momento.")

    for ch in challenges:
        with st.expander(f"{type_label(ch['challenge_type'])} | {difficulty_label(ch['difficulty'])} | {ch['title']}"):
            st.write(ch.get("description") or "")
            st.write("**Instruções:**", ch.get("instructions") or "-")
            st.write("**Entregável esperado:**", ch.get("expected_deliverable") or "-")
            st.write(f"**IRREAIS máximos:** {ch.get('max_irreais')}")
            st.write(f"**Prazo:** {ch.get('deadline_at') or '-'}")
            show_material("Baixar material da atividade", ch)

            st.divider()
            st.subheader("Enviar entregável desta atividade")
            delivery_form(
                f"quick_deliverable_{ch['id']}",
                c,
                mission=None,
                challenge=ch,
                default_title=f"Entrega - {ch['title']}",
            )


elif page == "Enviar entregável":
    st.header("Enviar entregável")

    class_rows = get_student_classes(user["id"])
    choices = [{"enrollment": e, "class": e.get("classes") or {}} for e in class_rows]
    selected = select_row("Turma", choices, lambda r: class_label(r["class"]))
    if not selected:
        st.stop()

    c = selected["class"]
    missions = get_rows("missions", class_id=c["id"], active=True)
    turma_ch = sb.table("challenges").select("*").eq("class_id", c["id"]).eq("active", True).eq("target_scope", "turma").execute().data or []
    aluno_ch = sb.table("challenges").select("*").eq("class_id", c["id"]).eq("active", True).eq("target_scope", "aluno").eq("target_student_id", user["id"]).execute().data or []
    challenges = turma_ch + aluno_ch

    with st.form("deliverable_form"):
        mission = select_row("Missão geral [opcional]", missions, lambda r: r["title"], key="manual_mission") if missions else None
        challenge = select_row("Desafio/atividade [opcional]", challenges, lambda r: f"{type_label(r['challenge_type'])} | {difficulty_label(r['difficulty'])} | {r['title']}", key="manual_challenge") if challenges else None
        title = st.text_input("Título do entregável")
        description = st.text_area("Descrição / resposta / evidências")
        external_link = st.text_input("Link externo [Drive, OneDrive, YouTube, etc.]")
        uploaded = st.file_uploader(
            "Arquivo opcional [foto, PDF, DOCX, XLSX, TXT, CSV]",
            type=ALLOWED_UPLOAD_TYPES,
        )
        ok = st.form_submit_button("Enviar entregável")

    if ok:
        if not title:
            st.error("Informe o título.")
        else:
            ok_email, msg = register_deliverable(c, mission, challenge, title, description, external_link, uploaded)
            if ok_email:
                st.success("Entregável registrado e enviado ao professor por e-mail.")
            else:
                st.warning(f"Entregável registrado, mas o e-mail não foi enviado: {msg}")


elif page == "Meu extrato":
    st.header("Meu extrato")

    class_rows = get_student_classes(user["id"])
    selected = select_row("Turma", [{"class": e.get("classes") or {}} for e in class_rows], lambda r: class_label(r["class"]))
    if not selected:
        st.stop()

    c = selected["class"]
    rows = sb.table("transactions").select("*").eq("student_id", user["id"]).eq("class_id", c["id"]).order("created_at", desc=True).execute().data or []

    st.metric("Saldo", f"{balance_for_student(user['id'], c['id'])} IRREAIS")
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


# ==========================================================
# EXPORTAÇÕES / CONFIG
# ==========================================================
elif page == "Exportações":
    if not is_super_admin(user):
        st.stop()

    st.header("Exportações")
    tables = [
        "app_users",
        "courses",
        "classes",
        "enrollments",
        "curricular_units",
        "missions",
        "challenges",
        "challenge_events",
        "leaders",
        "transactions",
        "store_items",
        "purchases",
        "deliverables",
    ]

    for t in tables:
        df = pd.DataFrame(get_rows(t))
        st.download_button(
            f"Baixar {t}.csv",
            df.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"{t}.csv",
            mime="text/csv",
        )


elif page == "Configuração":
    if not is_super_admin(user):
        st.stop()

    st.header("Configuração e segurança")
    st.warning("Não armazene senhas em código. Use Secrets do Streamlit Cloud.")

    st.markdown("""
    Checklist:
    - `SUPABASE_URL` configurado.
    - `SUPABASE_SERVICE_ROLE_KEY` configurado.
    - `RESEND_API_KEY` configurado.
    - `EMAIL_FROM` configurado.
    - Bucket `deliverables` criado no Supabase Storage.
    - Migração V6 executada para anexos de missões e atividades.
    - Professores podem criar/editar/desativar turmas, alunos, equipes, missões, atividades e liderança.
    - Alunos podem baixar materiais e enviar entregáveis com foto/PDF/arquivos.
    """)


