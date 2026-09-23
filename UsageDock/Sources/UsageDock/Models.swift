import Foundation
import CoreGraphics

struct DockLayout: Equatable {
    var collapsed: Bool
    var selectedIndex: Int?
    var ringCount: Int
    var popoutHeight: CGFloat
    var coupled: Bool

    static let scoop: CGFloat = 20
    static let snapDistance: CGFloat = 40
    static let capsuleWidth: CGFloat = 66
    static let capsuleTopPad: CGFloat = 16
    static let capsuleBottomPad: CGFloat = 12
    static let ringRow: CGFloat = 62
    static let ringIcon: CGFloat = 44
    static let ringSpacing: CGFloat = 12
    static let popoutWidth: CGFloat = 240
    static let popoutGap: CGFloat = 12
    static let settingsHeight: CGFloat = 296

    static func settingsCardHeight(parkedCount: Int) -> CGFloat {
        guard parkedCount > 0 else { return settingsHeight }
        return min(settingsHeight + 36 + CGFloat(parkedCount) * 36, 460)
    }
    static let peekWidth: CGFloat = 16
    static let peekHeight: CGFloat = 46
    /// ringSpacing + arco (7) + 2 + gear (22) + padding.top (2). Menor que isso clipa 1 pt.
    static let gearZone: CGFloat = 45
    /// Centro do anel dentro da linha: ringIcon / 2. O caret do popout aponta aqui.
    static let ringIconCenterY: CGFloat = ringIcon / 2

    var scoopPad: CGFloat { Self.scoop }

    var expandedCapsuleHeight: CGFloat {
        let rings = CGFloat(max(ringCount, 0))
        let ringsBlock: CGFloat = rings == 0
            ? 0
            : rings * Self.ringRow + max(0, rings - 1) * Self.ringSpacing
        return Self.capsuleTopPad
            + ringsBlock
            + Self.gearZone
            + Self.capsuleBottomPad
    }

    var capsuleHeight: CGFloat {
        collapsed ? Self.peekHeight : expandedCapsuleHeight
    }

    var expandedShellHeight: CGFloat {
        expandedCapsuleHeight + scoopPad * 2
    }

    var shellHeight: CGFloat {
        collapsed ? Self.peekHeight : expandedShellHeight
    }

    /// Window stays expanded so the spring morph is never clipped.
    var panelSize: CGSize {
        let lastTop = popoutTopPadding(index: max(ringCount - 1, 0))
        let height = max(expandedShellHeight, lastTop + popoutHeight)
        let width = Self.capsuleWidth + Self.popoutGap + Self.popoutWidth
        return CGSize(width: width, height: height)
    }

    func popoutTopPadding(index: Int) -> CGFloat {
        scoopPad + Self.capsuleTopPad + CGFloat(index) * (Self.ringRow + Self.ringSpacing)
    }

    static func estimatedPopoutHeight(
        detailCount: Int,
        extraCaptionCount: Int,
        sessionCount: Int,
        hasError: Bool,
        hasProfile: Bool = false
    ) -> CGFloat {
        let pad: CGFloat = 20
        let header: CGFloat = 16
        let sectionGap: CGFloat = 9
        if hasError { return pad + header + sectionGap + 48 }
        var height = pad + header + sectionGap
        height += CGFloat(max(detailCount, 1)) * 38
        height += CGFloat(max(detailCount - 1, 0)) * sectionGap
        height += CGFloat(extraCaptionCount) * 16
        if sessionCount > 0 {
            height += sectionGap + 2
            height += CGFloat(sessionCount) * 18
        }
        if hasProfile {
            height += Self.codexProfileBlock
        }
        return height
    }

    /// Bloco Codenotch 1.7 compactado na nossa largura 240: métricas, hoje/30d, histograma.
    static let codexProfileBlock: CGFloat = 188

