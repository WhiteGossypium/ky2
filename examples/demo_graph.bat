@echo off
rem Этап 3: граф на тестовых репозиториях и на настоящих пакетах npm.
cd /d "%~dp0.."
for %%F in (configs\test_*.csv configs\chalk.csv configs\axios.csv) do (
  echo === %%F
  python -m src.main %%F
)