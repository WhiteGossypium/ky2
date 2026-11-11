@echo off
rem Этап 1: правильные настройки и по одной ошибке на каждый параметр.
cd /d "%~dp0.."
for %%F in (configs\*.csv) do (
  echo === %%F
  python -m src.main %%F
)
for %%F in (configs\errors\*.csv) do (
  echo === %%F
  python -m src.main %%F
)
echo === configs\no_such_file.csv
python -m src.main configs\no_such_file.csv