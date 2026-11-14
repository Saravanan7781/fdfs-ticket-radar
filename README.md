# 🚨 FDFS Ticket Radar (BookMyShow + District by Zomato)

An autonomous, high-speed movie ticket radar that continuously monitors **BookMyShow** (`in.bookmyshow.com`) and **District by Zomato** (`district.in/movies` / formerly TicketNew & Paytm) to trigger an **emergency phone siren alert** the exact second First Day First Show (FDFS) tickets open!

---

## 🌟 Why This Exists

For major Indian releases (Rajinikanth, Thalapathy Vijay, Ajith, Prabhas, etc.), FDFS tickets sell out within 2 to 5 minutes:
- Sometimes tickets drop on **District** first.
- Sometimes tickets drop on **BookMyShow** first.
- Different single screens (Rohini, Vettri, Kamala, AGS, Devi) open without warning.

**FDFS Ticket Radar** scans both platforms simultaneously, ignores normal late shows, isolates **early morning FDFS shows (4:00 AM – 8:00 AM)**, and rings an emergency siren on your phone with a direct 1-tap booking button to beat the crowd.

---

## 🛡️ Anti-Bot & Bypass Technology

- **Chrome 120 TLS Impersonation**: Uses `curl_cffi` to mimic real Google Chrome SSL handshakes, completely gliding past Akamai and Cloudflare bot firewalls without getting blocked.
- **Adaptive Jitter Polling**: Randomizes request intervals (e.g. 50s ± 12s) to appear completely human.

---

## 📂 Project Architecture

```
fdfs-ticket-radar/
├── config/
│   ├── watchlist.json       # Active movies, target theatres, and cities
│   └── settings.py          # Notification & timing configurations
├── core/
│   ├── models.py            # Pydantic data schemas (Show, WatchItem, AlertEvent)
│   ├── bms_scanner.py       # BookMyShow TLS scanner
│   ├── district_scanner.py  # District by Zomato TLS scanner
│   └── fdfs_detector.py     # FDFS time logic & theatre filtering
├── notifiers/
│   ├── ntfy_notifier.py     # Priority 5 emergency phone siren alerts
│   └── telegram_notifier.py # (Optional) Telegram alerts
├── cli.py                   # Manage watchlist (add/list/test)
├── radar.py                 # Core tracking loop
├── requirements.txt         # Dependencies
└── run.bat                  # One-click Windows starter
```

---

## 📱 Quick Setup (Receive Phone Alerts in 60 Seconds)

### Step 1: Install `ntfy` on Your Phone (100% Free)
1. Download **ntfy** from the [Google Play Store](https://play.google.com/store/apps/details?id=io.heckel.ntfy) (Android) or [Apple App Store](https://apps.apple.com/app/ntfy/id1625396347) (iOS).
2. Open the app, tap **`+`** (Subscribe to topic), and enter your topic name:
   ```
   saravanan-fdfs-siren-7781
   ```
   *(You can change this topic name anytime in `.env`)*.

### Step 2: Send a Test Siren
Run this in PowerShell to make sure your phone buzzes:
```powershell
C:\Users\ELCOT\fdfs-ticket-radar\.venv\Scripts\python.exe cli.py test
```
Your phone will receive an alert with a test popcorn emoji!

---

## 🎮 Watchlist Management

### 1. View Current Watchlist
```powershell
python cli.py list
```

### 2. Add a Movie to Track
Track a specific movie with target theatres:
```powershell
python cli.py --movie "Coolie" --city "Chennai" --theatres "Rohini,Vettri,AGS"
```

Track a movie across **ALL theatres** in your district:
```powershell
python cli.py --movie "Thalapathy 69" --city "Chennai"
```

Track all shows (not just FDFS):
```powershell
python cli.py --movie "Good Bad Ugly" --city "Coimbatore" --all-shows
```

---

## 🚀 Run the Radar

Double-click **`run.bat`** or run:
```powershell
cd C:\Users\ELCOT\fdfs-ticket-radar
.\.venv\Scripts\python.exe radar.py
```

The radar will scan BookMyShow and District round-the-clock. The instant Day-1 tickets drop, your phone will ring with an emergency siren and a direct link to book!
