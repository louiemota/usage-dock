import SwiftUI

/// Limiares de alerta da % usada. A cor do anel é o único sinal alto.
/// 0–39 calmo · 40–69 atenção · 70–89 quente · 90–100 crítico.
enum UsageBand: String {
    case calm
    case watch
    case hot
    case critical
    case unknown

    static func band(for percent: Double?, ok: Bool) -> UsageBand {
        guard ok, let percent, percent.isFinite else { return .unknown }
        switch percent {
        case ..<40: return .calm
        case ..<70: return .watch
        case ..<90: return .hot
        default: return .critical
        }
    }

    var ring: Color {
        switch self {
        case .calm: return Color(red: 0.24, green: 0.86, blue: 0.59)      // #3DDC97
        case .watch: return Color(red: 0.96, green: 0.77, blue: 0.26)     // #F5C542
        case .hot: return Color(red: 1.00, green: 0.48, blue: 0.24)       // #FF7A3D
        case .critical: return Color(red: 1.00, green: 0.23, blue: 0.31)  // #FF3B4E
        case .unknown: return Color(red: 0.42, green: 0.45, blue: 0.50)
        }
    }
}

enum DockTheme {
    static let shell = Color(red: 0.043, green: 0.047, blue: 0.063)       // #0B0C10
    static let shellLift = Color(red: 0.086, green: 0.094, blue: 0.122)   // #16181F
    static let text = Color(red: 0.95, green: 0.96, blue: 0.97)
    static let muted = Color(red: 0.62, green: 0.63, blue: 0.68)
    static let track = Color(red: 0.22, green: 0.23, blue: 0.27)
    static let barTrack = Color.white.opacity(0.07)
    static let glassTint = Color.black.opacity(0.30)
}
