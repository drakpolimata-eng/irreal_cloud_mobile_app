import streamlit as st
import pandas as pd
from datetime import date, datetime
from irreal_auth import require_login, logout_button, is_super_admin, is_professor, is_student, hash_password, supabase_client
from data_service import get_rows, insert_row, update_row, deactivate_user, create_user, balance_for_student, get_professor_classes, get_student_classes, challenge_multiplier, difficulty_label, type_label, create_challenge_event
from email_service import send_deliverable_email

st.set_page_config(page_title="IRREAL App Cloud V4", page_icon="🎮", layout="wide")

# Estilo visual global do IRREAL App
st.markdown("""
<style>
.stApp {
    background:
        radial-gradient(circle at top left, rgba(255, 199, 44, 0.24) 0%, transparent 30%),
        radial-gradient(circle at bottom right, rgba(0, 255, 180, 0.18) 0%, transparent 34%),
        linear-gradient(135deg, #160B2E 0%, #0B1020 52%, #05070D 100%);
    color: #F8FAFC;
}

.block-container {
    padding-top: 1.2rem;
    padding-bottom: 2rem;
    max-width: 1200px;
}

[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #1B1035 0%, #0B1020 55%, #05070D 100%);
    border-right: 1px solid rgba(255, 255, 255, 0.08);
}

div[data-testid="stForm"] {
    background: rgba(15, 23, 42, 0.82);
    border: 1px solid rgba(255, 255, 255, 0.14);
    border-radius: 18px;
    padding: 1.1rem;
    box-shadow: 0 12px 35px rgba(0, 0, 0, 0.32);
}

div[data-testid="stMetric"] {
    background: rgba(15, 23, 42, 0.72);
    border: 1px solid rgba(255, 255, 255, 0.10);
    border-radius: 16px;
    padding: 1rem;
}

[data-testid="stExpander"] {
    background: rgba(15, 23, 42, 0.58);
    border-radius: 14px;
}

h1, h2, h3 {
    color: #FFFFFF;
}

p, label, span {
    color: #F2F2F2;
}

.stAlert {
    border-radius: 14px;
}
</style>
""", unsafe_allow_html=True)

user = require_login()
logout_button()
sb = supabase_client()

BUCKET_NAME = "deliverables"

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
                file_options={"content-type": content_type}
            )
        except TypeError:
            sb.storage.from_(BUCKET_NAME).upload(
                file_path,
                uploaded.getvalue(),
                {"content-type": content_type}
            )
        return file_name, file_path
    except Exception as e:
        st.warning(f"Não foi possível enviar o arquivo ao Storage. Erro: {e}")
        return file_name, ""

def signed_url_for(file_path: str, expires_in: int = 3600) -> str:
    """Gera link temporário para baixar arquivo privado do Supabase Storage."""
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
        st.markdown(f"[{label}: {file_name or 'arquivo'}]({url})")
    else:
        st.caption(f"{label}: {file_name or file_path} — link temporário indisponível.")

def show_challenge_material(ch):
    """Exibe material anexado pelo professor na atividade/desafio."""
    if ch.get("attachment_external_link"):
        st.markdown(f"[Abrir link/material do professor]({ch.get('attachment_external_link')})")
    if ch.get("attachment_file_path"):
        show_file_link("Baixar arquivo da atividade", ch.get("attachment_file_name") or "arquivo", ch.get("attachment_file_path"))

def get_professor_for_class(c):
    if c.get("professor_id"):
        prof_rows = get_rows("app_users", id=c["professor_id"])
        return prof_rows[0] if prof_rows else None
    return None

def register_deliverable(c, mission, challenge, title, description, external_link, uploaded):
    """Registra entregável do aluno, com arquivo opcional e envio de e-mail ao professor."""
    professor = get_professor_for_class(c)
    file_name, file_path = upload_file_to_storage(uploaded, f"student_deliverables/{c['id']}/{user['id']}")
    deliverable = insert_row("deliverables", {
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
        "email_status": "pending"
    })
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
        challenge_title=challenge.get("title") if challenge else ""
    )
    update_row("deliverables", deliverable["id"], {"email_status": "sent" if ok_email else f"failed: {msg}"})
    return ok_email, msg

