# Project Template (Python)

## 新規プロジェクト開始手順

1. 本テンプレをコピーして新しいGitHubリポジトリを作成する
2. 作成したリポジトリを repos 配下に clone
3. このテンプレの中身を clone 先にコピー
4. pdf_viewer_core を実際の名前に置換
5. 最初の commit を行う

## 開発ルール
- Git操作は repos 配下のみ
- .env は GitHub に上げない
- 作業開始時は git pull

## 実行方法
```powershell
.\.venv\Scripts\Activate.ps1
python .\apps\main.py



---


## 使い方まとめ（超重要）
- テンプレは **コピーされる側**
- 実プロジェクトは **最初からGitにつながる側**
- 作業は clone 後にしか始めない


このテンプレは必要に応じて拡張してよいが、
**構造の意味（役割分離）は崩さないこと**。



README.md（そのままコピペでOK）
# pdf-viewer-core

軽量な「PDF閲覧＋検索」機能に絞った PDF ビューアーのコア実装テンプレート。  
本リポジトリは **“後から積み上げられる”** ことを最優先にし、UI とコアロジックの責務を分離します。

---

## 目的

- PDF の **閲覧**（ページ移動 / ズーム / 回転 など）
- PDF の **検索**（全文検索 / ヒット箇所へのジャンプ）
- 将来的に注釈・タグ・DB連携などを積み上げても壊れない構造にする

---

## スコープ（案A）

このテンプレが提供するのは「閲覧＋検索」までです。

### ✅ 入るもの（Phase A）
- PDF読み込み
- ページ表示（単ページ / 連続はUI側で選択）
- ページ移動（前後 / 指定ページ）
- ズーム（倍率 / 幅合わせ等はUI側で実装）
- 文字検索（次へ / 前へ / ジャンプ）

### ❌ 入れないもの（将来拡張）
- 注釈（ハイライト / コメント / スタンプ）
- 編集（結合 / 分割 / 変換）
- DB連携（タグ・メタ情報・資産ID紐づけ）
- アカウント/権限管理

---

## 設計原則（重要）

### 1) main.py は “起動器” に徹する（薄く保つ）
`apps/main.py` は以下のみを担当します。

- 設定の読み込み（環境変数・引数）
- コアの初期化
- UIの起動（UI層へ制御を渡す）

**main.py にビジネスロジックを置かないこと。**  
（検索処理、PDF解析、状態管理などは `src/pdf_viewer_core/` 側へ）

### 2) コアは UI 非依存
`src/pdf_viewer_core/` は UI を知らないこと。

- ✅ OK: `bytes` / `pathlib.Path` / `dataclass` / 例外 / ログ
- ❌ NG: Qt の型、Flask、ブラウザDOM、GUIイベントの直接参照

UI は “外側” からコアを呼び出します。

### 3) 例外と戻り値のルール
- コアは「失敗」を例外で表現してよい（`ValueError`, 独自例外など）
- UI は例外をキャッチしてユーザに表示する（コア側でダイアログを出さない）

---

## ディレクトリ構成



pdf-viewer-core
├─ apps/
│ └─ main.py # 起動器（薄く）
├─ src/
│ └─ pdf_viewer_core/
│ ├─ init.py
│ └─ core.py # UI非依存の核（PDF操作 / 検索）
├─ tests/
│ ├─ init.py
│ └─ test_smoke.py
├─ scripts/
│ └─ dev.ps1 # 開発用起動（任意）
├─ pdf-viewer-core.spec # PyInstaller用（採用する場合のみ）
├─ requirements.txt
├─ .env.example
└─ README.md


---

## セットアップ

### 1) venv 作成

PowerShell:

```powershell
cd D:\Develop\repos\pdf-viewer-core
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install -r requirements.txt

2) 起動
python apps\main.py

環境変数（.env）

.env.example を .env にコピーして利用します。

例（キーはプロジェクト都合で増減OK）:

