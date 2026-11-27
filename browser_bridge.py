"""
Browser / Emscripten Interop, Focus-Loss Anti-AI Tracking, and Firebase Telemetry
"""

import json
import platform
import sys
import time
import urllib.parse
from config import FIREBASE_URL


def detect_class_id():
    """
    Detects class_id from browser URL query string (?class=7MAT1) when running
    under Pygbag/Emscripten (also styling Pygbag HTML prompts), or from CLI
    arguments when running locally.
    """
    class_id = "DEFAULT"
    if sys.platform == "emscripten":
        try:
            platform.window.eval("""
                var style = document.createElement('style');
                style.innerHTML = 'div, span, #status, #box { color: white !important; text-shadow: 1px 1px 2px black !important; }';
                document.head.appendChild(style);
            """)
            url = platform.window.location.href
            parsed = urllib.parse.urlparse(url)
            params = urllib.parse.parse_qs(parsed.query)
            class_id = params.get("class", ["DEFAULT"])[0]
        except Exception as e:
            print(f"Error reading URL parameters or setting styles: {e}")
    elif len(sys.argv) > 1:
        class_id = sys.argv[1]
    return class_id


def send_telemetry(class_id, player_id, player, state):
    """
    Sends an anonymised HTTP PUT request to Firebase Realtime Database using
    the student's integer array index (player_id) so no student names are ever
    stored in the database. Replaces prior status for that user.
    """
    if sys.platform != "emscripten" or not player:
        return
    if not FIREBASE_URL or "YOUR-FIREBASE-PROJECT-ID" in FIREBASE_URL:
        return

    safe_class = urllib.parse.quote(str(class_id).strip().upper())
    endpoint = f"{FIREBASE_URL.rstrip('/')}/classes/{safe_class}/players/{player_id}.json"

    payload = json.dumps({
        "id": player_id,
        "score": getattr(player, "score", 0),
        "inventory": list(getattr(player, "inventory", [])),
        "sin_binned": state == "sin_bin",
        "escaped": state == "victory",
        "updated_at": int(time.time()),
    })

    js_code = f"""
    fetch({json.dumps(endpoint)}, {{
        method: 'PUT',
        headers: {{ 'Content-Type': 'application/json' }},
        body: {json.dumps(payload)}
    }}).catch(function(err) {{ console.warn('Telemetry error:', err); }});
    """
    try:
        platform.window.eval(js_code)
    except Exception as e:
        print(f"Telemetry error: {e}")


def init_focus_tracker():
    """
    Registers persistent JavaScript blur and visibilitychange listeners on both
    window and window.top so focus loss is latched even if Chrome suspends
    requestAnimationFrame while the student is in another tab or snipping tool.
    """
    if sys.platform == "emscripten":
        try:
            platform.window.eval("""
                (function() {
                    if (window._heistTrackerInstalled) return;
                    window._heistTrackerInstalled = true;
                    window._heistFocusLost = false;
                    function markLost() { window._heistFocusLost = true; }
                    window.addEventListener('blur', markLost);
                    document.addEventListener('visibilitychange', function() {
                        if (document.hidden || document.visibilityState !== 'visible') {
                            window._heistFocusLost = true;
                        }
                    });
                    try {
                        if (window.top && window.top !== window) {
                            window.top.addEventListener('blur', markLost);
                            window.top.document.addEventListener('visibilitychange', function() {
                                if (window.top.document.hidden) window._heistFocusLost = true;
                            });
                        }
                    } catch (e) {}
                })();
            """)
        except Exception as e:
            print(f"[WARN] Could not install JS focus tracker: {e}")


def reset_focus_latch():
    if sys.platform == "emscripten":
        try:
            platform.window.eval("window._heistFocusLost = false;")
        except Exception as e:
            print(f"Error resetting focus latch in JS: {e}")


def check_browser_focus_lost():
    if sys.platform == "emscripten":
        try:
            res = platform.window.eval("""
                (function() {
                    var topHidden = false;
                    var topFocused = true;
                    try {
                        if (window.top && window.top !== window) {
                            topHidden = !!window.top.document.hidden;
                            topFocused = window.top.document.hasFocus();
                        }
                    } catch (e) {}
                    if (window._heistFocusLost || document.hidden || !document.hasFocus() || topHidden || !topFocused) {
                        window._heistFocusLost = false;
                        return "1";
                    }
                    return "0";
                })()
            """)
            return str(res) == "1"
        except Exception as e:
            print(f"Focus check error: {e}")
    return False