def get_class_enrollment_rows(class_id):
    """Retorna matrículas ativas da turma com dados do aluno."""
    enrollments = (
        sb.table("enrollments")
        .select("id, active, team_name, app_users(id, full_name, email, active)")
        .eq("class_id", class_id)
        .eq("active", True)
        .execute()
        .data
        or []
    )
    return [e for e in enrollments if e.get("app_users") and e["app_users"].get("active", True)]

def render_equipes_page():
    st.header("Equipes")
    selected_class = select_row("Turma", get_available_classes(), class_label)
    if not selected_class:
        st.stop()

    st.write(f"Turma: **{class_label(selected_class)}**")
    st.info("Cada equipe pode ter no máximo 6 alunos. A equipe pode ser identificada por nome, número ou ambos.")

    enrollments = get_class_enrollment_rows(selected_class["id"])
    if not enrollments:
        st.warning("Cadastre alunos nesta turma antes de organizar equipes.")
        st.stop()

    tab_create, tab_manage, tab_summary = st.tabs(["Cadastrar / montar equipe", "Gerenciar alunos", "Resumo"])

    with tab_create:
        with st.form("team_create_form"):
            c1, c2, c3 = st.columns([2, 1, 1])
            with c1:
                team_name = st.text_input("Nome da equipe", placeholder="Ex.: Equipe Diagnóstico")
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
            for e in members:
                aluno = e.get("app_users") or {}
                c1, c2 = st.columns([3, 1])
                c1.write(f"**{aluno.get('full_name')}** — {aluno.get('email') or 'sem e-mail'}")
                if c2.button("Remover da equipe", key=f"remove_team_{e['id']}"):
                    update_row("enrollments", e["id"], {"team_name": ""})
                    st.rerun()

            st.divider()
            st.subheader("Adicionar aluno existente à equipe")
            free_or_other = [
                e for e in enrollments
                if (e.get("team_name") or "").strip() != team
            ]
            if free_or_other:
                options = {
                    f"{e['app_users']['full_name']} | atual: {e.get('team_name') or 'sem equipe'}": e
                    for e in free_or_other
                }
                selected_label = st.selectbox("Aluno", list(options.keys()), key="add_student_to_team")
                if st.button("Adicionar à equipe selecionada"):
                    if len(members) >= 6:
                        st.error("Esta equipe já possui 6 alunos.")
                    else:
                        update_row("enrollments", options[selected_label]["id"], {"team_name": team})
                        st.success("Aluno adicionado à equipe.")
                        st.rerun()
            else:
                st.info("Todos os alunos já estão nesta equipe.")

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
        st.dataframe(df.sort_values(["equipe", "aluno"]), use_container_width=True, hide_index=True)
        if not df.empty:
            st.subheader("Quantidade por equipe")
            st.dataframe(df.groupby("equipe")["aluno"].count().reset_index(name="quantidade"), use_container_width=True, hide_index=True)


st.sidebar.title("🎮 IRREAL Cloud V4")

def role_label(role):
    return {"super_admin": "Controle geral", "professor": "Professor", "student": "Aluno"}.get(role, role)

def select_row(label, rows, label_fn):
    if not rows:
        st.warning(f"Nenhum registro disponível: {label}")
        return None
    options = {label_fn(r): r for r in rows}
    return options[st.selectbox(label, list(options.keys()))]

def class_label(c):
    course = c.get("courses") or {}
    return f"{c.get('name')} | {c.get('shift')} | {course.get('name','')} | {c.get('class_code')}"

def get_available_classes():
    if is_super_admin(user):
        return get_rows("classes", select="id, name, shift, class_code, active, professor_id, courses(name)", order="name", active=True)
    if is_professor(user):
        return get_professor_classes(user["id"])
    return []



