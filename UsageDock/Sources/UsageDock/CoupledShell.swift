import SwiftUI

enum NotchEdge {
    case trailing
}

/// D-tab soldado no bezel. `curlRadius` 0 = cápsula cortada na direita.
///
/// A família visual (scoop no bezel, pílula na borda) vem do Codenotch do Vinz,
/// agora MIT: https://github.com/vinzdg/codenotch — `Sources/Notch/SideNotchShape.swift`.
/// O path daqui é o da spec Sequoia (só trailing, arcos por tangente no peek).
/// Não copiar o transform de quatro bordas nem o merge com notch de hardware
/// sem uma ordem explícita: isso muda a casca aprovada.
struct SideNotchShape: Shape {
    var edge: NotchEdge = .trailing
    var joining: CGFloat = 8
    var curlRadius: CGFloat
    var cornerRadius: CGFloat = 0

    var animatableData: CGFloat {
        get { curlRadius }
        set { curlRadius = newValue }
    }

    init(scoop: CGFloat) {
        self.curlRadius = scoop
    }

    func path(in rect: CGRect) -> Path {
        let curl = min(max(curlRadius, 0), rect.height * 0.22)
        let pillTop = rect.minY + curl
        let pillBottom = rect.maxY - curl
        let autoCorner = min(rect.width / 2, max((pillBottom - pillTop) / 2, 1))
        let r = cornerRadius > 0.5 ? min(cornerRadius, autoCorner) : autoCorner
        let weld = edge == .trailing ? rect.maxX + joining : rect.minX - joining
        let leading = rect.minX

        var path = Path()
        path.move(to: CGPoint(x: weld, y: rect.minY))
        if curl < 0.5 {
            // D-tab: cantos esquerdos redondos, direita soldada. Arcos por tangente
            // (mesma construção do ramo com scoop) para o morph não inverter a curva.
            path.addLine(to: CGPoint(x: leading + r, y: rect.minY))
            path.addArc(
                tangent1End: CGPoint(x: leading, y: rect.minY),
                tangent2End: CGPoint(x: leading, y: rect.maxY),
                radius: r
            )
            path.addArc(
                tangent1End: CGPoint(x: leading, y: rect.maxY),
                tangent2End: CGPoint(x: weld, y: rect.maxY),
                radius: r
            )
            path.addLine(to: CGPoint(x: weld, y: rect.maxY))
        } else {
            path.addArc(
                tangent1End: CGPoint(x: weld, y: pillTop),
                tangent2End: CGPoint(x: leading + r, y: pillTop),
                radius: curl
            )
            path.addArc(
                tangent1End: CGPoint(x: leading, y: pillTop),
                tangent2End: CGPoint(x: leading, y: pillBottom),
                radius: r
            )
            path.addArc(
                tangent1End: CGPoint(x: leading, y: pillBottom),
                tangent2End: CGPoint(x: weld, y: pillBottom),
                radius: r
            )
            path.addArc(
                tangent1End: CGPoint(x: weld, y: pillBottom),
                tangent2End: CGPoint(x: weld, y: rect.maxY),
                radius: curl
            )
            path.addLine(to: CGPoint(x: weld, y: rect.maxY))
        }
        path.addLine(to: CGPoint(x: weld, y: rect.minY))
        path.closeSubpath()
        return path
    }
}

typealias CoupledShell = SideNotchShape

struct DockHitShape: Shape {
    var scoop: CGFloat

    func path(in rect: CGRect) -> Path {
        SideNotchShape(scoop: scoop).path(in: rect)
    }
}

struct GearArc: Shape {
    func path(in rect: CGRect) -> Path {
        var path = Path()
        path.move(to: CGPoint(x: rect.minX, y: rect.maxY))
        path.addQuadCurve(
            to: CGPoint(x: rect.maxX, y: rect.maxY),
            control: CGPoint(x: rect.midX, y: rect.minY)
        )
        return path
    }
}
