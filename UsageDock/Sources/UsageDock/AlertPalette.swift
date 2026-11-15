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
    /// Preto, não carvão e não leite.
    static let shell = Color.black
    static let text = Color.white
    static let muted = Color(red: 0.502, green: 0.502, blue: 0.502)       // #808080
    static let track = Color(red: 0.188, green: 0.188, blue: 0.188)       // #303030
    static let barTrack = Color(red: 0.176, green: 0.176, blue: 0.176)    // #2D2D2D
    static let hairline = Color.white.opacity(0.14)
}

/// Uma superfície só para pílula, popout e ajustes, em preto.
/// Material do Sequoia no card era o cinza leite; a casca não acompanha isso.
struct DockSurface<S: Shape>: View {
    var shape: S
    var stroke: Bool = true

    var body: some View {
        ZStack {
            shape.fill(DockTheme.shell)
            if stroke {
                shape.stroke(DockTheme.hairline, lineWidth: 1)
            }
        }
    }
}
