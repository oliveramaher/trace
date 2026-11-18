import Foundation
import CoreGraphics
import AppKit

let types: [CGEventType] = [.leftMouseDown, .rightMouseDown, .otherMouseDown, .mouseMoved, .leftMouseDragged, .rightMouseDragged, .otherMouseDragged, .keyDown]
let mask = types.reduce(CGEventMask(0)) { $0 | (CGEventMask(1) << $1.rawValue) }
var start: CGPoint? = nil
var end: CGPoint? = nil
var typingCount = 0
var typingText = ""
var typingApp: NSRunningApplication? = nil
var moveApp: NSRunningApplication? = nil
func emit(_ fields: [String: Any], app: NSRunningApplication?) {
    guard let app = app, let name = app.localizedName else { return }
    var item = fields
    item["app"] = name
    item["pid"] = app.processIdentifier
    item["time"] = ISO8601DateFormatter().string(from: Date())
    if let data = try? JSONSerialization.data(withJSONObject: item), let line = String(data: data, encoding: .utf8) {
        print(line); fflush(stdout)
    }
}
func flushActivity() {
    if let a = start, let b = end {
        emit(["trigger":"movement", "from":[a.x,a.y], "to":[b.x,b.y]], app: moveApp)
    }
    start = nil; end = nil; moveApp = nil
    if typingCount > 0 { emit(["trigger":"typing", "count":typingCount, "text":typingText], app: typingApp) }
    typingCount = 0; typingText = ""; typingApp = nil
}
let callback: CGEventTapCallBack = { _, type, event, _ in
    if type == .tapDisabledByTimeout || type == .tapDisabledByUserInput {
        fputs("input event tap disabled; stopping\n", stderr); exit(1)
    }
    let app = NSWorkspace.shared.frontmostApplication
    if [.mouseMoved, .leftMouseDragged, .rightMouseDragged, .otherMouseDragged].contains(type) {
        if moveApp?.processIdentifier != app?.processIdentifier && start != nil { flushActivity() }
        if start == nil { start = event.location; moveApp = app }
        end = event.location
        return Unmanaged.passUnretained(event)
    }
    if type == .keyDown {
        let key = event.getIntegerValueField(.keyboardEventKeycode)
        let flags = event.flags
        let isShortcut = !flags.intersection([.maskCommand, .maskControl, .maskAlternate]).isEmpty
        if key != 36 && key != 76 && !isShortcut {
            if typingApp?.processIdentifier != app?.processIdentifier && typingCount > 0 { flushActivity() }
            typingApp = app; typingCount += 1
            var length = 0
            var characters = [UniChar](repeating: 0, count: 32)
            event.keyboardGetUnicodeString(maxStringLength: characters.count, actualStringLength: &length, unicodeString: &characters)
            if length > 0 {
                typingText += String(decoding: characters.prefix(min(length, characters.count)), as: UTF16.self)
            }
            return Unmanaged.passUnretained(event)
        }
        flushActivity()
        if event.getIntegerValueField(.keyboardEventAutorepeat) != 0 { return Unmanaged.passUnretained(event) }
        if isShortcut {
            var modifiers: [String] = []
            if flags.contains(.maskCommand) { modifiers.append("command") }
            if flags.contains(.maskControl) { modifiers.append("control") }
            if flags.contains(.maskAlternate) { modifiers.append("option") }
            if flags.contains(.maskShift) { modifiers.append("shift") }
            emit(["trigger":"shortcut", "keycode":key, "modifiers":modifiers], app:app)
        } else { emit(["trigger":"return"], app:app) }
    } else {
        flushActivity()
        let position = event.location
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.15) {
            emit(["trigger":"click", "position":[position.x,position.y]], app:NSWorkspace.shared.frontmostApplication)
        }
    }
    return Unmanaged.passUnretained(event)
}
guard let tap = CGEvent.tapCreate(tap: .cgSessionEventTap, place: .headInsertEventTap, options: .listenOnly, eventsOfInterest: mask, callback: callback, userInfo: nil) else {
    fputs("Unable to observe input. Grant Input Monitoring permission to the launching app.\n", stderr); exit(1)
}
let source = CFMachPortCreateRunLoopSource(kCFAllocatorDefault, tap, 0)
CFRunLoopAddSource(CFRunLoopGetCurrent(), source, .commonModes)
let timer = Timer(timeInterval: 0.5, repeats: true) { _ in flushActivity() }
RunLoop.current.add(timer, forMode: .common)
CGEvent.tapEnable(tap: tap, enable: true)
CFRunLoopRun()