def get_enrolled_students(class_id):
    enrollments = sb.table("enrollments").select("id, team_name, app_users(id, full_name, email, active)").eq("class_id", class_id).eq("active", True).execute().data or []
    return [
        {
            "id": e["app_users"]["id"],
            "full_name": e["app_users"]["full_name"],
            "email": e["app_users"].get("email"),
            "team_name": e.get("team_name") or "",
            "active": e["app_users"].get("active", True)
        }
        for e in enrollments
        if e.get("app_users") and e["app_users"].get("active", True)
    ]

def menu_for_user(user):
    if is_super_admin(user):
        return ["Dashboard geral", "Professores", "Cursos e turmas", "Alunos", "Equipes", "Missões", "Desafios e atividades", "Liderança", "IRREAIS e loja", "Entregáveis", "Exportações", "Configuração"]
    if is_professor(user):
        return ["Minhas turmas", "Alunos", "Equipes", "Missões", "Desafios e atividades", "Liderança", "IRREAIS e loja", "Entregáveis"]
    return ["Minha área", "Meus desafios", "Enviar entregável", "Meu extrato"]

page = st.sidebar.radio("Menu", menu_for_user(user))
st.title("IRREAL App Cloud V4")
st.caption(f"Acesso: {user['full_name']} — {role_label(user['role'])}")

if page == "Dashboard geral":
    if not is_super_admin(user): st.stop()
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

elif page == "Professores":
    if not is_super_admin(user): st.stop()
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
    st.subheader("Professores")
    for t in get_rows("app_users", order="full_name", role="professor"):
        with st.expander(f"{t['full_name']} — {t.get('email') or 'sem e-mail'} — {'ativo' if t['active'] else 'inativo'}"):
            if st.button("Desativar", key=f"deact_teacher_{t['id']}"):
                deactivate_user(t["id"]); st.rerun()
            new_pass = st.text_input("Nova senha", type="password", key=f"pass_teacher_{t['id']}")
            if st.button("Trocar senha", key=f"chg_teacher_{t['id']}") and new_pass:
                update_row("app_users", t["id"], {"password_hash": hash_password(new_pass)})
                st.success("Senha atualizada.")

elif page == "Cursos e turmas":
    if not is_super_admin(user): st.stop()
    st.header("Cursos e turmas")
    tab1, tab2 = st.tabs(["Cursos", "Turmas"])
    with tab1:
        with st.form("course_form"):
            name = st.text_input("Nome do curso")
            desc = st.text_area("Descrição")
            ok = st.form_submit_button("Cadastrar curso")
            if ok and name:
                insert_row("courses", {"name": name.strip(), "description": desc.strip(), "active": True})
                st.success("Curso cadastrado.")
        st.dataframe(pd.DataFrame(get_rows("courses", order="name")), use_container_width=True, hide_index=True)
    with tab2:
        courses = get_rows("courses", order="name", active=True)
        teachers = get_rows("app_users", order="full_name", role="professor", active=True)
        with st.form("class_form"):
            course = select_row("Curso", courses, lambda r: r["name"])
            teacher = select_row("Professor responsável", teachers, lambda r: f"{r['full_name']} — {r.get('email') or ''}")
            class_name = st.text_input("Nome da turma")
            shift = st.selectbox("Turno", ["Matutino", "Vespertino", "Noturno", "Integral", "Outro"])
            code = st.text_input("Código da turma", placeholder="Ex.: MEC-2026-NOITE-A")
            ok = st.form_submit_button("Cadastrar turma")
            if ok and course and teacher and class_name and code:
                insert_row("classes", {"course_id": course["id"], "professor_id": teacher["id"], "name": class_name.strip(), "shift": shift, "class_code": code.strip(), "active": True})
                st.success("Turma cadastrada.")
        rows = get_rows("classes", select="id, name, shift, class_code, active, courses(name), app_users(full_name, email)", order="name")
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

