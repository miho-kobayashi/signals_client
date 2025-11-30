# -*- coding: utf-8 -*-
"""
signals_client_writer.py
- クライアント側用：あなたのVPS(217.146.81.83)からシグナルCSVを定期取得して、
  ローカルの infer_daemon_rel\out\signals_out.csv を上書きするだけのスクリプト。
- EA(AI_Bridge_Infer_M5.mq4) は、その signals_out.csv を読んで売買する。

使い方（例）:
  1) MT4 の MQL4\Files\infer_daemon_rel フォルダにこのファイルを置く
  2) Python で
       cd そのフォルダ
       python signals_client_writer.py
     を実行（止めるときは Ctrl+C）
"""

import os
import sys
import time
import datetime
try:
    from urllib.request import urlopen
    from urllib.error import URLError, HTTPError
except ImportError:
    # かなり古い環境向け保険
    import urllib2
    urlopen = urllib2.urlopen
    URLError = urllib2.URLError
    HTTPError = urllib2.HTTPError

# ===== 設定ここだけ変えればOK ==============================

# ★ あなたの VPS 上の FastAPI サーバ
SERVER_URL = "http://217.146.81.83:8000/signals"

# 何秒ごとに取りに行くか（EA の OnTimer が1秒なので、ここは5秒くらいで十分）
POLL_SEC = 5.0
HTTP_TIMEOUT_SEC = 10.0

# ===== パス解決（PyInstaller/生Python 両対応） ==============

FROZEN = getattr(sys, "frozen", False)
if FROZEN:
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# EA 側は InpOutCsvRel="infer_daemon_rel\\out\\signals_out.csv"
# → このスクリプトを infer_daemon_rel に置く前提で out/signals_out.csv に出力
OUT_DIR = os.path.join(BASE_DIR, "out")
OUT_CSV = os.path.join(OUT_DIR, "signals_out.csv")

def ensure_dir(path):
    d = path if os.path.splitext(path)[1] == "" else os.path.dirname(path)
    if d and not os.path.exists(d):
        os.makedirs(d, exist_ok=True)

def log(msg):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print("[CLIENT %s] %s" % (now, msg))
    sys.stdout.flush()

def fetch_signals():
    """
    VPS の /signals から CSV テキストを取得して、そのまま返す
    """
    try:
        resp = urlopen(SERVER_URL, timeout=HTTP_TIMEOUT_SEC)
        # Python2/3 両対応
        status = getattr(resp, "status", None)
        if status is None:
            # Python2系だと .getcode()
            status = resp.getcode()
        if status != 200:
            raise HTTPError(SERVER_URL, status, "non-200", hdrs=None, fp=None)

        body = resp.read()
        if isinstance(body, bytes):
            body = body.decode("utf-8", errors="replace")
        return body
    except HTTPError as e:
        log("HTTPError: code=%s" % getattr(e, "code", "unknown"))
    except URLError as e:
        log("URLError: %s" % (e,))
    except Exception as e:
        log("ERROR: %r" % (e,))
    return None

def main():
    log("=== signals_client_writer START ===")
    log("BASE_DIR = %s" % BASE_DIR)
    log("SERVER_URL = %s" % SERVER_URL)
    log("OUT_CSV   = %s" % OUT_CSV)

    ensure_dir(OUT_CSV)

    last_hash = None  # 同じ内容なら書き換えをスキップするための簡易ハッシュ

    try:
        while True:
            csv_text = fetch_signals()
            if csv_text is None:
                # 失敗したので次のループまで待機
                time.sleep(POLL_SEC)
                continue

            # 余計な改行の調整（最後に必ず改行を1つ付ける）
            csv_text_norm = csv_text.rstrip("\r\n") + "\n"

            cur_hash = hash(csv_text_norm)
            if cur_hash == last_hash:
                # 内容変わらず → EA 側は state を持っているので特に書き直さなくても良い
                log("no change in signals (skip write)")
            else:
                # 一時ファイルに書いてから atomically 置き換え
                tmp = OUT_CSV + ".tmp"
                with open(tmp, "w", encoding="utf-8", newline="") as f:
                    f.write(csv_text_norm)
                os.replace(tmp, OUT_CSV)
                last_hash = cur_hash

                # 行数をログに出す
                lines = [ln for ln in csv_text_norm.splitlines() if ln.strip()]
                n_lines = max(0, len(lines) - 1)  # ヘッダー除く件数
                log("updated signals_out.csv (%d signals)" % n_lines)

            time.sleep(POLL_SEC)

    except KeyboardInterrupt:
        log("Interrupted by user (Ctrl+C). Bye.")
        return

if __name__ == "__main__":
    main()
