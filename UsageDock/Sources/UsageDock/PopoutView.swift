import SwiftUI

struct PopoutView: View {
    let provider: ProviderUsage
    var caretY: CGFloat = DockLayout.ringIconCenterY
    var loading: Bool = false

    var body: some View {
        VStack(alignment: .leading, spacing: 9) {
            HStack(spacing: 7) {
                BrandMark(id: provider.id)
                    .frame(width: 14, height: 14)
                Text("\(provider.name) Usage")
                    .font(.system(size: 11, weight: .semibold))
                    .foregroundStyle(DockTheme.text)
                    .lineLimit(1)
                Spacer(minLength: 8)
                if provider.ok, let plan = provider.plan, !plan.isEmpty {
                    PlanChip(text: plan)
                }
            }

            if let error = provider.error, !provider.ok {
                Text(error)
                    .font(.system(size: 10))
                    .foregroundStyle(UsageBand.hot.ring)
                    .fixedSize(horizontal: false, vertical: true)
            } else if provider.details.isEmpty {
                Text(loading ? "Carregando…" : "Sem detalhe de cota")
                    .font(.system(size: 10))
                    .foregroundStyle(DockTheme.muted)
            } else {
                ForEach(provider.details) { detail in
                    DetailRow(detail: detail)
                }
            }

            if let sessions = provider.sessions, !sessions.isEmpty {
                VStack(alignment: .leading, spacing: 6) {
                    ForEach(sessions) { session in
                        HStack(spacing: 8) {
                            Text(session.name)
                                .font(.system(size: 10, weight: .medium))
                                .foregroundStyle(DockTheme.text.opacity(0.9))
                                .lineLimit(1)
                            Spacer(minLength: 8)
                            if let status = session.status, !status.isEmpty {
                                Text(status)
                                    .font(.system(size: 10))
                                    .foregroundStyle(DockTheme.muted)
                                    .lineLimit(1)
                            }
                        }
                    }
                }
                .padding(.top, 2)
            }
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 10)
        .frame(width: DockLayout.popoutWidth, alignment: .leading)
        .background(
            RoundedRectangle(cornerRadius: 13, style: .continuous)
                .fill(.ultraThinMaterial)
                .overlay {
                    RoundedRectangle(cornerRadius: 13, style: .continuous)
                        .fill(DockTheme.glassTint)
                }
                .shadow(color: .black.opacity(0.45), radius: 18, y: 8)
        )
        .overlay(
            RoundedRectangle(cornerRadius: 13, style: .continuous)
                .stroke(Color.white.opacity(0.14), lineWidth: 1)
        )
        .overlay(alignment: .topTrailing) {
            PopoutCaret()
                .fill(DockTheme.shell.opacity(0.92))
                .frame(width: 16, height: 24)
                .offset(x: 10, y: caretY - 12)
        }
    }
}

/// Chip de plano do header (SPEC estado 3). Altura fixa em 16 pt para não
/// alterar a estimativa de altura do popout usada no hit-test.
private struct PlanChip: View {
    let text: String

    var body: some View {
        Text(text)
            .font(.system(size: 9, weight: .semibold, design: .rounded))
            .foregroundStyle(DockTheme.text.opacity(0.85))
            .lineLimit(1)
            .padding(.horizontal, 6)
            .frame(height: 16)
            .background(Capsule().fill(Color.white.opacity(0.10)))
            .overlay(Capsule().stroke(Color.white.opacity(0.12), lineWidth: 1))
    }
}

private struct DetailRow: View {
    let detail: UsageDetail
    @State private var settle = false

    private var extraCaption: String? {
        guard let caption = detail.caption, !caption.isEmpty else { return nil }
        if caption.contains("$") { return caption }
        return nil
    }

