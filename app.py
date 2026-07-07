import streamlit as st
import pandas as pd
from datetime import date, datetime
from irreal_auth import require_login, logout_button, is_super_admin, is_professor, is_student, hash_password, supabase_client
from data_service import get_rows, insert_row, update_row, deactivate_user, create_user, balance_for_student, get_professor_classes, get_student_classes, challenge_multiplier, difficulty_label, type_label, create_challenge_event
from email_service import send_deliverable_email

st.set_page_config(page_title="IRREAL App Cloud V2", page_icon="🎮", layout="wide")
user = require_login()
logout_button()
sb = supabase_client()

st.sidebar.title("🎮 IRREAL Cloud V2")

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
        return ["Dashboard geral", "Professores", "Cursos e turmas", "Alunos", "Missões", "Desafios e atividades", "Liderança", "IRREAIS e loja", "Entregáveis", "Exportações", "Configuração"]
    if is_professor(user):
        return ["Minhas turmas", "Alunos", "Missões", "Desafios e atividades", "Liderança", "IRREAIS e loja", "Entregáveis"]
    return ["Minha área", "Meus desafios", "Enviar entregável", "Meu extrato"]

page = st.sidebar.radio("Menu", menu_for_user(user))
st.title("IRREAL App Cloud V2")
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
            deadline = st.date_input("Prazo", value=date.today())
            penalty = st.number_input("Penalidade máxima sugerida", min_value=0, value=0, step=5)
            ok = st.form_submit_button("Publicar desafio/atividade")
            if ok:
                if not title:
                    st.error("Informe o título.")
                elif target_scope_label == "Aluno específico" and not target_student:
                    st.error("Selecione o aluno.")
                else:
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
                notes = st.text_input("Motivo da retirada", key=f"remove_note_{ch['id']}")
                c1, c2 = st.columns(2)
                if c1.button("Retirar/desativar", key=f"remove_ch_{ch['id']}"):
                    update_row("challenges", ch["id"], {"active": False, "removed_at": datetime.now().isoformat(), "removed_by": user["id"]})
                    create_challenge_event(ch["id"], user["id"], "removed", notes or "Retirado pelo docente.")
                    st.rerun()
                if c2.button("Duplicar para adaptação", key=f"dup_ch_{ch['id']}"):
                    payload = {k: ch.get(k) for k in ["class_id", "unit_id", "mission_id", "title", "challenge_type", "difficulty", "target_scope", "target_student_id", "description", "instructions", "expected_deliverable", "max_irreais", "penalty_irreais", "deadline_at"]}
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
    deliverables = sb.table("deliverables").select("*, app_users(full_name), missions(title), challenges(title, difficulty, challenge_type)").eq("class_id", selected_class["id"]).order("created_at", desc=True).execute().data or []
    st.dataframe(pd.DataFrame(deliverables), use_container_width=True, hide_index=True)

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
            st.caption("Para enviar, vá em 'Enviar entregável' e selecione este desafio.")

elif page == "Enviar entregável":
    st.header("Enviar entregável")
    class_rows = get_student_classes(user["id"])
    choices = [{"enrollment": e, "class": e.get("classes") or {}} for e in class_rows]
    selected = select_row("Turma", choices, lambda r: class_label(r["class"]))
    if not selected: st.stop()
    c = selected["class"]
    professor = None
    if c.get("professor_id"):
        prof_rows = get_rows("app_users", id=c["professor_id"])
        professor = prof_rows[0] if prof_rows else None
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
            file_name = ""
            file_path = ""
            if uploaded is not None:
                file_name = uploaded.name
                file_path = f"{c['id']}/{user['id']}/{datetime.now().strftime('%Y%m%d%H%M%S')}_{uploaded.name}"
                try:
                    sb.storage.from_("deliverables").upload(file_path, uploaded.getvalue(), {"content-type": uploaded.type or "application/octet-stream"})
                except Exception as e:
                    st.warning(f"Não foi possível enviar arquivo ao Storage. Erro: {e}")
                    file_path = ""
            deliverable = insert_row("deliverables", {"class_id": c["id"], "mission_id": mission["id"] if mission else None, "challenge_id": challenge["id"] if challenge else None, "student_id": user["id"], "title": title.strip(), "description": description.strip(), "external_link": external_link.strip(), "file_name": file_name, "file_path": file_path, "sent_to_email": professor.get("email") if professor else "", "email_status": "pending"})
            ok_email, msg = send_deliverable_email(professor.get("email") if professor else "", professor.get("full_name") if professor else "", user["full_name"], c.get("name"), mission.get("title") if mission else "", title, description, external_link, file_name, challenge_title=challenge.get("title") if challenge else "")
            update_row("deliverables", deliverable["id"], {"email_status": "sent" if ok_email else f"failed: {msg}"})
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
    """)
