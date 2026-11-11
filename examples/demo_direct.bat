@echo off
rem Этап 2: прямые зависимости пакетов из реестра npm (нужен интернет).
cd /d "%~dp0.."
for %%F in (configs\express.csv configs\chalk.csv configs\axios.csv configs\types_node.csv configs\network_errors\*.csv) do (
  echo === %%F
  python -m src.main %%F
)