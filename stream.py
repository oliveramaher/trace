#!/usr/bin/env python3
"""Poll agent-desktop snapshots and emit newline-delimited observations."""
import argparse
import datetime
import json
import signal
import subprocess
import sys
import time


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--app', action='append', required=True, help='App to observe; repeat for multiple apps')
    p.add_argument('--interval', type=float, default=2, help='Seconds between polling rounds')
    p.add_argument('--window-id', help='Select one window when an app has multiple windows')
    p.add_argument('--binary', default='agent-desktop')
    p.add_argument('--timeout', type=float, default=10)
    args = p.parse_args()
    if args.interval <= 0 or args.timeout <= 0:
        p.error('interval and timeout must be positive')
    stopped = False
    def stop(_signum, _frame):
        nonlocal stopped
        stopped = True
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    while not stopped:
        start = time.monotonic()
        for app in args.app:
            if stopped:
                break
            event = {'time': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'app': app}
            try:
                command = [args.binary, 'snapshot', '--app', app, '-i', '--compact']
                if args.window_id:
                    command.extend(['--window-id', args.window_id])
                result = subprocess.run(command, capture_output=True, text=True, timeout=args.timeout)
                event['exit_code'] = result.returncode
                try:
                    event['observation'] = json.loads(result.stdout)
                except json.JSONDecodeError:
                    event['error'] = 'Invalid JSON response from agent-desktop'
            except subprocess.TimeoutExpired:
                event['error'] = 'Snapshot timed out'
            except OSError as exc:
                event['error'] = str(exc)
                stopped = True
            print(json.dumps(event, ensure_ascii=False), flush=True)
        remaining = args.interval - (time.monotonic() - start)
        if remaining > 0 and not stopped:
            time.sleep(remaining)
    return 0


if __name__ == '__main__':
    sys.exit(main())
