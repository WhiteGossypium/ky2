@echo off
rem Этап 4: обратные зависимости на тестовых репозиториях.
cd /d "%~dp0.."
for %%F in (configs\reverse_*.csv configs\errors\reverse_*.csv) do (
  echo === %%F
  python -m src.main %%F
)