elif page in ["Alunos", "Minhas turmas"]:
    st.header("Gestão de alunos")
    selected_class = select_row("Turma", get_available_classes(), class_label)
    if not selected_class: st.stop()
    st.write(f"Turma: **{class_label(selected_class)}**")
    tab1, tab2 = st.tabs(["Cadastrar aluno", "Lista da turma"])
    with tab1:
        with st.form("student_form"):
            full_name = st.text_input("Nome completo do aluno")
            password = st.text_input("Senha inicial do aluno", type="password")
            team_name = st.text_input("Equipe")
            email = st.text_input("E-mail do aluno [opcional]")
            ok = st.form_submit_button("Cadastrar e vincular aluno")
            if ok:
                if not full_name or not password:
                    st.error("Nome completo e senha são obrigatórios.")
                else:
                    student = create_user(full_name, email, "student", password, created_by=user["id"])
                    insert_row("enrollments", {"class_id": selected_class["id"], "student_id": student["id"], "team_name": team_name.strip(), "active": True})
                    st.success("Aluno cadastrado e vinculado.")
    with tab2:
        enrollments = sb.table("enrollments").select("id, active, team_name, app_users(id, full_name, email, active)").eq("class_id", selected_class["id"]).execute().data or []
        for e in enrollments:
            aluno = e.get("app_users") or {}
            with st.expander(f"{aluno.get('full_name')} | equipe: {e.get('team_name') or '-'} | {'ativo' if e.get('active') and aluno.get('active') else 'inativo'}"):
                new_team = st.text_input("Equipe", value=e.get("team_name") or "", key=f"team_{e['id']}")
                c1, c2, c3 = st.columns(3)
                if c1.button("Atualizar equipe", key=f"upd_team_{e['id']}"):
                    update_row("enrollments", e["id"], {"team_name": new_team}); st.rerun()
                if c2.button("Desvincular da turma", key=f"unenroll_{e['id']}"):
                    update_row("enrollments", e["id"], {"active": False}); st.rerun()
                if c3.button("Desativar aluno", key=f"deact_student_{aluno.get('id')}"):
                    deactivate_user(aluno["id"]); st.rerun()
                new_pass = st.text_input("Nova senha do aluno", type="password", key=f"newpass_{aluno.get('id')}")
                if st.button("Trocar senha do aluno", key=f"chgpass_{aluno.get('id')}") and new_pass:
                    update_row("app_users", aluno["id"], {"password_hash": hash_password(new_pass)})
                    st.success("Senha alterada.")

elif page == "Equipes":
    render_equipes_page()

elif page == "Missões":
    st.header("Missões")
    selected_class = select_row("Turma", get_available_classes(), class_label)
    if not selected_class: st.stop()
    tab1, tab2 = st.tabs(["Unidade curricular", "Missão"])
    with tab1:
        with st.form("unit_form"):
            name = st.text_input("Unidade curricular")
            workload = st.number_input("Carga horária", min_value=0, step=1)
            description = st.text_area("Descrição")
            ok = st.form_submit_button("Cadastrar unidade")
            if ok and name:
                insert_row("curricular_units", {"class_id": selected_class["id"], "name": name.strip(), "workload_hours": int(workload), "description": description.strip(), "active": True})
                st.success("Unidade cadastrada.")
        st.dataframe(pd.DataFrame(get_rows("curricular_units", class_id=selected_class["id"], active=True)), use_container_width=True, hide_index=True)
    with tab2:
        units = get_rows("curricular_units", class_id=selected_class["id"], active=True)
        with st.form("mission_form"):
            unit = select_row("Unidade curricular", units, lambda r: r["name"]) if units else None
            title = st.text_input("Título da missão")
            description = st.text_area("Descrição / orientação")
            max_irreais = st.number_input("Valor máximo em IRREAIS", min_value=1, value=100, step=10)
            deadline = st.date_input("Data limite", value=date.today())
            ok = st.form_submit_button("Cadastrar missão")
            if ok and title:
                insert_row("missions", {"class_id": selected_class["id"], "unit_id": unit["id"] if unit else None, "title": title.strip(), "description": description.strip(), "max_irreais": int(max_irreais), "deadline_at": datetime.combine(deadline, datetime.min.time()).isoformat(), "active": True})
                st.success("Missão cadastrada.")
        st.dataframe(pd.DataFrame(get_rows("missions", class_id=selected_class["id"], active=True)), use_container_width=True, hide_index=True)


