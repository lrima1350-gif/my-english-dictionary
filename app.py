"""Personal English Dictionary built with Streamlit and Google Firestore."""

from __future__ import annotations

import json
import os
import hmac
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import firebase_admin
import streamlit as st
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1 import Client


st.set_page_config(page_title="My English Dictionary", page_icon="📚", layout="wide")

DEFAULT_TAGS = ["関係代名詞", "仮定法", "分詞構文", "比較", "SVO+C", "時制", "助動詞", "イディオム"]


def secret_or_env(name: str) -> str | None:
    """Read a non-secret setting from Streamlit Secrets first, then the environment."""
    try:
        value = st.secrets.get(name)
    except Exception:
        value = None
    return value or os.getenv(name)


def require_login() -> bool:
    """Protect a cloud deployment with a password stored outside the source code."""
    app_password = secret_or_env("APP_PASSWORD")
    # Local development remains convenient; cloud deployment always sets APP_PASSWORD.
    if not app_password:
        return True
    if st.session_state.get("authenticated"):
        return True

    st.title("📚 My English Dictionary")
    st.info("この辞典は個人用です。アクセス用パスワードを入力してください。")
    with st.form("login_form"):
        entered_password = st.text_input("パスワード", type="password")
        submitted = st.form_submit_button("開く", type="primary")
    if submitted:
        if hmac.compare_digest(entered_password, app_password):
            st.session_state.authenticated = True
            st.rerun()
        st.error("パスワードが違います。")
    return False


@st.cache_resource(show_spinner=False)
def get_firestore_client(service_account_json: str, database_id: str | None) -> Client:
    """Initialize the Firebase Admin SDK only once, then return Firestore."""
    service_account = json.loads(service_account_json)
    if not firebase_admin._apps:
        firebase_admin.initialize_app(credentials.Certificate(service_account))
    return firestore.client(database_id=database_id)


def get_client() -> Client | None:
    """Read credentials from Secrets, an environment variable, or a local JSON file."""
    service_account: dict[str, Any] | None = None
    try:
        if "firebase_service_account" in st.secrets:
            service_account = dict(st.secrets["firebase_service_account"])
    except Exception:
        pass

    # Useful for local development. Never commit this JSON file.
    credential_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH")
    if service_account is None and not credential_path:
        # Firebase names downloaded Admin SDK keys like *-firebase-adminsdk-*.json.
        # The file remains local and is ignored by Git; deployment should use Secrets.
        candidates = [Path.cwd() / "firebase-service-account.json"]
        candidates.extend(Path.cwd().glob("*-firebase-adminsdk-*.json"))
        credential_path = next((str(path) for path in candidates if path.is_file()), None)

    if service_account is None and credential_path:
        try:
            with open(credential_path, encoding="utf-8") as file:
                service_account = json.load(file)
        except (OSError, json.JSONDecodeError) as exc:
            st.error(f"サービスアカウントJSONを読み込めませんでした: {exc}")
            return None

    if service_account is None:
        st.error("Firebase認証情報が未設定です。`.streamlit/secrets.toml` またはサービスアカウントJSONを設定してください。")
        return None
    try:
        database_id = secret_or_env("FIRESTORE_DATABASE_ID")
        return get_firestore_client(json.dumps(service_account), database_id)
    except Exception as exc:
        st.error(f"Firestoreへ接続できませんでした: {exc}")
        return None


def contains_keyword(row: dict[str, Any], fields: list[str], keyword: str) -> bool:
    if not keyword:
        return True
    needle = keyword.lower()
    return any(needle in str(row.get(field) or "").lower() for field in fields)


def format_date(value: Any) -> str:
    if isinstance(value, datetime):
        return value.astimezone().strftime("%Y-%m-%d %H:%M")
    return str(value).replace("T", " ")[:16] if value else ""


def show_firestore_error(action: str, exc: Exception) -> None:
    """Show an actionable message for a disabled Firestore API."""
    message = str(exc)
    if "SERVICE_DISABLED" in message or "firestore.googleapis.com" in message:
        st.error(f"{action}できませんでした: Cloud Firestore APIが有効化されていません。")
        st.markdown(
            "[FirebaseプロジェクトのCloud Firestore APIを有効化する](https://console.developers.google.com/apis/api/firestore.googleapis.com/overview?project=my-dictionary-date-base)"
        )
        st.info("有効化後、反映に数分かかることがあります。数分待ってからもう一度保存してください。")
    elif "database (default) does not exist" in message:
        st.error(f"{action}できませんでした: Firestoreデータベースがまだ作成されていません。")
        st.markdown(
            "[Firebase ConsoleでFirestoreデータベースを作成する](https://console.cloud.google.com/datastore/setup?project=my-dictionary-date-base)"
        )
        st.info("作成時は「Cloud Firestore」「Native mode」を選んでください。作成後にもう一度保存できます。")
    else:
        st.error(f"{action}できませんでした: {exc}")


def fetch_rows(client: Client, collection: str) -> list[dict[str, Any]]:
    """Fetch one collection, newest first. Filtering happens in the app for flexible search."""
    documents = client.collection(collection).order_by("created_at", direction=firestore.Query.DESCENDING).stream()
    return [{"id": document.id, **document.to_dict()} for document in documents]


def delete_document(client: Client, collection: str, document_id: str, label: str) -> None:
    """Delete only after the user confirms from the card popover."""
    try:
        client.collection(collection).document(document_id).delete()
        st.success(f"{label}を削除しました。")
        st.rerun()
    except Exception as exc:
        show_firestore_error(f"{label}を削除", exc)


