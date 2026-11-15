import AppKit
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
    /// Provider sem login/assinatura sai da fila e some do HUD.
    @Published private(set) var skippedIDs: Set<String> = []

    private let pythonPath = "/Users/imac/Documents/subscription-widget/.venv/bin/python"
    private let scriptPath = "/Users/imac/Documents/usage-dock/collector.py"
    private var pulseSource: DispatchSourceTimer?
    private var wakeObserver: NSObjectProtocol?
    private var screensWakeObserver: NSObjectProtocol?
    private var sessionObserver: NSObjectProtocol?
    private var loadingStartedAt: Date?
    /// 60s while the HUD is in use, 5 min idle. Timer de RunLoop morria depois do sono.
    private static let busyInterval: TimeInterval = 60
    private static let idleInterval: TimeInterval = 300
    private static let pulseEvery: TimeInterval = 15
    private static let loadingDeadline: TimeInterval = 20
    private static let staleAfter: TimeInterval = 180
    private static let skippedIDsKey = "usageDock.skippedIDs"
    private static let skippedReasonsKey = "usageDock.skippedReasons"
    private var skippedReasons: [String: String] = [:]

    private var pinnedID: String?
    private var hoveringRing: String?
    private var hoveringPopout = false
    private var isDragging = false
    private var hoverOpenTask: Task<Void, Never>?
    private var hoverCloseTask: Task<Void, Never>?
    /// Atraso do hover: abre o popout sem flicker.
    private static let hoverGraceOpen: UInt64 = 90_000_000
    private static let hoverGraceClose: UInt64 = 180_000_000

    var parked: [ParkedProvider] {
        ProviderUsage.placeholders
            .filter { skippedIDs.contains($0.id) }
            .map {
                ParkedProvider(
                    id: $0.id,
                    name: $0.name,
                    reason: skippedReasons[$0.id] ?? "sem login ou assinatura"
                )
            }
    }

    init() {
        skippedIDs = Set(UserDefaults.standard.stringArray(forKey: Self.skippedIDsKey) ?? [])
        skippedReasons = UserDefaults.standard.dictionary(forKey: Self.skippedReasonsKey) as? [String: String] ?? [:]
        providers = loadArchive() ?? ProviderUsage.placeholders.filter { !skippedIDs.contains($0.id) }
        if let preset = ProcessInfo.processInfo.environment["USAGE_DOCK_SELECT"],
           providers.contains(where: { $0.id == preset }) {
            selectedID = preset
            pinnedID = preset
            pinned = true
        }
        startPulse()
        observeWake()
        Task { await refresh() }
    }

    deinit {
        pulseSource?.cancel()
        if let wakeObserver {
            NSWorkspace.shared.notificationCenter.removeObserver(wakeObserver)
        }
        if let screensWakeObserver {
            NSWorkspace.shared.notificationCenter.removeObserver(screensWakeObserver)
        }
        if let sessionObserver {
            NSWorkspace.shared.notificationCenter.removeObserver(sessionObserver)
        }
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

    func restoreWatch(_ id: String) {
        skippedIDs.remove(id)
        skippedReasons.removeValue(forKey: id)
        persistSkip()
        if providers.contains(where: { $0.id == id }) == false,
           let slot = ProviderUsage.placeholders.first(where: { $0.id == id }) {
            let order = ProviderUsage.placeholders.map(\.id)
            var next = providers
            next.append(slot)
            next.sort { (order.firstIndex(of: $0.id) ?? 99) < (order.firstIndex(of: $1.id) ?? 99) }
            providers = next
        }
        Task { await refresh() }
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
        if isLoading {
            if let started = loadingStartedAt,
               Date().timeIntervalSince(started) < Self.loadingDeadline {
                return
            }
        }
        isLoading = true
        loadingStartedAt = Date()
        lastError = nil
        do {
            let data = try await runCollector()
            let payload = try JSONDecoder().decode(CollectorPayload.self, from: data)
            apply(payload.providers)
            lastUpdated = Date()
            saveArchive()
            if selectedID == nil,
               let preset = ProcessInfo.processInfo.environment["USAGE_DOCK_SELECT"],
               providers.contains(where: { $0.id == preset }) {
                selectedID = preset
                pinnedID = preset
                pinned = true
            }
        } catch {
            lastError = error.localizedDescription
            markAged()
        }
        isLoading = false
        loadingStartedAt = nil
    }

    private func apply(_ incoming: [ProviderUsage]) {
        var skipped = skippedIDs
        var reasons = skippedReasons
        for fresh in incoming where fresh.shouldPark {
            skipped.insert(fresh.id)
            reasons[fresh.id] = fresh.error ?? "sem login ou assinatura"
        }
        // Estacionados continuam sendo coletados: quem voltou ok sai da fila sozinho.
        for fresh in incoming where fresh.ok {
            if skipped.contains(fresh.id) {
                skipped.remove(fresh.id)
                reasons.removeValue(forKey: fresh.id)
            }
        }
        if skipped != skippedIDs {
            skippedIDs = skipped
            skippedReasons = reasons
            persistSkip()
            if let selectedID, skipped.contains(selectedID) {
                dismiss()
            }
        }
        let byID = Dictionary(incoming.map { ($0.id, $0) }, uniquingKeysWith: { _, last in last })
        providers = ProviderUsage.placeholders.filter { !skippedIDs.contains($0.id) }.map { slot in
            let current = providers.first(where: { $0.id == slot.id }) ?? slot
            guard let fresh = byID[slot.id] else {
                return current.agedIfLive
            }
            if fresh.ok {
                var live = fresh
                live.stale = false
                return live
            }
            // Leitura boa fica; o anel só esmaece.
            if current.ok, current.usedPercent != nil {
                var kept = current
                kept.stale = true
                return kept
            }
            return fresh
        }
    }

    private func persistSkip() {
        UserDefaults.standard.set(Array(skippedIDs).sorted(), forKey: Self.skippedIDsKey)
        UserDefaults.standard.set(skippedReasons, forKey: Self.skippedReasonsKey)
        UserDefaults.standard.synchronize()
    }

    private static var archiveURL: URL {
        let root = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("UsageDock", isDirectory: true)
        return root.appendingPathComponent("last-providers.json")
    }

    private func loadArchive() -> [ProviderUsage]? {
        guard let data = try? Data(contentsOf: Self.archiveURL),
              let payload = try? JSONDecoder().decode(LastReadings.self, from: data) else {
            return nil
        }
        let byID = Dictionary(payload.providers.map { ($0.id, $0) }, uniquingKeysWith: { _, last in last })
        let aged = Date().timeIntervalSince(payload.savedAt) > Self.staleAfter
        let slots = ProviderUsage.placeholders.filter { !skippedIDs.contains($0.id) }
        return slots.map { slot in
            guard var row = byID[slot.id] else { return slot }
            if aged, row.ok { row.stale = true }
            return row
        }
    }

    private func saveArchive() {
        let url = Self.archiveURL
        try? FileManager.default.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
        let payload = LastReadings(savedAt: Date(), providers: providers)
        guard let data = try? JSONEncoder().encode(payload) else { return }
        try? data.write(to: url, options: .atomic)
    }

    private func markAged() {
        providers = providers.map(\.agedIfLive)
    }

    private func markAgedIfNeeded() {
        guard let lastUpdated, Date().timeIntervalSince(lastUpdated) > Self.staleAfter else { return }
        markAged()
    }

    private var surfaceBusy: Bool {
        selectedID != nil || settingsOpen || hoveringRing != nil || hoveringPopout || pinned
    }

    private func startPulse() {
        pulseSource?.cancel()
        let source = DispatchSource.makeTimerSource(queue: .main)
        source.schedule(deadline: .now() + 1, repeating: Self.pulseEvery, leeway: .seconds(1))
        source.setEventHandler { [weak self] in
            Task { @MainActor in
                self?.pulse()
            }
        }
        source.resume()
        pulseSource = source
    }

    private func pulse() {
        markAgedIfNeeded()
        let due = surfaceBusy ? Self.busyInterval : Self.idleInterval
        if let lastUpdated, Date().timeIntervalSince(lastUpdated) < due {
            return
        }
        Task { await refresh() }
    }

    private func observeWake() {
        let center = NSWorkspace.shared.notificationCenter
        wakeObserver = center.addObserver(
            forName: NSWorkspace.didWakeNotification,
            object: nil,
            queue: .main
        ) { [weak self] _ in
            Task { @MainActor in
                await self?.refresh()
            }
        }
        screensWakeObserver = center.addObserver(
            forName: NSWorkspace.screensDidWakeNotification,
            object: nil,
            queue: .main
        ) { [weak self] _ in
            Task { @MainActor in
                await self?.refresh()
            }
        }
        sessionObserver = center.addObserver(
            forName: NSWorkspace.sessionDidBecomeActiveNotification,
            object: nil,
            queue: .main
        ) { [weak self] _ in
            Task { @MainActor in
                await self?.refresh()
            }
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
        let pythonPath = self.pythonPath
        let scriptPath = self.scriptPath
        return try await withCheckedThrowingContinuation { continuation in
            DispatchQueue.global(qos: .userInitiated).async {
                let process = Process()
                process.executableURL = URL(fileURLWithPath: pythonPath)
                process.arguments = [scriptPath]
                let out = Pipe()
                let err = Pipe()
                process.standardOutput = out
                process.standardError = err
                var env = ProcessInfo.processInfo.environment
                env["PYTHONUNBUFFERED"] = "1"
                // Sem USAGE_DOCK_SKIP: estacionados seguem coletados pra auto-voltar.
                process.environment = env
                do {
                    try process.run()
                    var stdout = Data()
                    let reads = DispatchGroup()
                    reads.enter()
                    DispatchQueue.global(qos: .utility).async {
                        stdout = out.fileHandleForReading.readDataToEndOfFile()
                        reads.leave()
                    }
                    let deadline = Date().addingTimeInterval(18)
                    while process.isRunning, Date() < deadline {
                        Thread.sleep(forTimeInterval: 0.05)
                    }
                    if process.isRunning {
                        process.terminate()
                        Thread.sleep(forTimeInterval: 0.2)
                        if process.isRunning {
                            process.interrupt()
                        }
                    }
                    process.waitUntilExit()
                    _ = reads.wait(timeout: .now() + 1)
                    if process.terminationStatus != 0, stdout.isEmpty {
                        let message = String(data: err.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8) ?? ""
                        continuation.resume(throwing: CollectorError.failed(process.terminationStatus, message.isEmpty ? "coletor travou (>18s)" : message))
                    } else if stdout.isEmpty {
                        continuation.resume(throwing: CollectorError.failed(1, "coletor sem JSON"))
                    } else {
                        continuation.resume(returning: stdout)
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
