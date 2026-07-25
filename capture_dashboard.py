"""Login via requests session then open dashboard pages for screenshots."""
import requests, time, os, subprocess
import ctypes
from PIL import ImageGrab

os.makedirs('screenshots', exist_ok=True)

BASE = 'http://localhost:5000'

# Get the login page to fetch CSRF / session cookie
s = requests.Session()
s.get(f'{BASE}/login')

# POST login as admin
r = s.post(f'{BASE}/login', data={
    'email': 'admin@heartguard.com',
    'password': 'admin123'
}, allow_redirects=True)

# Extract session cookie
cookies = s.cookies.get_dict()
cookie_str = '; '.join(f'{k}={v}' for k,v in cookies.items())

dashboard_pages = [
    (f'{BASE}/dashboard/overview',  'screenshots/admin_overview.png'),
    (f'{BASE}/dashboard/patients',  'screenshots/patients.png'),
    (f'{BASE}/dashboard/doctors',   'screenshots/doctors.png'),
    (f'{BASE}/dashboard/detect',    'screenshots/detect.png'),
    (f'{BASE}/dashboard/results',   'screenshots/results.png'),
    (f'{BASE}/dashboard/messages',  'screenshots/messages.png'),
    (f'{BASE}/dashboard/settings',  'screenshots/settings.png'),
    (f'{BASE}/dashboard/analysis',  'screenshots/analysis.png'),
]

import ctypes
def take_screenshot(path):
    img = ImageGrab.grab()
    img.save(path)
    print(f'  Saved {path}')

for url, path in dashboard_pages:
    # Open in Edge with session cookie via devtools protocol isn't easy,
    # so just open the URL directly — user must already be logged in
    subprocess.Popen(['cmd', '/c', f'start msedge --window-size=1400,900 --app={url}'])
    time.sleep(4)
    take_screenshot(path)
    # Close edge
    os.system('taskkill /f /im msedge.exe >nul 2>&1')
    time.sleep(1)

print('Done.')
