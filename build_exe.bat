@echo off
echo ==================================================
echo   Polymarket 足球比赛 ID 查询器 - 正在打包为桌面应用 (.exe)
echo ==================================================
echo.

REM 运行 pyinstaller 进行打包，将网页文件夹作为资源包含进去
python -m PyInstaller --noconfirm --onefile --windowed --add-data "PolymarketFootballFinder;PolymarketFootballFinder" --name "Polymarket查询器" launcher.py

echo.
echo ==================================================
echo   打包完成！生成的单独可执行程序位于 dist/Polymarket查询器.exe
echo ==================================================
pause
