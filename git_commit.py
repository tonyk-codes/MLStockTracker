import subprocess, os

repo = r'e:\Desktop\Project\MLStockTracker\MLStockTracker'

def run(cmd):
    r = subprocess.run(cmd, cwd=repo, capture_output=True, text=True, shell=True)
    print(f'CMD: {cmd}')
    print(f'STDOUT: {r.stdout.strip()}')
    if r.stderr.strip():
        print(f'STDERR: {r.stderr.strip()}')
    print()
    return r

# 1. Status
run('git status --short')

# 2. Stage all changes
run('git add -A')

# 3. Commit
run('git commit -m "Revamp: Machine Learning Signal Platform\n\nComplete rewrite of all frontend and backend files:\n- index.html: new 2-tab dark terminal UI (Signal Analysis + Correlation)\n- css/style.css: full dark theme rewrite (Bloomberg-style, JetBrains Mono)\n- js/app.js: new signal table, portfolio upload, GitHub Actions trigger, correlation heatmap\n- scripts/analyze.py: TL/N classification + BUY/SELL/HOLD signal logic\n- requirements.txt: simplified to yfinance/pandas/numpy\n- .github/workflows/analyze.yml: on-demand workflow_dispatch only\n\nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"')

# 4. Push
run('git push')
