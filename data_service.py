from datetime import datetime
import pandas as pd
from irreal_auth import supabase_client, hash_password


def now_iso():
    return datetime.now().isoformat()


def df_from(table, select="*", **filters):
    sb = supabase_client()
    q = sb.table(table).select(select)
    for k, v in filters.items():
        if v is not None:
            q = q.eq(k, v)
    res = q.execute()
    return pd.DataFrame(res.data or [])


def get_rows(table, select="*", order=None, desc=False, **filters):
    sb = supabase_client()
    q = sb.table(table).select(select)
    for k, v in filters.items():
        if v is not None:
            q = q.eq(k, v)
    if order:
        q = q.order(order, desc=desc)
    return q.execute().data or []


def insert_row(table, payload):
    sb = supabase_client()
    return sb.table(table).insert(payload).execute().data[0]


def update_row(table, row_id, payload):
    sb = supabase_client()
    return sb.table(table).update(payload).eq("id", row_id).execute().data


def deactivate_user(user_id):
    return update_row("app_users", user_id, {"active": False})


def create_user(full_name, email, role, password, created_by=None):
    payload = {
        "full_name": full_name.strip(),
        "email": (email or "").strip() or None,
        "role": role,
        "password_hash": hash_password(password),
        "active": True,
        "created_by": created_by,
    }
    return insert_row("app_users", payload)


def balance_for_student(student_id, class_id=None):
    sb = supabase_client()
    q = sb.table("transactions").select("amount").eq("student_id", student_id)
    if class_id:
        q = q.eq("class_id", class_id)
    data = q.execute().data or []
    return sum(int(r.get("amount") or 0) for r in data)


def get_professor_classes(professor_id):
    return get_rows(
        "classes",
        select="id, name, shift, class_code, active, courses(name), professor_id",
        order="name",
        professor_id=professor_id,
        active=True,
    )


def get_student_classes(student_id):
    sb = supabase_client()
    rows = (
        sb.table("enrollments")
        .select("id, team_name, active, classes(id, name, shift, class_code, professor_id, courses(name))")
        .eq("student_id", student_id)
        .eq("active", True)
        .execute()
        .data
        or []
    )
    return rows


def challenge_multiplier(difficulty):
    return {
        "basico": 1.0,
        "intermediario": 1.25,
        "avancado": 1.5,
        "mestre": 2.0,
    }.get(difficulty, 1.0)


def difficulty_label(difficulty):
    return {
        "basico": "Básico",
        "intermediario": "Intermediário",
        "avancado": "Avançado",
        "mestre": "Desafio Mestre",
    }.get(difficulty, difficulty)


def type_label(challenge_type):
    return {
        "desafio": "Desafio",
        "atividade": "Atividade",
        "missao_extra": "Missão extra",
        "diagnostico": "Diagnóstico",
        "recuperacao": "Recuperação",
    }.get(challenge_type, challenge_type)


def create_challenge_event(challenge_id, actor_id, event_type, notes=""):
    return insert_row(
        "challenge_events",
        {
            "challenge_id": challenge_id,
            "actor_id": actor_id,
            "event_type": event_type,
            "notes": notes,
        },
    )


