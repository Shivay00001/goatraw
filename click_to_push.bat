@echo off
echo =======================================
echo 🦅 GoatRaw v2 - Premium Push Script
echo =======================================
echo.
echo Staging all files...
git add .

echo.
echo Committing changes...
git commit -m "GoatRaw v2 Final - Premium Launch (Postgres & Ollama)"

echo.
echo Pushing to GitHub (origin main)...
git push origin main

echo.
echo =======================================
echo ✅ Done! Your Premium Code is Live.
echo =======================================
pause
