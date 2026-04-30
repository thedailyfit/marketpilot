import re
content = open('dashboard/index.html', 'r', encoding='utf-8').read()
ids = re.findall(r'id=["\']([^"\']+)["\']', content)
for i in sorted(set(ids)):
    print(i)
