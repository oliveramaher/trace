#!/usr/bin/env python3
"""Display a Trace JSONL session as a readable timeline."""
import argparse
import datetime
import json


def elements(node):
    if isinstance(node, dict):
        role = node.get('role')
        name = node.get('name')
        if role and name:
            yield role, str(name)
        for child in node.get('children', []):
            yield from elements(child)
    elif isinstance(node, list):
        for child in node:
            yield from elements(child)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('log', help='Path to a Trace JSONL file')
    args = parser.parse_args()
    with open(args.log, encoding='utf-8') as source:
        for number, line in enumerate(source, 1):
            try:
                item = json.loads(line)
                timestamp = item.get('time', '?')
                try:
                    timestamp = datetime.datetime.fromisoformat(timestamp.replace('Z', '+00:00')).astimezone().strftime('%H:%M:%S')
                except (ValueError, AttributeError):
                    pass
                print(f"\n{timestamp}  {item.get('app', '?')}")
                if item.get('type') == 'input':
                    kind = item.get('trigger', '?')
                    if kind == 'typing': print(f"  typed: {item.get('text', '[not recorded]')!r} ({item.get('count', '?')} keys)")
                    elif kind == 'movement': print(f"  mouse: {item.get('from')} → {item.get('to')}")
                    elif kind == 'shortcut': print(f"  shortcut: {' + '.join(item.get('modifiers', []))} + keycode {item.get('keycode', '?')}")
                    else: print(f"  {kind}: {item.get('position', '')}")
                    continue
                observation = item.get('observation', {})
                if not observation.get('ok'):
                    print(f"  error: {item.get('error') or observation.get('error', {}).get('message', 'unknown')}")
                    continue
                data = observation.get('data', {})
                print(f"  snapshot: {data.get('window', {}).get('title', '(window unavailable)')}")
                for role, name in elements(data.get('tree', {})):
                    print(f"    {role}: {name}")
            except (ValueError, TypeError) as exc:
                print(f'line {number}: unable to read record ({exc})')


if __name__ == '__main__':
    main()
