@echo off
title PrintForge Auto-Slicer
cd /d "%~dp0"
python auto_slice.py %*
pause
