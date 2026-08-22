# My English Dictionary (Firestore版)

映画・小説の引用と英単語の語源を、自分専用の Firestore 辞典として保存・検索する Streamlit アプリです。

## Firestoreのデータ構造

初回保存時に Firestore が自動作成するため、テーブル作成やSQLは不要です。

| コレクション | フィールド |
| --- | --- |
| `quotes` | `sentence`, `translation`, `source`, `tags`（文字列配列）, `memo`, `created_at` |
| `etymologies` | `words`, `root`, `memo`, `created_at` |
| `lessons` | `title`, `unit`, `lesson_date`, `memo`, `created_at`, `updated_at` |
| `lesson_cards` | `lesson_id`, `elapsed_minutes`, `category`, `content`, `question`, `created_at`, `updated_at` |

各データには Firestore が自動発行するドキュメントIDも付きます。アプリは `created_at` の降順で取得し、キーワードやタグを画面側で柔軟に絞り込みます。

## 授業タイムライン

サイドバーの **授業タイムライン** から、授業名・単元名・日付を作成し、授業開始からの経過分ごとにカードを記録できます。カードは経過時間順に並び、内容・出題問題・カテゴリを後から編集または削除できます。

授業ごとに **JSONで書き出す** ボタンも用意しており、保存済みの設定とタイムラインカードを一つのファイルとしてエクスポートできます。

## 長文読解テスト・ジェネレータ

Gemini APIを利用し、入力した英語長文から問題用紙と解答・解説を生成できます。Streamlit Cloudではアプリの **Settings → Secrets** に次を追加してください。APIキーはソースコードやGitHubへ保存しないでください。

```toml
GEMINI_API_KEY = "YOUR_GEMINI_API_KEY"
GEMINI_MODEL = "gemini-2.5-flash" # 任意
```

## 1. Firebaseプロジェクトを準備

1. [Firebase Console](https://console.firebase.google.com/) でプロジェクトを作成（または選択）します。
2. **Build → Firestore Database → Create database** を選び、Firestore を有効化します。
3. **Project settings → Service accounts → Generate new private key** からサービスアカウントJSONをダウンロードします。

サービスアカウントはデータベースへの強い権限を持つため、公開リポジトリやソースコードへ絶対に登録しないでください。本アプリの `.gitignore` にはローカルJSONの名前を登録済みです。

## 2. ライブラリのインストール

Python 3.10以上で以下を実行します。

```powershell
cd "C:\Users\25010017\Documents\Codex\2026-07-30\python-web-streamlit-supabase-web-etymology"
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

PowerShell の実行ポリシーにより `Activate.ps1` が実行できない環境でも、この手順なら仮想環境を有効化せずにインストールできます。起動時も下記のように仮想環境内の Python を直接指定してください。

## 3. 認証情報の設定

### 推奨: Streamlit Secrets

`.streamlit/secrets.toml.example` を `.streamlit/secrets.toml` にコピーし、ダウンロードしたサービスアカウントJSONの内容を転記します。`private_key` 内の改行は `\\n` のまま記入してください。

### 代替: サービスアカウントJSONのパスを環境変数に設定

ダウンロードしたJSONをプロジェクト外などの安全な場所に置き、以下を実行します。

```powershell
$env:FIREBASE_SERVICE_ACCOUNT_PATH = "C:\\safe-path\\firebase-service-account.json"
$env:FIRESTORE_DATABASE_ID = "my-dictionary2" # `(default)` 以外を作成した場合のみ
```

VS Code の **Streamlit: My English Dictionary** 起動構成では、プロジェクト直下のサービスアカウントJSONを参照する設定をあらかじめ追加しています。ターミナルから起動する場合は、上記の環境変数も同じターミナルで設定してください。

ローカル開発時は、Firebaseからダウンロードした `*-firebase-adminsdk-*.json` 形式のJSONをプロジェクト直下に置くだけでも、アプリが自動検出します。このファイルは必ずGit管理対象外のままにしてください。

Firestore作成時にデータベースIDを `(default)` 以外にした場合は、`FIRESTORE_DATABASE_ID` をそのIDに設定します。このプロジェクトでは `my-dictionary2` が該当します。

## 4. 起動

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

ブラウザに表示された URL を開き、引用または語源の「新規登録」から1件保存してください。Firestore Console の **Firestore Database → Data** で `quotes` または `etymologies` コレクションとドキュメントを確認できます。

## Firestoreセキュリティについて

このアプリはサーバー側の Firebase Admin SDK で接続します。クライアントにサービスアカウントの秘密鍵は渡りませんが、公開URLへこのままデプロイする場合は、Streamlit側にログイン・アクセス制限を必ず追加してください。
