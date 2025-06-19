import subprocess
import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

PROCS = [
    [sys.executable, os.path.join(PROJECT_ROOT, 'src', 'server_http.py')],
    [sys.executable, os.path.join(PROJECT_ROOT, 'src', 'chat_api.py')],
    [sys.executable, os.path.join(PROJECT_ROOT, 'src', 'auth', 'auth_api.py')],
]

def main():
    print("Starting all Flask servers: server_http.py, chat_api.py, and auth_api.py ...")
    procs = []
    try:
        for cmd in PROCS:
            proc = subprocess.Popen(cmd)
            print(f"Started {' '.join(cmd)} with PID {proc.pid}")
            procs.append(proc)
        print("\nAll servers are running. Press Ctrl+C to stop them.")
        while True:
            for proc in procs:
                if proc.poll() is not None:
                    print(f"Process {proc.pid} exited unexpectedly.")
                    procs.remove(proc)
            if not procs:
                print("All servers have exited.")
                break
    except KeyboardInterrupt:
        print("\nShutting down servers...")
        for proc in procs:
            proc.terminate()
        for proc in procs:
            proc.wait()
        print("All servers stopped.")

if __name__ == '__main__':
    main() 