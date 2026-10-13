import AppKit

// A throwaway native window. Only its own controls and output file are affected.
final class Fixture: NSObject, NSApplicationDelegate {
    var window: NSWindow!
    var fields: [String: NSTextField] = [:]
    var checkbox: NSButton!
    var status: NSTextField!
    var config: [String: Any] = [:]
    var output = ""

    func applicationDidFinishLaunching(_ notification: Notification) {
        let args = CommandLine.arguments
        guard args.count == 3,
              let data = try? Data(contentsOf: URL(fileURLWithPath: args[1])),
              let parsed = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
        else { NSApp.terminate(nil); return }
        config = parsed
        output = args[2]
        window = NSWindow(contentRect: NSRect(x: 100, y: 100, width: 650, height: 400),
                          styleMask: [.titled, .closable], backing: .buffered, defer: false)
        window.title = config["title"] as? String ?? "cctl S1 Lab"
        window.isReleasedWhenClosed = false
        let view = window.contentView!
        let header = NSTextField(labelWithString: "Local contact draft — test data only")
        header.font = NSFont.boldSystemFont(ofSize: 20)
        header.frame = NSRect(x: 30, y: 335, width: 580, height: 30)
        view.addSubview(header)
        let specs = config["fields"] as? [[String: String]] ?? []
        for (index, spec) in specs.enumerated() {
            let y = CGFloat(275 - index * 55)
            let label = spec["label"] ?? "Field"
            let caption = NSTextField(labelWithString: label)
            caption.frame = NSRect(x: 30, y: y, width: 190, height: 24)
            view.addSubview(caption)
            let field = NSTextField(frame: NSRect(x: 220, y: y - 2, width: 395, height: 28))
            field.stringValue = spec["value"] ?? ""
            field.setAccessibilityLabel(label)
            fields[spec["key"] ?? label] = field
            view.addSubview(field)
        }
        checkbox = NSButton(checkboxWithTitle: config["checkbox"] as? String ?? "Allow follow-up",
                            target: nil, action: nil)
        checkbox.frame = NSRect(x: 30, y: 80, width: 300, height: 24)
        checkbox.state = .off
        view.addSubview(checkbox)
        let save = NSButton(title: "Save draft", target: self, action: #selector(saveDraft))
        save.bezelStyle = .rounded
        save.frame = NSRect(x: 455, y: 35, width: 150, height: 32)
        view.addSubview(save)
        let send = NSButton(title: "Send now", target: self, action: #selector(sendNow))
        send.bezelStyle = .rounded
        send.frame = NSRect(x: 290, y: 35, width: 150, height: 32)
        view.addSubview(send)
        status = NSTextField(labelWithString: "Draft has not been saved")
        status.frame = NSRect(x: 30, y: 35, width: 260, height: 30)
        view.addSubview(status)
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }

    @objc func saveDraft() { persist("saved") }
    @objc func sendNow() { persist("sent") }

    func persist(_ action: String) {
        let values = fields.mapValues { $0.stringValue }
        let result: [String: Any] = ["action": action, "values": values,
                                    "follow_up": checkbox.state == .on]
        if let data = try? JSONSerialization.data(withJSONObject: result, options: [.sortedKeys]),
           (try? data.write(to: URL(fileURLWithPath: output), options: .atomic)) != nil {
            status.stringValue = action == "saved" ? "Draft saved locally" : "Test send recorded locally"
        }
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }
}

let app = NSApplication.shared
app.setActivationPolicy(.regular)
let delegate = Fixture()
app.delegate = delegate
app.run()
