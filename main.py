from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response, FileResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from fastapi.middleware.cors import CORSMiddleware
from slowapi.middleware import SlowAPIMiddleware
from cachetools import TTLCache
import instaloader
import os
import random
import requests

# ------------------------------
# ✅ App and middleware setup
# ------------------------------
app = FastAPI()
limiter = Limiter(key_func=get_remote_address)

# ✅ Correct way to add SlowAPI middleware
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Replace with frontend URL in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------
# 🔐 Load or create session files
# ------------------------------
SESSION_DIR = "./sessions"
INSTALOADER_ACCOUNTS = []

ACCOUNTS = [
    {"username": "python_dev1000", "password": "6397257222"},
    {"username": "ajf7382025", "password": "9012449011"},
]

if not os.path.exists(SESSION_DIR):
    os.makedirs(SESSION_DIR)

for acc in ACCOUNTS:
    username = acc["username"]
    password = acc["password"]
    session_path = os.path.join(SESSION_DIR, f"{username}_session.json")

    loader = instaloader.Instaloader(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    )

    try:
        if os.path.exists(session_path):
            loader.load_session_from_file(username, session_path)
            print(f"[+] Loaded session: {username}")
        else:
            print(f"[*] Logging in: {username}...")
            loader.login(username, password)
            loader.save_session_to_file(session_path)
            print(f"[+] New session saved: {username}")

        INSTALOADER_ACCOUNTS.append(loader)

    except Exception as e:
        print(f"[!] Failed session for {username}: {e}")

if not INSTALOADER_ACCOUNTS:
    raise Exception("No valid Instagram sessions found or created.")

# ------------------------------
# 🧠 Simple in-memory cache (10 mins)
# ------------------------------
cache = TTLCache(maxsize=500, ttl=600)

# ------------------------------
# 📦 Instagram profile fetch route
# ------------------------------
@app.get("/profile/{username}")
@limiter.limit("10/minute")
def get_instagram_profile(username: str, request: Request):
    username = username.strip().lower()

    if username in cache:
        return {"success": True, "data": cache[username]}

    loader = random.choice(INSTALOADER_ACCOUNTS)

    try:
        profile = instaloader.Profile.from_username(loader.context, username)
        data = {
            "full_name": profile.full_name or "",
            "bio": profile.biography or "",
            "profile_pic_url": profile.profile_pic_url,
            "followers": profile.followers,
            "following": profile.followees,
            "posts_count": profile.mediacount,
        }
        cache[username] = data
        return {"success": True, "data": data}

    except instaloader.exceptions.ProfileNotExistsException:
        raise HTTPException(status_code=404, detail="Profile not found")
    except instaloader.exceptions.ConnectionException:
        raise HTTPException(status_code=503, detail="Instagram connection failed. Try again later.")
    except Exception as e:
        print(f"Error while fetching profile: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# ------------------------------
# 🖼️ Proxy Image route to fix CORS error
# ------------------------------
@app.get("/proxy-image/")
def proxy_image(url: str):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0"
        }
        resp = requests.get(url, headers=headers)
        return Response(content=resp.content, media_type=resp.headers.get("Content-Type", "image/jpeg"))
    except Exception as e:
        print(f"Error proxying image: {e}")
        raise HTTPException(status_code=500, detail="Image fetch failed")

# ------------------------------
# 🏠 Serve index.html at root "/"
# ------------------------------
@app.get("/", response_class=FileResponse)
def serve_index():
    return FileResponse("index.html")


