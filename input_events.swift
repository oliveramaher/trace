import Foundation
import CoreGraphics
import AppKit

let mask = (1 << CGEventType.leftMouseDown.rawValue) | (1 << CGEventType.rightMouseDown.rawValue) | (1 << CGEventType.otherMouseDown.rawValue) | (1 << CGEventType.keyDown.rawValue)
let callback: CGEventTapCallBack = { _, type, event, _ in
    if type == .tapDisabledByTimeout || type == .tapDisabledByUserInput {
        fputs("input event tap disabled; stopping\n", stderr)
        exit(1)
    }
    if type == .keyDown {
        if event.getIntegerValueField(.keyboardEventAutorepeat) != 0 { return Unmanaged.passUnretained(event) }
        let key = event.getIntegerValueField(.keyboardEventKeycode)
        let shortcuts: CGEventFlags = [.maskCommand, .maskControl, .maskAlternate]
        if key != 36 && key != 76 && event.flags.intersection(shortcuts).isEmpty {
            return Unmanaged.passUnretained(event)
        }
    }
    let trigger = type == .keyDown ? "key" : "click"
    // Allow the target app to receive the event and become frontmost first.
    DispatchQueue.main.asyncAfter(deadline: .now() + 0.15) {
        guard let app = NSWorkspace.shared.frontmostApplication,
              let name = app.localizedName else { return }
        let event: [String: Any] = ["trigger": trigger, "app": name, "pid": app.processIdentifier]
        if let data = try? JSONSerialization.data(withJSONObject: event),
           let line = String(data: data, encoding: .utf8) {
            print(line)
            fflush(stdout)
        }
    }
    return Unmanaged.passUnretained(event)
}
guard let tap = CGEvent.tapCreate(tap: .cgSessionEventTap, place: .headInsertEventTap, options: .listenOnly, eventsOfInterest: CGEventMask(mask), callback: callback, userInfo: nil) else {
    fputs("Unable to observe input. Grant Input Monitoring permission to the launching app.\n", stderr)
    exit(1)
}
let source = CFMachPortCreateRunLoopSource(kCFAllocatorDefault, tap, 0)
CFRunLoopAddSource(CFRunLoopGetCurrent(), source, .commonModes)
CGEvent.tapEnable(tap: tap, enable: true)
CFRunLoopRun()
