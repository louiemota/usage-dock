import AppKit
import SwiftUI

@main
struct UsageDockApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var appDelegate

    var body: some Scene {
        Settings {
            VStack(alignment: .leading, spacing: 8) {
                Text("Usage Dock")
                    .font(.headline)
                Text("0–39% verde · 40–69% amarelo · 70–89% laranja · 90–100% vermelho")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            .padding(20)
            .frame(width: 360)
        }
    }
}

@MainActor
final class AppDelegate: NSObject, NSApplicationDelegate {
    let store = UsageStore()
    var overlay: OverlayController?

    func applicationDidFinishLaunching(_ notification: Notification) {
        if handOffToCanonicalIfNeeded() { return }
        terminateOtherInstances()
        NSApp.setActivationPolicy(.accessory)
        overlay = OverlayController(store: store)
        overlay?.show()
    }

    /// Documents está sob File Provider: no reboot o Mac às vezes abre uma cópia velha.
    /// Se Applications tiver versão maior, passa o live pra lá.
    private func handOffToCanonicalIfNeeded() -> Bool {
        let canonical = AppDelegate.canonicalApp
        let here = Bundle.main.bundlePath
        guard here != canonical, FileManager.default.fileExists(atPath: canonical) else {
            return false
        }
        guard bundleVersion(at: canonical) > bundleVersion(at: here) else { return false }
        NSWorkspace.shared.open(URL(fileURLWithPath: canonical))
        DispatchQueue.main.async {
            NSApp.terminate(nil)
        }
        return true
    }

    private func bundleVersion(at path: String) -> Int {
        let plist = (path as NSString).appendingPathComponent("Contents/Info.plist")
        guard let raw = NSDictionary(contentsOfFile: plist)?["CFBundleVersion"] as? String,
              let value = Int(raw) else { return 0 }
        return value
    }

    private static let canonicalApp = "/Users/imac/Applications/UsageDock.app"

    private func terminateOtherInstances() {
        let mine = ProcessInfo.processInfo.processIdentifier
        let bundleID = Bundle.main.bundleIdentifier ?? "com.louiemota.usagedock"
        for app in NSRunningApplication.runningApplications(withBundleIdentifier: bundleID) where app.processIdentifier != mine {
            app.terminate()
        }
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        false
    }
}
