import subprocess

repo = r'e:\Desktop\Project\MLStockTracker\MLStockTracker'

def run(cmd):
    r = subprocess.run(cmd, cwd=repo, capture_output=True, text=True, shell=True)
    print(f'>>> {cmd}')
    if r.stdout.strip(): 
        print(r.stdout.strip())
    if r.stderr.strip(): 
        print('ERR:', r.stderr.strip())
    print()

run('git status --short')
run('git add -A')
run('git commit -m "Revamp: Machine Learning Signal Platform\n\nComplete rewrite of all frontend and backend files:\n- index.html: new 2-tab dark terminal UI\n- css/style.css: full dark theme (JetBrains Mono)\n- js/app.js: signals, portfolio, GitHub Actions trigger, heatmap\n- scripts/analyze.py: TL/N classification + BUY/SELL/HOLD logic\n- requirements.txt: simplified\n- .github/workflows/analyze.yml: on-demand only\n\nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"')
run('git push')