PDF_VIEWER_DEFAULT_OPEN_DIR : 起動時に開く初期フォルダ

PDF_VIEWER_LOG_LEVEL : INFO / DEBUG

開発方針（積み上げ拡張）

将来機能は以下の順で増やすことを想定します。

Phase A（このリポジトリの最小到達点）: 閲覧＋検索

Phase B: 検索結果一覧パネル / 検索ヒットの強調表示

Phase C: 注釈（ハイライト・コメント）＋注釈一覧（外付けモジュール）

Phase D: DB連携（資産ID・タグ・リンク）

Phase B 以降でも core が UI に寄らないことを維持します。

テスト
pytest -q

ビルド（exe化する場合）

このプロジェクトでは .spec を正 とします（Single Source of Truth）。
初回以外はコマンド引数を使わず、spec からビルドします。

例:

pyinstaller .\pdf-viewer-core.spec

ライセンス

必要に応じて追記（MIT / Apache-2.0 / Proprietary など）。


---

## 「不要なものがあれば削除・変更」指示（テンプレ運用ルール）

ここは**中身を見ずに断定しない**で、削除候補と判断基準を提示します。

### 1) 現時点で “採用しないなら消して良い” 候補
- `pdf-viewer-core.spec`  
  → **PyInstallerでexe化する運用を採用しないなら削除**  
  （採用するなら残す。あなたの運用思想的には残す可能性高め）
- `.vscode/settings.json`  
  → チーム共有しない/個人差が大きいなら削除 or 最小化  
- `memo.md`  
  → テンプレに “雑メモ” は混ざりやすいので、基本は削除推奨  
  （残すなら `docs/notes.md` に移す等、位置づけを明確化）

### 2) 基本残す（テンプレとして価値が高い）
- `README.md`（今回作成したテンプレ）
- `requirements.txt`
- `.env.example`
- `scripts/dev.ps1`（ローカル運用が安定するなら）
- `tests/test_smoke.py`（テンプレの最低品質担保）

### 3) 変更推奨（中身次第で）
- `apps/main.py`  
  → **薄さを守るルール**を追加（下にチェックリスト書きます）
- `src/pdf_viewer_core/core.py`  
  → “UI非依存”の説明コメントだけでも先に入れておくと事故りにくい

---

## main.py を薄く保つチェックリスト（運用ルール）
`apps/main.py` に下記が増えたら、分離を検討してください。

- PDFの解析・検索処理を書き始めた
- 状態（現在ページ、検索結果リスト）を保持し始めた
- GUIイベントの処理が増え始めた
- 200行を超えてきた

→ その時点で `src/pdf_viewer_core/` または `ui/` に移す。


## PyInstaller 運用（採用）

このリポジトリでは **.spec を正（Single Source of Truth）** とします。

- onefile：配布が簡単（exe 1本）
- onedir：壊れにくい（フォルダ配布、DLLやデータ同梱が安定）

### ビルド（onefile）

```powershell
pyinstaller .\pdf-viewer-core.onefile.spec
生成物：

dist\pdf-viewer-core.exe

ビルド（onedir）
powershell
コードをコピーする
pyinstaller .\pdf-viewer-core.onedir.spec
生成物：

dist\pdf-viewer-core\pdf-viewer-core.exe

yaml
コードをコピーする

---

## 4) いま削除/変更して良いもの（テンプレ整理）

### ✅ 変更
- `pdf-viewer-core.spec` → `pdf-viewer-core.onefile.spec` にリネーム  
  （テンプレとして意図が明確になる）

### ✅ 削除候補（テンプレとしては消して良い）
- `memo.md`（前に言った通り。残すなら docs/ にテンプレ化して移動）

---

## 5) 仕上げの動作チェック（onedir）
リネーム＆追加後にこれを実行：

```powershell
pyinstaller .\pdf-viewer-core.onedir.spec
.\dist\pdf-viewer-core\pdf-viewer-core.exe