elif page == "Desafios e atividades":
    st.header("Desafios e atividades por turma ou aluno")
    selected_class = select_row("Turma", get_available_classes(), class_label)
    if not selected_class: st.stop()

    tab_create, tab_manage, tab_events = st.tabs(["Criar desafio/atividade", "Gerenciar e retirar", "Histórico"])

    units = get_rows("curricular_units", class_id=selected_class["id"], active=True)
    missions = get_rows("missions", class_id=selected_class["id"], active=True)
    students = get_enrolled_students(selected_class["id"])

    with tab_create:
        st.info("Use 'Turma inteira' para todos. Use 'Aluno específico' para recuperação, nivelamento ou trilha avançada individual.")
        with st.form("challenge_form"):
            c1, c2 = st.columns(2)
            with c1:
                challenge_type = st.selectbox("Tipo", ["atividade", "desafio", "missao_extra", "diagnostico", "recuperacao"], format_func=type_label)
                difficulty = st.selectbox("Nível de dificuldade", ["basico", "intermediario", "avancado", "mestre"], format_func=difficulty_label)
                unit = select_row("Unidade curricular [opcional]", units, lambda r: r["name"]) if units else None
                mission = select_row("Missão geral [opcional]", missions, lambda r: r["title"]) if missions else None
            with c2:
                target_scope_label = st.radio("Aplicação", ["Turma inteira", "Aluno específico"])
                target_student = None
                if target_scope_label == "Aluno específico":
                    target_student = select_row("Aluno", students, lambda r: f"{r['full_name']} | {r.get('team_name') or '-'}")
                max_base = st.number_input("IRREAIS base", min_value=1, value=100, step=10)
                multiplier = challenge_multiplier(difficulty)
                st.metric("Multiplicador", f"{multiplier:.2f}x")
                st.metric("IRREAIS sugeridos", int(max_base * multiplier))
            title = st.text_input("Título")
            description = st.text_area("Descrição")
            instructions = st.text_area("Instruções ao aluno")
            expected = st.text_area("Entregável esperado")
            attachment_external_link = st.text_input("Link do material/anexo do professor [opcional]")
            teacher_attachment = st.file_uploader("Anexar arquivo da atividade [opcional]", key="teacher_challenge_attachment")
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
                        f"teacher_activity_attachments/{selected_class['id']}/{user['id']}"
                    )
                    challenge = insert_row("challenges", {
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
                        "active": True
                    })
                    create_challenge_event(challenge["id"], user["id"], "created", "Desafio/atividade criado.")
                    st.success("Desafio/atividade publicado.")

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
                show_challenge_material(ch)
                notes = st.text_input("Motivo da retirada", key=f"remove_note_{ch['id']}")
                c1, c2 = st.columns(2)
                if c1.button("Retirar/desativar", key=f"remove_ch_{ch['id']}"):
                    update_row("challenges", ch["id"], {"active": False, "removed_at": datetime.now().isoformat(), "removed_by": user["id"]})
                    create_challenge_event(ch["id"], user["id"], "removed", notes or "Retirado pelo docente.")
                    st.rerun()
                if c2.button("Duplicar para adaptação", key=f"dup_ch_{ch['id']}"):
                    payload = {k: ch.get(k) for k in ["class_id", "unit_id", "mission_id", "title", "challenge_type", "difficulty", "target_scope", "target_student_id", "description", "instructions", "expected_deliverable", "attachment_external_link", "attachment_file_name", "attachment_file_path", "max_irreais", "penalty_irreais", "deadline_at"]}
                    payload["title"] = f"Cópia - {payload['title']}"
                    payload["created_by"] = user["id"]
                    payload["active"] = True
                    duplicated = insert_row("challenges", payload)
                    create_challenge_event(duplicated["id"], user["id"], "created", "Duplicado a partir de outro desafio.")
                    st.rerun()

        st.subheader("Retirados/inativos")
        inactive = get_rows("challenges", class_id=selected_class["id"], active=False, order="created_at", desc=True)
        st.dataframe(pd.DataFrame(inactive), use_container_width=True, hide_index=True)
        for ch in inactive:
            if st.button(f"Reativar: {ch['title']}", key=f"react_{ch['id']}"):
                update_row("challenges", ch["id"], {"active": True, "removed_at": None, "removed_by": None})
                create_challenge_event(ch["id"], user["id"], "reactivated", "Reativado pelo docente.")
                st.rerun()

    with tab_events:
        events = sb.table("challenge_events").select("*, challenges(title), app_users(full_name)").order("created_at", desc=True).limit(200).execute().data or []
        st.dataframe(pd.DataFrame(events), use_container_width=True, hide_index=True)

