@echo off
rem Этап 5: диаграммы Mermaid для трёх пакетов npm и тестовых графов.
cd /d "%~dp0.."
for %%F in (configs\visual_express.csv configs\visual_chalk.csv configs\visual_axios.csv configs\visual_react_dom.csv configs\visual_cycle.csv configs\visual_filter.csv) do (
  echo === %%F
  python -m src.main %%F
)
start "" output\express.html
start "" output\chalk.html
start "" output\axios.html