    @MainActor
    static func from(store: UsageStore) -> DockLayout {
        let idx: Int? = {
            guard !store.collapsed, let sid = store.selectedID else { return nil }
            return store.providers.firstIndex(where: { $0.id == sid })
        }()
        let activePopout: CGFloat = {
            if store.settingsOpen { return settingsCardHeight(parkedCount: store.parked.count) }
            guard let idx else { return 0 }
            let provider = store.providers[idx]
            let extraCaptions = provider.details.filter {
                guard let caption = $0.caption else { return false }
                return caption.contains("$")
            }.count
            return estimatedPopoutHeight(
                detailCount: provider.details.count,
                extraCaptionCount: extraCaptions,
                sessionCount: provider.sessions?.count ?? 0,
                hasError: !provider.ok,
                hasProfile: provider.profile != nil
            )
        }()
        return DockLayout(
            collapsed: store.collapsed,
            selectedIndex: idx,
            ringCount: store.providers.count,
            popoutHeight: activePopout,
            coupled: store.coupledTrailing
        )
    }
}

struct CollectorPayload: Codable {
    var ts: Double
    var providers: [ProviderUsage]
}

struct ProviderUsage: Codable, Identifiable {
    var id: String
    var name: String
    var ok: Bool
    var usedPercent: Double?
    var details: [UsageDetail]
    var note: String?
    var plan: String?
    var error: String?
    var stale: Bool?
    var skipWatch: Bool? = nil
    var sessions: [UsageSession]?
    var profile: CodexProfileUsage? = nil

    var ringPercent: Double {
        guard ok, let usedPercent, usedPercent.isFinite else { return 0 }
        return min(max(usedPercent, 0), 100)
    }

    var isAged: Bool { stale == true }

    var shouldPark: Bool {
        if ok { return false }
        if skipWatch == true { return true }
        guard let error, !error.isEmpty else { return false }
        let text = error.lowercased()
        let hints = [
            "sem chave",
            "faça login",
            "deslogado",
            "sem api key",
            "api key inválida",
            "chave go recusada",
            "token grok vazio",
            "auth.json",
            "cli/limits indisponível",
            "histórico codexlimits vazio",
        ]
        return hints.contains { text.contains($0) }
    }

    var agedIfLive: ProviderUsage {
        guard ok else { return self }
        var copy = self
        copy.stale = true
        return copy
    }
}

struct UsageDetail: Codable, Identifiable {
    var label: String
    var usedPercent: Double?
    var resetsAt: String?
    var caption: String?
    var windowSeconds: Double? = nil

    var id: String { label }

    var percent: Double {
        guard let usedPercent, usedPercent.isFinite else { return 0 }
        return min(max(usedPercent, 0), 100)
    }
}

/// Token statistics from Codex `/wham/profiles/me`. Absent when the fetch fails.
struct CodexProfileUsage: Codable, Equatable {
    var lifetimeTokens: Int?
    var peakDailyTokens: Int?
    var longestChatSeconds: Double?
    var currentStreakDays: Int?
    var longestStreakDays: Int?
    var todayTokens: Int?
    var thirtyDayTokens: Int?
    var daily: [Int]
}

/// Optional collector field. Rendered only when the payload actually sends it.
struct UsageSession: Codable, Identifiable {
    var name: String
    var status: String?

    var id: String { name }
}

extension ProviderUsage {
    static let placeholders: [ProviderUsage] = [
        ProviderUsage(id: "codex", name: "Codex", ok: false, usedPercent: nil, details: [], note: nil, plan: nil, error: nil, stale: false, sessions: nil),
        ProviderUsage(id: "opencode", name: "OpenCode", ok: false, usedPercent: nil, details: [], note: nil, plan: nil, error: nil, stale: false, sessions: nil),
        ProviderUsage(id: "goat", name: "Command", ok: false, usedPercent: nil, details: [], note: nil, plan: nil, error: nil, stale: false, sessions: nil),
        ProviderUsage(id: "cursor", name: "Cursor", ok: false, usedPercent: nil, details: [], note: nil, plan: nil, error: nil, stale: false, sessions: nil),
        ProviderUsage(id: "grok", name: "Grok", ok: false, usedPercent: nil, details: [], note: nil, plan: nil, error: nil, stale: false, sessions: nil),
        ProviderUsage(id: "devin", name: "Devin", ok: false, usedPercent: nil, details: [], note: nil, plan: nil, error: nil, stale: false, sessions: nil)
    ]
}

struct ParkedProvider: Identifiable, Equatable {
    var id: String
    var name: String
    var reason: String
}

struct LastReadings: Codable {
    var savedAt: Date
    var providers: [ProviderUsage]
}