elif page == "Liderança":
    st.header("Liderança rotativa")
    selected_class = select_row("Turma", get_available_classes(), class_label)
    if not selected_class: st.stop()
    enrollments = sb.table("enrollments").select("id, team_name, app_users(id, full_name)").eq("class_id", selected_class["id"]).eq("active", True).execute().data or []
    students = [{"id": e["app_users"]["id"], "full_name": e["app_users"]["full_name"], "team_name": e.get("team_name")} for e in enrollments if e.get("app_users")]
    with st.form("leader_form"):
        class_date = st.date_input("Data da aula", value=date.today())
        student = select_row("Líder do dia", students, lambda r: f"{r['full_name']} | {r.get('team_name') or '-'}")
        notes = st.text_area("Observações")
        ok = st.form_submit_button("Registrar líder")
        if ok and student:
            insert_row("leaders", {"class_id": selected_class["id"], "class_date": str(class_date), "student_id": student["id"], "notes": notes.strip()})
            st.success("Líder registrado.")
    leaders = sb.table("leaders").select("id, class_date, notes, app_users(full_name)").eq("class_id", selected_class["id"]).order("class_date", desc=True).execute().data or []
    st.dataframe(pd.DataFrame(leaders), use_container_width=True, hide_index=True)

elif page == "IRREAIS e loja":
    st.header("IRREAIS e loja")
    selected_class = select_row("Turma", get_available_classes(), class_label)
    if not selected_class: st.stop()
    tab1, tab2, tab3 = st.tabs(["Lançar IRREAIS", "Loja", "Ranking"])
    with tab1:
        enrollments = sb.table("enrollments").select("id, team_name, app_users(id, full_name)").eq("class_id", selected_class["id"]).eq("active", True).execute().data or []
        students = [{"id": e["app_users"]["id"], "full_name": e["app_users"]["full_name"], "team_name": e.get("team_name")} for e in enrollments if e.get("app_users")]
        with st.form("tx_form"):
            student = select_row("Aluno", students, lambda r: f"{r['full_name']} | {r.get('team_name') or '-'}")
            amount = st.number_input("Valor: positivo = crédito; negativo = débito", value=10, step=5)
            reason = st.text_input("Motivo")
            ok = st.form_submit_button("Registrar transação")
            if ok and student:
                insert_row("transactions", {"class_id": selected_class["id"], "student_id": student["id"], "team_name": student.get("team_name") or "", "amount": int(amount), "reason": reason.strip() or "Lançamento manual", "reference_type": "manual"})
                st.success("Transação registrada.")
    with tab2:
        with st.form("store_form"):
            name = st.text_input("Item da loja")
            cost = st.number_input("Custo", min_value=1, value=50, step=10)
            desc = st.text_area("Descrição")
            max_per = st.number_input("Limite por aluno [0 = sem limite]", min_value=0, value=1)
            ok = st.form_submit_button("Cadastrar item")
            if ok and name:
                insert_row("store_items", {"class_id": selected_class["id"], "name": name.strip(), "cost": int(cost), "description": desc.strip(), "max_per_student": int(max_per), "active": True})
                st.success("Item cadastrado.")
        st.dataframe(pd.DataFrame(get_rows("store_items", class_id=selected_class["id"], active=True)), use_container_width=True, hide_index=True)
    with tab3:
        rows = sb.table("transactions").select("student_id, team_name, amount, app_users(full_name)").eq("class_id", selected_class["id"]).execute().data or []
        if rows:
            df = pd.DataFrame([{"aluno": (r.get("app_users") or {}).get("full_name"), "equipe": r.get("team_name"), "valor": int(r.get("amount") or 0)} for r in rows])
            st.subheader("Ranking individual")
            st.dataframe(df.groupby(["aluno", "equipe"], dropna=False)["valor"].sum().reset_index().sort_values("valor", ascending=False), use_container_width=True, hide_index=True)
            st.subheader("Ranking por equipe")
            st.dataframe(df.groupby("equipe", dropna=False)["valor"].sum().reset_index().sort_values("valor", ascending=False), use_container_width=True, hide_index=True)
        else:
            st.info("Sem transações nesta turma.")

