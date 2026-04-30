import sys
sys.stdout.reconfigure(encoding='utf-8')
content = open('dashboard/index.html', 'r', encoding='utf-8').read()
idx = content.find('refreshCmd')
if idx > 0:
    start = max(0, idx)
    end = min(len(content), idx + 2000)
    snippet = content[start:end]
    print(snippet)
