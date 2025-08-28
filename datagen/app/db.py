import sqlite3
import os, stat
from .constants import DB_PATH
from .queries import CREATE_TABLES

def _fmt_mode(mode: int) -> str:
    return stat.filemode(mode)  # e.g. '-rw-r--r--'

def _stat_summary(path: str) -> str:
    try:
        st = os.stat(path, follow_symlinks=True)
        return f"exists mode={_fmt_mode(st.st_mode)} uid={st.st_uid} gid={st.st_gid}"
    except FileNotFoundError:
        return "does NOT exist"
    except Exception as e:
        return f"stat error: {type(e).__name__}: {e}"

def _writability_summary(dirpath: str) -> str:
    can_w = os.access(dirpath, os.W_OK)
    can_x = os.access(dirpath, os.X_OK)  # needed to create files
    msg = f"os.access(W_OK={can_w}, X_OK={can_x})"
    # Try an actual write test, which catches SELinux/ACL surprises
    test_path = os.path.join(dirpath, f".write-test-{os.getpid()}")
    try:
        with open(test_path, "w") as f:
            f.write("ok")
        os.remove(test_path)
        msg += " | write_test=OK"
    except Exception as e:
        msg += f" | write_test=FAIL ({type(e).__name__}: {e})"
    return msg

def get_db():
    db_path = DB_PATH
    db_dir = os.path.dirname(db_path or "") or "."
    print("=== SQLite debug ===")
    print(f"ENV DB_PATH: {db_path}")
    print(f"Process uid/gid: {os.geteuid()}:{os.getegid()}")
    print(f"DB file: {db_path} -> {_stat_summary(db_path)}")
    print(f"DB dir : {db_dir} -> {_stat_summary(db_dir)}")

    # Ensure directory exists
    if not os.path.isdir(db_dir):
        try:
            os.makedirs(db_dir, exist_ok=True)
            print(f"Created DB dir: {db_dir}")
        except Exception as e:
            print(f"ERROR: Failed to create DB dir {db_dir}: {type(e).__name__}: {e}")
            raise

    # Check writability of dir
    print(f"Dir writability: {_writability_summary(db_dir)}")

    # If file exists, check writability of the file itself
    if os.path.exists(db_path):
        can_write_file = os.access(db_path, os.W_OK)
        try:
            with open(db_path, "a"):
                pass
            append_ok = True
        except Exception as e:
            append_ok = False
            print(f"File append test: FAIL ({type(e).__name__}: {e})")
        print(f"File writable: os.access(W_OK={can_write_file}) | append_test={append_ok}")

    print(f"Connecting to SQLite @ {db_path} ...")
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        print("SQLite connect: OK")
        return conn
    except sqlite3.OperationalError as e:
        # Enrich error with common hints
        err_no = getattr(e, "errno", None)
        print(f"SQLite connect: OperationalError (errno={err_no}) -> {e}")
        print("HINTS:")
        print(" - Ensure the container user owns the mounted directory or has write perms.")
        print(" - On SELinux hosts, use ':Z' on the bind mount (e.g., -v ./data:/data:Z).")
        print(" - Or run with '--user $(id -u):$(id -g)' to match host permissions.")
        raise

def init_db():
    conn = get_db()
    try:
        cur = conn.cursor()
        for ddl in CREATE_TABLES:
            cur.execute(ddl)
        conn.commit()
    finally:
        conn.close()