elif page == "Entregáveis":
    st.header("Entregáveis")
    selected_class = select_row("Turma", get_available_classes(), class_label)
    if not selected_class: st.stop()
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
            with st.expander(f"{d.get('title')} | aluno: {aluno.get('full_name', '-')} | desafio: {challenge.get('title') or '-'}"):
                st.write("**Descrição / resposta:**")
                st.write(d.get("description") or "-")
                if d.get("external_link"):
                    st.markdown(f"[Abrir link externo do aluno]({d.get('external_link')})")
                show_file_link("Baixar arquivo enviado pelo aluno", d.get("file_name") or "arquivo", d.get("file_path"))
                st.caption(f"Missão: {mission.get('title') or '-'} | E-mail: {d.get('email_status') or '-'} | Enviado em: {d.get('created_at') or '-'}")

elif page == "Minha área":
    st.header("Minha área")
    class_rows = get_student_classes(user["id"])
    st.subheader("Minhas turmas")
    st.dataframe(pd.DataFrame(class_rows), use_container_width=True, hide_index=True)
    for e in class_rows:
        c = e.get("classes") or {}
        st.metric(f"Saldo — {c.get('name')}", f"{balance_for_student(user['id'], c.get('id'))} IRREAIS")


elif page == "Meus desafios":
    st.header("Meus desafios e atividades")
    class_rows = get_student_classes(user["id"])
    selected = select_row("Turma", [{"class": e.get("classes") or {}} for e in class_rows], lambda r: class_label(r["class"]))
    if not selected: st.stop()
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
            show_challenge_material(ch)
            st.divider()
            st.subheader("Enviar entregável desta atividade")
            with st.form(f"quick_deliverable_{ch['id']}"):
                q_title = st.text_input("Título do entregável", value=f"Entrega - {ch['title']}", key=f"quick_title_{ch['id']}")
                q_description = st.text_area("Descrição / resposta / evidências", key=f"quick_desc_{ch['id']}")
                q_external_link = st.text_input("Link externo [Drive, OneDrive, YouTube, etc.]", key=f"quick_link_{ch['id']}")
                q_uploaded = st.file_uploader("Anexar arquivo do entregável [opcional]", key=f"quick_file_{ch['id']}")
                q_ok = st.form_submit_button("Enviar entregável")
                if q_ok:
                    if not q_title:
                        st.error("Informe o título.")
                    else:
                        ok_email, msg = register_deliverable(c, None, ch, q_title, q_description, q_external_link, q_uploaded)
                        if ok_email:
                            st.success("Entregável registrado e enviado ao professor por e-mail.")
                        else:
                            st.warning(f"Entregável registrado, mas o e-mail não foi enviado: {msg}")