    var body: some View {
        let band = UsageBand.band(for: detail.usedPercent, ok: detail.usedPercent != nil)
        let reset = ResetCopy.label(detail.resetsAt)
        VStack(alignment: .leading, spacing: 4) {
            HStack(alignment: .firstTextBaseline, spacing: 8) {
                Text(detail.label)
                    .font(.system(size: 10, weight: .medium))
                    .foregroundStyle(DockTheme.muted)
                    .lineLimit(1)
                Spacer(minLength: 8)
                if !reset.isEmpty {
                    Text(reset)
                        .font(.system(size: 10))
                        .foregroundStyle(DockTheme.muted)
                        .lineLimit(1)
                        .minimumScaleFactor(0.75)
                        .multilineTextAlignment(.trailing)
                }
            }

            if detail.usedPercent != nil {
                QuietUsageBar(percent: detail.percent, color: band.ring)
                Text("\(Int(detail.percent.rounded()))% usado")
                    .font(.system(size: 10, weight: .semibold, design: .rounded))
                    .monospacedDigit()
                    .foregroundStyle(band.ring)
                    .contentTransition(settle ? .numericText() : .identity)
                    .transaction { $0.animation = settle ? .easeOut(duration: 0.55) : nil }
            } else if let caption = detail.caption, !caption.isEmpty {
                Text(caption)
                    .font(.system(size: 11, weight: .semibold))
                    .foregroundStyle(DockTheme.text)
                    .fixedSize(horizontal: false, vertical: true)
            }

            if detail.usedPercent != nil, let extraCaption {
                Text(extraCaption)
                    .font(.system(size: 10, weight: .medium))
                    .foregroundStyle(DockTheme.text.opacity(0.88))
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
        .onAppear {
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.22) {
                settle = true
            }
        }
    }
}

private struct QuietUsageBar: View {
    var percent: Double
    var color: Color
    @State private var fill: Double = 0
    @State private var live = false

    var body: some View {
        Capsule()
            .fill(DockTheme.barTrack)
            .frame(height: 3)
            .overlay(alignment: .leading) {
                Capsule()
                    .fill(color)
                    .scaleEffect(x: max(0.02, CGFloat(fill / 100)), y: 1, anchor: .leading)
            }
            .clipShape(Capsule())
            .onAppear {
                fill = 0
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.2) {
                    withAnimation(.timingCurve(0.22, 0.8, 0.2, 1, duration: 0.85)) {
                        fill = percent
                    }
                    DispatchQueue.main.asyncAfter(deadline: .now() + 0.9) {
                        live = true
                    }
                }
            }
            .onChange(of: percent) { _, newValue in
                guard live else { return }
                withAnimation(.easeOut(duration: 0.55)) {
                    fill = newValue
                }
            }
    }
}

enum ResetCopy {
    static func label(_ raw: String?) -> String {
        guard let raw, let date = parse(raw) else { return "" }
        let remaining = date.timeIntervalSinceNow
        if remaining <= 0 {
            return "resetou"
        }
        if remaining < 60 {
            return "Reseta em 1 min"
        }
        if remaining < 36 * 3600 {
            let hours = Int(remaining / 3600)
            let minutes = Int(remaining.truncatingRemainder(dividingBy: 3600) / 60)
            if hours == 0 {
                return "Reseta em \(max(1, minutes)) min"
            }
            if minutes == 0 {
                return "Reseta em \(hours)h"
            }
            return "Reseta em \(hours)h \(minutes)m"
        }
        if remaining < 7 * 24 * 3600 {
            let days = Int(remaining / 86_400)
            let hours = Int(remaining.truncatingRemainder(dividingBy: 86_400) / 3600)
            if hours == 0 {
                return "Reseta em \(days)d"
            }
            return "Reseta em \(days)d \(hours)h"
        }
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "pt_BR")
        formatter.dateFormat = "dd/MM HH:mm"
        return "Reseta \(formatter.string(from: date))"
    }

    static func parse(_ raw: String) -> Date? {
        let iso = ISO8601DateFormatter()
        iso.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let date = iso.date(from: raw) { return date }
        iso.formatOptions = [.withInternetDateTime]
        if let date = iso.date(from: raw) { return date }
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.dateFormat = "yyyy-MM-dd'T'HH:mm:ssXXXXX"
        return formatter.date(from: raw)
    }
}

private struct PopoutCaret: Shape {
    func path(in rect: CGRect) -> Path {
        var path = Path()
        path.move(to: CGPoint(x: rect.minX, y: rect.minY))
        path.addLine(to: CGPoint(x: rect.maxX, y: rect.midY))
        path.addLine(to: CGPoint(x: rect.minX, y: rect.maxY))
        path.closeSubpath()
        return path
    }
}
