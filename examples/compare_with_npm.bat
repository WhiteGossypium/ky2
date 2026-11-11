@echo off
rem Этап 5: сравнение с npm install и npm ls (нужны Node.js и интернет).
cd /d "%~dp0.."
for %%F in (configs\express.csv configs\chalk.csv configs\axios.csv configs\visual_react_dom.csv configs\chokidar.csv) do (
  echo === %%F
  python -m src.npm_compare %%F
)