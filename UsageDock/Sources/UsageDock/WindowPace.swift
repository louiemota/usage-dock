import Foundation

/// Compara o consumo de uma janela de cota com o relógio dela.
/// Se 60% da cota foi usada quando 43% do tempo passou, o uso está 17 pontos na frente.
struct WindowPace {
    /// Pontos percentuais entre o uso e o tempo decorrido. Positivo quer dizer uso na frente do relógio.
    let lead: Double

    /// Devolve nil quando não há o que comparar: janela sem duração ou reset que já passou.
    init?(usedPercent: Double, windowSeconds: Double, resetsAt: Date, now: Date) {
        let secondsLeft = resetsAt.timeIntervalSince(now)
        guard usedPercent.isFinite, usedPercent >= 0,
              windowSeconds.isFinite, windowSeconds > 0,
              secondsLeft.isFinite, secondsLeft > 0 else { return nil }
        // O relógio do provedor pode estar adiantado: o que falta nunca passa da janela inteira.
        let clockShare = 1 - min(secondsLeft / windowSeconds, 1)
        let usedShare = min(usedPercent / 100, 1)
        lead = (usedShare - clockShare) * 100
    }

    var isAhead: Bool { lead > 0 }

    /// Texto do cartão, como "7.8% déficit" ou "3% reserva".
    var caption: String {
        let size = abs(lead)
        let tenths = Tenths.count(size)
        let number = tenths == 0 && size > 0 ? "<0.1" : Tenths.text(tenths, keepZero: false)
        return "\(number)% \(isAhead ? "déficit" : "reserva")"
    }
}

/// Valores com uma casa decimal, guardados como décimos inteiros para não depender de formatação de ponto flutuante.
enum Tenths {
    static func count(_ value: Double) -> Int {
        Int((value * 10).rounded())
    }

    /// Escreve os décimos com ponto. Com `keepZero` falso, 120 vira "12" em vez de "12.0".
    static func text(_ tenths: Int, keepZero: Bool) -> String {
        let (whole, rest) = tenths.quotientAndRemainder(dividingBy: 10)
        return rest == 0 && !keepZero ? "\(whole)" : "\(whole).\(rest)"
    }
}

enum PercentText {
    /// Textos de "usado" e "restante" de uma barra, a partir da fração usada.
    /// Perto de 0% e de 100% entra uma casa decimal, para 0,4% não aparecer como 0% nem 99,6% como 100%.
    static func usedAndLeft(fraction: Double) -> (used: String, left: String) {
        let used = fraction * 100
        let nearAnEdge = (used > 0 && used < 1) || (used > 99 && used < 100)
        guard nearAnEdge else {
            let whole = Int(used.rounded())
            return (String(whole), String(max(0, 100 - whole)))
        }
        let left = max(0, 100 - used)
        return (edge(used), left > 99.9 ? ">99.9" : edge(left))
    }

    private static func edge(_ percent: Double) -> String {
        guard percent > 0 else { return "0" }
        switch Tenths.count(percent) {
        case ..<1: return "<0.1"
        case 1000...: return ">99.9"
        case let tenths: return Tenths.text(tenths, keepZero: true)
        }
    }
}

/// Números do bloco de estatísticas, em formato curto.
enum CompactValue {
    static let missing = "—"

    private static let tokenUnits: [(size: Int, suffix: String, decimals: Int)] = [
        (1_000_000_000, "B", 2),
        (1_000_000, "M", 1),
        (1_000, "K", 0),
    ]

    static func tokens(_ count: Int?) -> String {
        guard let count else { return missing }
        guard let unit = tokenUnits.first(where: { count >= $0.size }) else { return String(count) }
        let scaled = Double(count) / Double(unit.size)
        return String(format: "%.\(unit.decimals)f", locale: Locale(identifier: "en_US_POSIX"), scaled) + unit.suffix
    }

    static func timeSpan(seconds: Double?) -> String {
        guard let seconds, seconds.isFinite, seconds > 0 else { return missing }
        let total = max(1, Int((seconds / 60).rounded()))
        let (hours, minutes) = total.quotientAndRemainder(dividingBy: 60)
        switch (hours, minutes) {
        case (0, _): return "\(minutes)m"
        case (_, 0): return "\(hours)h"
        default: return "\(hours)h \(minutes)m"
        }
    }

    static func days(_ count: Int?) -> String {
        count.map { "\($0)d" } ?? missing
    }
}
