import streamlit as st
import resend

def get_secret(name, default=None):
    try:
        return st.secrets.get(name, default)
    except Exception:
        return default

def send_deliverable_email(to_email, professor_name, student_name, class_name, mission_title, title, description, external_link, file_name, challenge_title=""):
    api_key = get_secret("RESEND_API_KEY")
    email_from = get_secret("EMAIL_FROM", "IRREAL App <onboarding@resend.dev>")

    if not api_key:
        return False, "RESEND_API_KEY não configurada."

    if not to_email:
        return False, "Professor sem e-mail cadastrado."

    resend.api_key = api_key

    html = f"""
    <h2>Novo entregável recebido - IRREAL App</h2>
    <p><strong>Professor:</strong> {professor_name}</p>
    <p><strong>Aluno:</strong> {student_name}</p>
    <p><strong>Turma:</strong> {class_name}</p>
    <p><strong>Missão:</strong> {mission_title or "Não vinculada"}</p>
    <p><strong>Desafio/atividade:</strong> {challenge_title or "Não vinculado"}</p>
    <p><strong>Título:</strong> {title}</p>
    <p><strong>Descrição:</strong></p>
    <pre>{description}</pre>
    <p><strong>Link externo:</strong> {external_link or "Não informado"}</p>
    <p><strong>Arquivo:</strong> {file_name or "Não enviado"}</p>
    """

    try:
        resend.Emails.send({
            "from": email_from,
            "to": [to_email],
            "subject": f"IRREAL App - Entregável de {student_name}",
            "html": html,
        })
        return True, "E-mail enviado."
    except Exception as e:
        return False, str(e)
