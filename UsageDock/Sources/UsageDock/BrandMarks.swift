import AppKit
import SwiftUI

enum BrandID: String {
    case codex, opencode, goat, cursor, grok
}

enum BrandTone {
    case light
    case dark

    var color: Color {
        switch self {
        case .light: return Color.white.opacity(0.94)
        case .dark: return Color.black.opacity(0.88)
        }
    }
}

struct BrandMark: View {
    let id: String
    var tone: BrandTone = .light

    var body: some View {
        Group {
            switch BrandID(rawValue: id) {
            case .codex:
                RasterTemplateMark(id: id, tone: tone)
            case .opencode:
                BundledSVGMark(name: "opencode", tone: tone)
            case .goat:
                BundledSVGMark(name: "commandcode", tone: tone)
            case .cursor:
                BundledSVGMark(name: "cursor-mark", tone: tone)
            case .grok:
                BundledSVGMark(name: "xai", tone: tone)
            case .none:
                Circle()
                    .fill(tone.color)
                    .padding(5)
            }
        }
        .scaleEffect(opticalScale)
        .accessibilityHidden(true)
    }

    private var opticalScale: CGFloat {
        switch BrandID(rawValue: id) {
        case .opencode, .grok: return 1.08
        case .goat: return 1.02
        case .codex, .cursor, .none: return 1
        }
    }
}

private struct BundledSVGMark: View {
    let name: String
    let tone: BrandTone

    private var image: NSImage? {
        guard let url = Bundle.main.url(forResource: name, withExtension: "svg") else {
            return nil
        }
        guard let loaded = NSImage(contentsOf: url) else { return nil }
        let image = loaded.copy() as? NSImage ?? loaded
        image.isTemplate = true
        return image
    }

    var body: some View {
        Group {
            if let image {
                Image(nsImage: image)
                    .renderingMode(.template)
                    .resizable()
                    .interpolation(.high)
                    .scaledToFit()
                    .foregroundStyle(tone.color)
            } else {
                Image(systemName: "circle.dashed")
                    .resizable()
                    .scaledToFit()
                    .foregroundStyle(tone.color)
            }
        }
    }
}

private struct RasterTemplateMark: View {
    let id: String
    let tone: BrandTone

    var body: some View {
        Group {
            if let (image, invert) = BrandAsset.image(for: id) {
                if invert {
                    Image(nsImage: image)
                        .resizable()
                        .interpolation(.high)
                        .scaledToFit()
                        .colorInvert()
                        .luminanceToAlpha()
                        .colorInvert()
                        .colorMultiply(tone.color)
                } else {
                    Image(nsImage: image)
                        .renderingMode(.template)
                        .resizable()
                        .interpolation(.high)
                        .scaledToFit()
                        .foregroundStyle(tone.color)
                }
            } else {
                Image(systemName: "circle.dashed")
                    .resizable()
                    .scaledToFit()
                    .foregroundStyle(tone.color)
            }
        }
    }
}