elif page == "Enviar entregável":
    st.header("Enviar entregável")
    class_rows = get_student_classes(user["id"])
    choices = [{"enrollment": e, "class": e.get("classes") or {}} for e in class_rows]
    selected = select_row("Turma", choices, lambda r: class_label(r["class"]))
    if not selected: st.stop()
    c = selected["class"]
    missions = get_rows("missions", class_id=c["id"], active=True)
    turma_ch = sb.table("challenges").select("*").eq("class_id", c["id"]).eq("active", True).eq("target_scope", "turma").execute().data or []
    aluno_ch = sb.table("challenges").select("*").eq("class_id", c["id"]).eq("active", True).eq("target_scope", "aluno").eq("target_student_id", user["id"]).execute().data or []
    challenges = turma_ch + aluno_ch
    with st.form("deliverable_form"):
        mission = select_row("Missão geral [opcional]", missions, lambda r: r["title"]) if missions else None
        challenge = select_row("Desafio/atividade", challenges, lambda r: f"{type_label(r['challenge_type'])} | {difficulty_label(r['difficulty'])} | {r['title']}") if challenges else None
        title = st.text_input("Título do entregável")
        description = st.text_area("Descrição / resposta / evidências")
        external_link = st.text_input("Link externo [Drive, OneDrive, YouTube, etc.]")
        uploaded = st.file_uploader("Arquivo opcional")
        ok = st.form_submit_button("Enviar entregável")
        if ok:
            if not title:
                st.error("Informe o título."); st.stop()
            ok_email, msg = register_deliverable(c, mission, challenge, title, description, external_link, uploaded)
            if ok_email: st.success("Entregável registrado e enviado ao professor por e-mail.")
            else: st.warning(f"Entregável registrado, mas o e-mail não foi enviado: {msg}")

elif page == "Meu extrato":
    st.header("Meu extrato")
    class_rows = get_student_classes(user["id"])
    selected = select_row("Turma", [{"class": e.get("classes") or {}} for e in class_rows], lambda r: class_label(r["class"]))
    if not selected: st.stop()
    c = selected["class"]
    rows = sb.table("transactions").select("*").eq("student_id", user["id"]).eq("class_id", c["id"]).order("created_at", desc=True).execute().data or []
    st.metric("Saldo", f"{balance_for_student(user['id'], c['id'])} IRREAIS")
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

elif page == "Exportações":
    if not is_super_admin(user): st.stop()
    st.header("Exportações")
    tables = ["app_users", "courses", "classes", "enrollments", "missions", "challenges", "challenge_events", "leaders", "transactions", "store_items", "purchases", "deliverables"]
    for t in tables:
        df = pd.DataFrame(get_rows(t))
        st.download_button(f"Baixar {t}.csv", df.to_csv(index=False).encode("utf-8-sig"), file_name=f"{t}.csv", mime="text/csv")

elif page == "Configuração":
    if not is_super_admin(user): st.stop()
    st.header("Configuração e segurança")
    st.warning("Não armazene senhas em código. Use Secrets do Streamlit Cloud.")
    st.markdown("""
    Checklist:
    - `SUPABASE_URL` configurado.
    - `SUPABASE_SERVICE_ROLE_KEY` configurado.
    - `RESEND_API_KEY` configurado.
    - `EMAIL_FROM` configurado.
    - Bucket `deliverables` criado no Supabase Storage, caso use upload de arquivos.
    - Migração `sql/migration_v1_to_v2_challenges.sql` executada se já existia banco V1.
    - Migração V4 executada para anexos de atividades.
    """)
