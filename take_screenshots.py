"""
Takes screenshots of the HeartGuard app pages using pyautogui + Edge browser.
Run with: venv\Scripts\python.exe take_screenshots.py
"""
import os, time, subprocess, ctypes

# Ensure screenshots dir exists
os.makedirs('screenshots', exist_ok=True)

import ctypes

def screenshot(path):
    """Capture the full screen and save."""
    try:
        import PIL.ImageGrab as ig
        img = ig.grab()
        img.save(path)
        print(f"  Saved: {path}")
    except Exception as e:
        print(f"  ERROR: {e}")

def open_url(url):
    os.system(f'start msedge --window-size=1400,900 --app="{url}"')
    time.sleep(3)

pages = [
    ('http://localhost:5000/',                    'screenshots/home.png'),
    ('http://localhost:5000/about',               'screenshots/about.png'),
    ('http://localhost:5000/contact',             'screenshots/contact.png'),
    ('http://localhost:5000/login',               'screenshots/login.png'),
    ('http://localhost:5000/register',            'screenshots/register.png'),
    ('http://localhost:5000/forgot-password',     'screenshots/forgot_password.png'),
]

for url, path in pages:
    print(f"Capturing: {url}")
    open_url(url)
    screenshot(path)
    time.sleep(1)

print("Done.")
