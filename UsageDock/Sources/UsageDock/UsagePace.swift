import Foundation

/// Used quota minus elapsed time, in percentage points.
/// Port of Codenotch `UsagePace` (MIT) — labels in pt-BR.
struct UsagePace {
    let percentagePoints: Double

    var isDeficit: Bool { percentagePoints > 0 }

    var summary: String {
        let magnitude = abs(percentagePoints)
        let rounded = (magnitude * 10).rounded() / 10
        let value = rounded == 0 && magnitude > 0
            ? "<0.1"
            : String(format: "%.1f", locale: Locale(identifier: "en_US_POSIX"), rounded)
                .replacingOccurrences(of: ".0", with: "")
        return isDeficit ? "\(value)% déficit" : "\(value)% reserva"
    }

    static func from(usedPercent: Double, windowSeconds: Double, resetsAt: Date, now: Date) -> UsagePace? {
        guard usedPercent.isFinite, usedPercent >= 0,
              windowSeconds.isFinite, windowSeconds > 0 else { return nil }
        let remainingTime = resetsAt.timeIntervalSince(now)
        guard remainingTime.isFinite, remainingTime > 0 else { return nil }
        let remainingFraction = min(remainingTime / windowSeconds, 1)
        let elapsedFraction = 1 - remainingFraction
        let spentFraction = min(usedPercent / 100, 1)
        return UsagePace(percentagePoints: (spentFraction - elapsedFraction) * 100)
    }
}

enum Percent {
    static func halves(for fraction: Double) -> (used: String, left: String) {
        let value = fraction * 100
        let fractional = (value > 0 && value < 1) || (value > 99 && value < 100)
        guard fractional else {
            let used = Int(value.rounded())
            return ("\(used)", "\(max(0, 100 - used))")
        }
        let left = max(0, 100 - value)
        return (small(value), left > 99.9 ? ">99.9" : small(left))
    }

    private static func small(_ value: Double) -> String {
        if value <= 0 { return "0" }
        let tenths = (value * 10).rounded() / 10
        if tenths < 0.1 { return "<0.1" }
        if tenths > 99.9 { return ">99.9" }
        return String(format: "%.1f", locale: Locale(identifier: "en_US_POSIX"), tenths)
    }
}

enum UsageFormat {
    static func tokens(_ value: Int?) -> String {
        guard let value else { return "—" }
        switch value {
        case 1_000_000_000...:
            return String(format: "%.2fB", locale: Locale(identifier: "en_US_POSIX"),
                          Double(value) / 1_000_000_000)
        case 1_000_000...:
            return String(format: "%.1fM", locale: Locale(identifier: "en_US_POSIX"),
                          Double(value) / 1_000_000)
        case 1_000...:
            return String(format: "%.0fK", locale: Locale(identifier: "en_US_POSIX"),
                          Double(value) / 1_000)
        default:
            return "\(value)"
        }
    }

    static func duration(seconds: Double?) -> String {
        guard let seconds, seconds.isFinite, seconds > 0 else { return "—" }
        let minutes = max(1, Int((seconds / 60).rounded()))
        let hours = minutes / 60
        let remainder = minutes % 60
        if hours > 0 {
            return remainder == 0 ? "\(hours)h" : "\(hours)h \(remainder)m"
        }
        return "\(minutes)m"
    }

    static func days(_ value: Int?) -> String {
        guard let value else { return "—" }
        return "\(value)d"
    }
}
