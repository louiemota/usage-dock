import Foundation
import SwiftUI

@MainActor
final class UsageStore: ObservableObject {
    @Published var providers: [ProviderUsage] = ProviderUsage.placeholders
    @Published var isLoading = false
    @Published var lastError: String?
    @Published var lastUpdated: Date?
    @Published var selectedID: String?
    /// Sempre começa expandido; recolher é estado de sessão, não persistido.
    @Published var collapsed = false
    @Published var coupledTrailing = true
    @Published var settingsOpen = false
    @Published private(set) var pinned = false

    private let pythonPath = "/Users/imac/Documents/subscription-widget/.venv/bin/python"
    private let scriptPath = "/Users/imac/Documents/usage-dock/collector.py"
    private var timer: Timer?
    private let interval: TimeInterval = 30

    private var pinnedID: String?
    private var hoveringRing: String?
    private var hoveringPopout = false
    private var isDragging = false
    private var hoverOpenTask: Task<Void, Never>?
    private var hoverCloseTask: Task<Void, Never>?
    /// Codenotch `hoverGrace` — abre o popout sem flicker.
    private static let hoverGraceOpen: UInt64 = 90_000_000
    private static let hoverGraceClose: UInt64 = 180_000_000

    init() {
        if let preset = ProcessInfo.processInfo.environment["USAGE_DOCK_SELECT"],
           providers.contains(where: { $0.id == preset }) {
            selectedID = preset
            pinnedID = preset
            pinned = true
        }
        startTimer()
        Task { await refresh() }
    }

    deinit {
        timer?.invalidate()
    }

    func startTimer() {
        timer?.invalidate()
        let t = Timer(timeInterval: interval, repeats: true) { [weak self] _ in
            Task { @MainActor in
                await self?.refresh()
            }
        }
        RunLoop.main.add(t, forMode: .common)
        timer = t
    }

    func select(_ id: String) {
        hoverOpenTask?.cancel()
        hoverCloseTask?.cancel()
        settingsOpen = false
        if pinnedID == id {
            pinnedID = nil
            pinned = false
            selectedID = nil
            return
        }
        pinnedID = id
        pinned = true
        selectedID = id
        Task { await refresh() }
    }

    func dismiss() {
        hoverOpenTask?.cancel()
        hoverCloseTask?.cancel()
        pinnedID = nil
        pinned = false
        hoveringRing = nil
        hoveringPopout = false
        selectedID = nil
    }

    func openSettings() {
        hoverOpenTask?.cancel()
        hoverCloseTask?.cancel()
        pinnedID = nil
        pinned = false
        selectedID = nil
        hoveringRing = nil
        hoveringPopout = false
        settingsOpen = true
    }

    func closeSettings() {
        settingsOpen = false
    }

    func setCollapsed(_ value: Bool) {
        collapsed = value
        if value {
            settingsOpen = false
            pinnedID = nil
            pinned = false
            hoveringRing = nil
            hoveringPopout = false
            selectedID = nil
        }
    }

    func pointerEnteredRing(_ id: String) {
        hoveringRing = id
        hoverCloseTask?.cancel()
        hoverOpenTask?.cancel()
        guard !collapsed, !isDragging, !settingsOpen else { return }
        if pinnedID == id, selectedID == id { return }
        if selectedID != nil, pinnedID == nil {
            selectedID = id
            return
        }
        hoverOpenTask = Task { @MainActor in
            try? await Task.sleep(nanoseconds: Self.hoverGraceOpen)
            guard !Task.isCancelled, !self.isDragging, self.hoveringRing == id else { return }
            self.selectedID = id
        }
    }

    func pointerExitedRing(_ id: String) {
        if isDragging { return }
        if hoveringRing == id { hoveringRing = nil }
        hoverOpenTask?.cancel()
        scheduleHoverClose()
    }

    func pointerEnteredPopout() {
        hoveringPopout = true
        hoverCloseTask?.cancel()
    }

    func pointerExitedPopout() {
        hoveringPopout = false
        scheduleHoverClose()
    }

    func beginDrag() {
        isDragging = true
        hoverOpenTask?.cancel()
        hoverCloseTask?.cancel()
        if pinnedID == nil {
            selectedID = nil
        } else {
            selectedID = pinnedID
        }
    }

    func endDrag() {
        isDragging = false
        if let id = hoveringRing, !collapsed {
            pointerEnteredRing(id)
        }
    }

    func refresh() async {
        guard !isLoading else { return }
        isLoading = true
        lastError = nil
        do {
            let data = try await runCollector()
            let payload = try JSONDecoder().decode(CollectorPayload.self, from: data)
            apply(payload.providers)
            lastUpdated = Date()
            if selectedID == nil,
               let preset = ProcessInfo.processInfo.environment["USAGE_DOCK_SELECT"],
               providers.contains(where: { $0.id == preset }) {
                selectedID = preset
                pinnedID = preset
                pinned = true
            }
        } catch {
            lastError = error.localizedDescription
        }
        isLoading = false
    }

    private func apply(_ incoming: [ProviderUsage]) {
        let byID = Dictionary(incoming.map { ($0.id, $0) }, uniquingKeysWith: { _, last in last })
        providers = ProviderUsage.placeholders.map { slot in
            byID[slot.id] ?? providers.first(where: { $0.id == slot.id }) ?? slot
        }
    }

    private func scheduleHoverClose() {
        hoverCloseTask?.cancel()
        hoverCloseTask = Task { @MainActor in
            try? await Task.sleep(nanoseconds: Self.hoverGraceClose)
            guard !Task.isCancelled else { return }
            guard hoveringRing == nil, !hoveringPopout, !isDragging else { return }
            if let pinnedID {
                selectedID = pinnedID
            } else {
                selectedID = nil
            }
        }
    }

    private func runCollector() async throws -> Data {
        try await withCheckedThrowingContinuation { continuation in
            DispatchQueue.global(qos: .userInitiated).async {
                let process = Process()
                process.executableURL = URL(fileURLWithPath: self.pythonPath)
                process.arguments = [self.scriptPath]
                let out = Pipe()
                let err = Pipe()
                process.standardOutput = out
                process.standardError = err
                var env = ProcessInfo.processInfo.environment
                env["PYTHONUNBUFFERED"] = "1"
                process.environment = env
                do {
                    try process.run()
                    let deadline = Date().addingTimeInterval(25)
                    while process.isRunning, Date() < deadline {
                        Thread.sleep(forTimeInterval: 0.05)
                    }
                    if process.isRunning {
                        process.terminate()
                        continuation.resume(throwing: CollectorError.failed(1, "coletor travou (>25s)"))
                        return
                    }
                    process.waitUntilExit()
                    let data = out.fileHandleForReading.readDataToEndOfFile()
                    if process.terminationStatus != 0 {
                        let message = String(data: err.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8) ?? ""
                        continuation.resume(throwing: CollectorError.failed(process.terminationStatus, message))
                    } else {
                        continuation.resume(returning: data)
                    }
                } catch {
                    continuation.resume(throwing: error)
                }
            }
        }
    }

    enum CollectorError: LocalizedError {
        case failed(Int32, String)
        var errorDescription: String? {
            switch self {
            case .failed(let code, let message):
                let tail = message.trimmingCharacters(in: .whitespacesAndNewlines)
                if tail.isEmpty {
                    return "coletor falhou (\(code))"
                }
                return String(tail.prefix(180))
            }
        }
    }
}
