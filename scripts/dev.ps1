#scripts\dev.ps1
# 開発用スクリプト
# venv 作成・起動・依存導入・実行・テスト を一本化

$ErrorActionPreference = "Stop"

# リポジトリルートへ移動（このps1の場所基準）
$ROOT = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $ROOT

if (-not (Test-Path ".venv")) {
    py -3 -m venv .venv
}

.\.venv\Scripts\Activate.ps1

python -m pip install -U pip
pip install -r requirements.txt

# srcレイアウト対応：パッケージ import を安定させる
$env:PYTHONPATH = (Join-Path $ROOT "src")

python -m apps.main
pytest -q
