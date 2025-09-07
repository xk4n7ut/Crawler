import requests
from concurrent.futures import ThreadPoolExecutor
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

# Color codes for terminal output
GREEN = '\033[92m'
RESET = '\033[0m'

def main(site):
    s = requests.Session()
    ua = {"user-agent": "Mozilla/5.0 (Linux; U; Android 4.2.2; en-ca; GT-P5113 Build/JDQ39) AppleWebKit/534.30 (KHTML, like Gecko) Version/4.0 Safari/534.30"}
    sub = site.split('.')
    archive = [sub[0], sub[1], site, f'{sub[0]}.{sub[1]}', f'{sub[0]}_{sub[1]}', f'{sub[0]}-{sub[1]}', f'{sub[0]}{sub[1]}', 'app', 'apps', 'application', 'web', 'archive', 'archives', 'applications', '__MACOSX', 'www', 'cgi-bin', '.git', '.well-known', '.env', 'Apps', 'App', 'backup', 'back', 'bak', 'old', f'old{sub[0]}', f'{sub[0]}old', f'{sub[0]}_old', f'{sub[0]}-old', 'public', 'asset', 'assets', 'html', 'public_html', 'Archive', '2023', '2022', '2021', '2024', '2025', 'wwwroot', 'database', 'production', 'htdocs', 'index', 'resources', 'new', 'root', 'upload', 'uploads']
    ext = ['sql', 'zip', 'rar', 'tar', 'tar.gz']
    try:
        for i in archive:
            for j in ext:
                r = s.get(f'http://{site}/{i}.{j}', headers=ua, stream=True, timeout=7, verify=False)
                if r.status_code == 200 and 'application/' in r.headers['Content-Type'] and 'imunify360' not in r.headers['Server'] and 'Content-Length' in r.headers and 'ETag' not in r.headers and int(r.headers['Content-Length']) > 3000:
                    with open('result.txt', 'a+') as f:
                        f.write(f'http://{site}/{i}.{j}\n')
                    print(f"{GREEN}{site} | FOUND{RESET}")  # Green colored output
    except:
        pass

asd = input("List Yang Mau di Sodom : ")
f = open(asd).read().splitlines()
with ThreadPoolExecutor(max_workers=100) as ex:
    [ex.submit(main, i) for i in f]
__import__('sys').exit()