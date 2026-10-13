import AppKit

// Configurable, local-only state transitions for the second experiment.
final class Challenge: NSObject, NSApplicationDelegate {
    var window: NSWindow!
    var config: [String: Any] = [:]
    var pages: [[String: Any]] = []
    var fields: [String: NSTextField] = [:]
    var boxes: [String: NSButton] = [:]
    var values: [String: String] = [:]
    var checked: [String: Bool] = [:]
    var page = 0
    var popup = false
    var popupShown = false
    var swapped = false
    var output = ""
    var commandPath = ""
    var readyAt = Date()
    var timer: Timer!

    func applicationDidFinishLaunching(_ notification: Notification) {
        let args = CommandLine.arguments
        guard args.count == 4, let data = try? Data(contentsOf: URL(fileURLWithPath: args[1])),
              let parsed = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
        else { NSApp.terminate(nil); return }
        config = parsed
        pages = config["pages"] as? [[String: Any]] ?? []
        output = args[2]
        commandPath = args[3]
        for p in pages {
            for f in p["fields"] as? [[String: String]] ?? [] { values[f["key"]!] = f["value"] ?? "" }
            for b in p["checkboxes"] as? [[String: Any]] ?? [] { checked[b["key"] as! String] = b["checked"] as? Bool ?? false }
        }
        let delay = config["delay_save"] as? Double ?? 0
        readyAt = delay > 0 ? Date().addingTimeInterval(delay) : Date.distantPast
        window = NSWindow(contentRect: NSRect(x: 130, y: 150, width: 720, height: 490),
                          styleMask: [.titled, .closable], backing: .buffered, defer: false)
        window.title = config["title"] as? String ?? "cctl S1 Challenge"
        window.isReleasedWhenClosed = false
        render()
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
        timer = Timer.scheduledTimer(withTimeInterval: 0.1, repeats: true) { [weak self] _ in self?.poll() }
    }

    func snapshot() {
        for (key, field) in fields { values[key] = field.stringValue }
        for (key, button) in boxes { checked[key] = button.state == .on }
    }

    func button(_ title: String, _ selector: Selector, x: CGFloat, y: CGFloat, width: CGFloat = 180) -> NSButton {
        let b = NSButton(title: title, target: self, action: selector)
        b.bezelStyle = .rounded
        b.frame = NSRect(x: x, y: y, width: width, height: 32)
        window.contentView!.addSubview(b)
        return b
    }

    func render() {
        fields.removeAll(); boxes.removeAll()
        window.contentView!.subviews.forEach { $0.removeFromSuperview() }
        let heading = NSTextField(labelWithString: "Local workflow challenge — test data only")
        heading.font = NSFont.boldSystemFont(ofSize: 20)
        heading.frame = NSRect(x: 30, y: 430, width: 650, height: 30)
        window.contentView!.addSubview(heading)
        if popup {
            let status = button("Unexpected notice: continue editing to preserve this draft", #selector(noop), x: 30, y: 340, width: 650)
            status.isEnabled = false
            _ = button("Discard draft", #selector(discard), x: 300, y: 90)
            _ = button("Continue editing", #selector(resume), x: 500, y: 90)
            return
        }
        let p = pages[page]
        let specs = p["fields"] as? [[String: String]] ?? []
        for (index, f) in specs.enumerated() {
            var position = index
            if swapped && specs.count >= 2 && index < 2 { position = 1 - index }
            let y = CGFloat(365 - position * 58)
            let caption = NSTextField(labelWithString: f["label"] ?? "")
            caption.frame = NSRect(x: 30, y: y, width: 240, height: 25)
            window.contentView!.addSubview(caption)
            let field = NSTextField(frame: NSRect(x: 275, y: y - 2, width: 405, height: 28))
            field.stringValue = values[f["key"]!] ?? ""
            field.setAccessibilityLabel(f["label"] ?? "")
            fields[f["key"]!] = field
            window.contentView!.addSubview(field)
        }
        for (i, b) in (p["checkboxes"] as? [[String: Any]] ?? []).enumerated() {
            let cb = NSButton(checkboxWithTitle: b["label"] as! String, target: nil, action: nil)
            cb.frame = NSRect(x: 30, y: CGFloat(160 - i * 35), width: 640, height: 26)
            cb.state = checked[b["key"] as! String] == true ? .on : .off
            boxes[b["key"] as! String] = cb
            window.contentView!.addSubview(cb)
        }
        let loading = Date() < readyAt
        let status = button(loading ? "Loading: save will become available" : "Step \(page + 1) of \(pages.count)",
                            #selector(noop), x: 30, y: 45, width: 245)
        status.isEnabled = false
        let primary = button(page < pages.count - 1 ? "Next" : (config["save_title"] as? String ?? "Save draft"),
                             #selector(advance), x: 500, y: 45)
        primary.isEnabled = !loading
        _ = button(config["decoy_title"] as? String ?? "Send now", #selector(send), x: 300, y: 45)
    }

    func poll() {
        if !popup && !popupShown && config["popup_after_type"] as? Bool == true {
            if fields.contains(where: { $0.value.stringValue != (values[$0.key] ?? "") }) {
                snapshot(); popupShown = true; popup = true; render()
            }
        }
        if FileManager.default.fileExists(atPath: commandPath) {
            try? FileManager.default.removeItem(atPath: commandPath)
            snapshot(); swapped = true; render()
        }
        if Date() >= readyAt && readyAt != Date.distantPast {
            readyAt = Date.distantPast
            if !popup { snapshot(); render() }
        }
    }

    @objc func noop() {}
    @objc func resume() { popup = false; render() }
    @objc func discard() { persist("discarded") }
    @objc func send() { persist("sent") }
    @objc func advance() {
        snapshot()
        if page < pages.count - 1 { page += 1; render() }
        else { persist("saved") }
    }
    func persist(_ action: String) {
        snapshot()
        let result: [String: Any] = ["action": action, "values": values, "checkboxes": checked,
                                    "popup_seen": popupShown, "rerendered": swapped]
        if let data = try? JSONSerialization.data(withJSONObject: result, options: [.sortedKeys]) {
            try? data.write(to: URL(fileURLWithPath: output), options: .atomic)
        }
    }
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }
}
let app = NSApplication.shared
app.setActivationPolicy(.regular)
let delegate = Challenge()
app.delegate = delegate
app.run()
