#!/usr/bin/env python3
"""Record accessibility snapshots on input; write JSON lines to stdout."""
import argparse
import datetime
import json
import signal
import subprocess
import sys
import time
from pathlib import Path


def comparable(value):
    """Discard snapshot-scoped identifiers while preserving visible state."""
    if isinstance(value, dict):
        return {k: comparable(v) for k, v in value.items() if k not in ("snapshot_id", "ref_id")}
    if isinstance(value, list):
        return [comparable(v) for v in value]
    return value


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--app', action='append', help='App to observe in polling mode; repeat for multiple apps')
    p.add_argument('--interval', type=float, default=2, help='Seconds between polling rounds')
    p.add_argument('--window-id', help='Select one window when an app has multiple windows')
    p.add_argument('--binary', default='agent-desktop')
    p.add_argument('--timeout', type=float, default=10)
    p.add_argument('--on-input', metavar='HELPER', help='Use an existing compiled input helper')
    args = p.parse_args()
    event_mode = args.on_input is not None or not args.app
    if args.on_input and (args.app or args.window_id):
        p.error('--on-input uses the foreground app and cannot be combined with --app or --window-id')
    if event_mode and args.window_id:
        p.error('--window-id requires --app')
    if args.interval <= 0 or args.timeout <= 0:
        p.error('interval and timeout must be positive')
    stopped = False
    previous = {}
    helper = None
    def stop(_signum, _frame):
        nonlocal stopped
        stopped = True
        if helper and helper.poll() is None:
            helper.terminate()
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    if event_mode:
        helper_path = args.on_input
        if not helper_path:
            source = Path(__file__).resolve().with_name('input_events.swift')
            build_dir = Path(__file__).resolve().parent / '.trace-build'
            helper_path = build_dir / 'input-events'
            try:
                build_dir.mkdir(mode=0o700, exist_ok=True)
                if not helper_path.exists() or source.stat().st_mtime_ns > helper_path.stat().st_mtime_ns:
                    print('building input observer...', file=sys.stderr, flush=True)
                    subprocess.run(['swiftc', '-module-cache-path', str(build_dir / 'module-cache'), str(source), '-o', str(helper_path)], check=True)
            except (OSError, subprocess.CalledProcessError) as exc:
                p.error(f'could not build input observer: {exc}')
        try:
            helper = subprocess.Popen([str(helper_path)], stdout=subprocess.PIPE, text=True)
        except OSError as exc:
            p.error(str(exc))
        print('trace is running; press ctrl-c to stop. input and snapshots may contain passwords or private text.', file=sys.stderr, flush=True)
    while not stopped:
        trigger = None
        if helper:
            line = helper.stdout.readline().strip()
            if not line:
                break
            try:
                trigger = json.loads(line)
                app_name = trigger['app']
                pid = trigger['pid']
            except (ValueError, KeyError, TypeError):
                print('Invalid input helper event', file=sys.stderr)
                continue
        if trigger:
            print(json.dumps({'type': 'input', **trigger}, ensure_ascii=False), flush=True)
            if trigger['trigger'] not in ('click', 'return', 'shortcut', 'key'):
                continue
        start = time.monotonic()
        for app in ([app_name] if helper else args.app):
            if stopped:
                break
            event = {'type': 'snapshot', 'time': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'app': app}
            if trigger:
                event['trigger'] = trigger['trigger']
                event['pid'] = pid
            try:
                if helper:
                    listing = subprocess.run([args.binary, 'list-windows', '--app', app], capture_output=True, text=True, timeout=args.timeout)
                    windows = json.loads(listing.stdout)
                    matches = [w for w in windows.get('data', []) if w.get('pid') == pid and w.get('is_focused') and w.get('accessible')]
                    if listing.returncode or not windows.get('ok') or len(matches) != 1:
                        raise ValueError('Could not identify a unique focused accessible window')
                    window_id = matches[0]['id']
                else:
                    window_id = args.window_id
                command = [args.binary, 'snapshot', '--app', app, '-i', '--compact']
                if window_id:
                    command.extend(['--window-id', window_id])
                result = subprocess.run(command, capture_output=True, text=True, timeout=args.timeout)
                event['exit_code'] = result.returncode
                try:
                    event['observation'] = json.loads(result.stdout)
                except json.JSONDecodeError:
                    event['error'] = 'Invalid JSON response from agent-desktop'
            except (ValueError, KeyError, TypeError) as exc:
                event['error'] = str(exc)
            except subprocess.TimeoutExpired:
                event['error'] = 'Snapshot timed out'
            except OSError as exc:
                event['error'] = str(exc)
                stopped = True
            observation = event.get("observation", {})
            if event.get("exit_code") == 0 and observation.get("ok"):
                current = comparable(observation.get("data"))
                if (app, event.get("pid")) in previous and previous.get((app, event.get("pid"))) == current:
                    continue
                previous[(app, event.get("pid"))] = current
            else:
                previous.pop((app, event.get("pid")), None)
            print(json.dumps(event, ensure_ascii=False), flush=True)
        remaining = args.interval - (time.monotonic() - start)
        if remaining > 0 and not stopped and not helper:
            time.sleep(remaining)
    if helper:
        if helper.poll() is None:
            helper.terminate()
        helper.wait()
        if not stopped and helper.returncode:
            return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
