@echo off
chcp 65001 > nul
echo =======================================
echo  株式おすすめアプリ セットアップ & 起動
echo =======================================
echo.

REM 依存パッケージのインストール
echo [1/2] パッケージをインストール中...
pip install -r requirements.txt --quiet

echo.
echo [2/2] アプリを起動中...
echo.
echo  ブラウザで以下のURLを開いてください:
echo  http://localhost:5000
echo.
echo  終了するには Ctrl+C を押してください
echo.

python app.py
pause
