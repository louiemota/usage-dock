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
        NSApp.setActivationPolicy(.accessory)
        overlay = OverlayController(store: store)
        overlay?.show()
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        false
    }
}
