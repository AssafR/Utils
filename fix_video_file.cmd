@echo off
powershell -NoProfile -ExecutionPolicy Bypass ^
  -File "%~dp0fix_video_file.ps1" %*