def quote_list(client: Client) -> None:
    st.subheader("登録済みの引用")
    keyword = st.text_input("キーワード", placeholder="引用文・出典・メモを検索", key="quote_keyword")
    try:
        rows = fetch_rows(client, "quotes")
    except Exception as exc:
        show_firestore_error("引用データを取得", exc)
        return

    all_tags = sorted({tag for row in rows for tag in (row.get("tags") or [])})
    selected_tags = st.multiselect("文法タグで絞り込み", all_tags, key="quote_tags")
    filtered = [
        row for row in rows
        if contains_keyword(row, ["sentence", "source", "memo"], keyword)
        and set(selected_tags).issubset(set(row.get("tags") or []))
    ]
    st.caption(f"{len(filtered)} 件表示")
    if not filtered:
        st.info("該当する引用はありません。新規登録タブから追加できます。")
        return
    for row in filtered:
        with st.container(border=True):
            st.markdown(f"> {row.get('sentence', '')}")
            if row.get("translation"):
                st.write(f"**訳**　{row['translation']}")
            if row.get("source"):
                st.caption(f"出典: {row['source']}")
            if row.get("tags"):
                st.caption("　".join(f"`{tag}`" for tag in row["tags"]))
            if row.get("memo"):
                st.write(f"**メモ**　{row['memo']}")
            if row.get("created_at"):
                st.caption(f"登録: {format_date(row['created_at'])}")
            with st.popover("削除", icon="🗑️"):
                st.warning("この引用を削除します。元に戻せません。")
                if st.button("この引用を削除する", type="primary", key=f"delete_quote_{row['id']}"):
                    delete_document(client, "quotes", row["id"], "引用")


def quote_form(client: Client) -> None:
    st.subheader("引用を新規登録")
    with st.form("quote_form", clear_on_submit=True):
        sentence = st.text_area("引用文 *", placeholder="To be, or not to be...")
        translation = st.text_area("日本語訳 *")
        source = st.text_input("出典", placeholder="Hamlet / William Shakespeare")
        tags = st.multiselect("文法タグ", DEFAULT_TAGS, accept_new_options=True)
        memo = st.text_area("自分用メモ")
        submitted = st.form_submit_button("保存する", type="primary")
    if not submitted:
        return
    if not sentence.strip() or not translation.strip():
        st.warning("「引用文」と「日本語訳」は必須です。")
        return
    payload = {
        "sentence": sentence.strip(), "translation": translation.strip(), "source": source.strip(),
        "tags": tags, "memo": memo.strip(), "created_at": datetime.now(timezone.utc),
    }
    try:
        client.collection("quotes").add(payload)
        st.success("引用をFirestoreへ保存しました。")
    except Exception as exc:
        show_firestore_error("引用を保存", exc)


def etymology_list(client: Client) -> None:
    st.subheader("登録済みの語源")
    keyword = st.text_input("キーワード", placeholder="単語・語源・メモを検索", key="etymology_keyword")
    try:
        rows = fetch_rows(client, "etymologies")
    except Exception as exc:
        show_firestore_error("語源データを取得", exc)
        return
    filtered = [row for row in rows if contains_keyword(row, ["words", "root", "memo"], keyword)]
    st.caption(f"{len(filtered)} 件表示")
    if not filtered:
        st.info("該当する語源はありません。新規登録タブから追加できます。")
        return
    for row in filtered:
        with st.container(border=True):
            st.markdown(f"### {row.get('words', '')}")
            st.write(f"**語源**　{row.get('root', '')}")
            if row.get("memo"):
                st.write(row["memo"])
            if row.get("created_at"):
                st.caption(f"登録: {format_date(row['created_at'])}")
            with st.popover("削除", icon="🗑️"):
                st.warning("この語源を削除します。元に戻せません。")
                if st.button("この語源を削除する", type="primary", key=f"delete_etymology_{row['id']}"):
                    delete_document(client, "etymologies", row["id"], "語源")


def etymology_form(client: Client) -> None:
    st.subheader("語源を新規登録")
    with st.form("etymology_form", clear_on_submit=True):
        words = st.text_input("現在の単語（代表例） *", placeholder="dictionary, dictate")
        root = st.text_input("語源となる言葉 *", placeholder="dict = 言う")
        memo = st.text_area("由来・メモ", placeholder="覚え方や関連語を書き留める")
        submitted = st.form_submit_button("保存する", type="primary")
    if not submitted:
        return
    if not words.strip() or not root.strip():
        st.warning("「現在の単語」と「語源となる言葉」は必須です。")
        return
    payload = {"words": words.strip(), "root": root.strip(), "memo": memo.strip(), "created_at": datetime.now(timezone.utc)}
    try:
        client.collection("etymologies").add(payload)
        st.success("語源をFirestoreへ保存しました。")
    except Exception as exc:
        show_firestore_error("語源を保存", exc)


def main() -> None:
    if not require_login():
        st.stop()
    st.title("📚 My English Dictionary")
    st.caption("心に残った引用と、単語の語源を自分だけの辞典に。")
    client = get_client()
    if client is None:
        st.stop()
    page = st.sidebar.radio("メニュー", ["引用", "語源"])
    list_tab, form_tab = st.tabs(["一覧・検索", "新規登録"])
    if page == "引用":
        with list_tab:
            quote_list(client)
        with form_tab:
            quote_form(client)
    else:
        with list_tab:
            etymology_list(client)
        with form_tab:
            etymology_form(client)


if __name__ == "__main__":
    main()
