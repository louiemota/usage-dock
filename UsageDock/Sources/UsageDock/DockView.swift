import SwiftUI

struct DockView: View {
    @ObservedObject var store: UsageStore
    var onQuit: () -> Void
    var onLayout: () -> Void = {}
    var onResetPosition: () -> Void = {}

    private var layout: DockLayout { DockLayout.from(store: store) }

    private var selectedProvider: ProviderUsage? {
        guard !store.collapsed, !store.settingsOpen, let id = store.selectedID else { return nil }
        return store.providers.first(where: { $0.id == id })
    }

    var body: some View {
        let layout = self.layout
        let expandedH = layout.expandedShellHeight
        let pillW: CGFloat = store.collapsed ? DockLayout.peekWidth : DockLayout.capsuleWidth
        let pillH: CGFloat = store.collapsed ? DockLayout.peekHeight : expandedH
        let scoop: CGFloat = store.collapsed ? 0 : DockLayout.scoop
        ZStack(alignment: .topTrailing) {
            if store.settingsOpen, !store.collapsed {
                SettingsModal(
                    store: store,
                    onQuit: onQuit,
                    onResetPosition: onResetPosition
                )
                .padding(.trailing, DockLayout.capsuleWidth + DockLayout.popoutGap)
                .padding(.top, layout.scoopPad + 8)
                .transition(
                    .asymmetric(
                        insertion: .opacity.combined(with: .offset(x: 10)),
                        removal: .opacity.combined(with: .offset(x: 10))
                    )
                )
            } else if let selected = selectedProvider, let index = store.providers.firstIndex(where: { $0.id == selected.id }) {
                PopoutView(
                    provider: selected,
                    caretY: DockLayout.ringIconCenterY,
                    loading: store.isLoading
                )
                .padding(.trailing, DockLayout.capsuleWidth + DockLayout.popoutGap)
                .padding(.top, layout.popoutTopPadding(index: index))
                .onHover { hovering in
                    if hovering { store.pointerEnteredPopout() }
                    else { store.pointerExitedPopout() }
                }
                .transition(
                    .asymmetric(
                        insertion: .opacity.combined(with: .offset(x: 10)),
                        removal: .opacity.combined(with: .offset(x: 10))
                    )
                )
            }

            // Peek fica no meio vertical da pílula expandida (SPEC estado 1) e o
            // spring nasce do centro. Expandido, o frame coincide com a pílula.
            morphingPill(pillW: pillW, pillH: pillH, scoop: scoop, layout: layout)
                .frame(width: pillW, height: expandedH, alignment: .center)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topTrailing)
        .ignoresSafeArea()
        .animation(
            store.collapsed
                ? .linear(duration: 0.14)
                : .spring(response: 0.34, dampingFraction: 0.78),
            value: store.collapsed
        )
        .animation(.easeOut(duration: 0.16), value: store.selectedID)
        .animation(.easeOut(duration: 0.16), value: store.coupledTrailing)
        .animation(.easeOut(duration: 0.16), value: store.settingsOpen)
        .onChange(of: store.selectedID) { _, _ in onLayout() }
        .onChange(of: store.collapsed) { _, _ in onLayout() }
        .onChange(of: store.lastUpdated) { _, _ in onLayout() }
        .onChange(of: store.coupledTrailing) { _, _ in onLayout() }
        .onChange(of: store.settingsOpen) { _, _ in onLayout() }
        .onChange(of: store.providers.count) { _, _ in onLayout() }
        .onChange(of: store.parked.count) { _, _ in onLayout() }
        .onAppear { onLayout() }
    }

    private func morphingPill(pillW: CGFloat, pillH: CGFloat, scoop: CGFloat, layout: DockLayout) -> some View {
        ZStack(alignment: .top) {
            Group {
                if layout.coupled {
                    DockSurface(shape: CoupledShell(scoop: scoop), stroke: false)
                } else {
                    DockSurface(shape: Capsule(style: .continuous), stroke: true)
                }
            }
            .shadow(
                color: layout.coupled ? .clear : .black.opacity(0.45),
                radius: store.collapsed ? 8 : 18,
                y: store.collapsed ? 3 : 8
            )
            .frame(width: pillW, height: pillH)

            capsuleContent
                .frame(width: DockLayout.capsuleWidth, height: layout.expandedCapsuleHeight)
                .opacity(store.collapsed ? 0 : 1)
                .allowsHitTesting(!store.collapsed)
                .frame(width: pillW, height: pillH, alignment: .center)
                .clipped()
        }
        .frame(width: pillW, height: pillH)
        .contentShape(DockHitShape(scoop: scoop))
        .onTapGesture {
            if store.collapsed {
                store.setCollapsed(false)
            }
        }
        .onHover { hovering in
            if store.collapsed, hovering {
                store.setCollapsed(false)
            }
        }
        .contextMenu { dockMenu }
        .help(store.collapsed ? "Clique para expandir" : "Arraste para mover · encosta na direita para acoplar")
        .accessibilityLabel(store.collapsed ? "Expandir Usage Dock" : "Usage Dock")
    }

    private var capsuleContent: some View {
        VStack(spacing: DockLayout.ringSpacing) {
            ForEach(store.providers) { provider in
                ringRow(for: provider)
            }
            VStack(spacing: 2) {
                GearArc()
                    .stroke(
                        Color.white.opacity(0.14),
                        style: StrokeStyle(lineWidth: 1.5, lineCap: .round)
                    )
                    .frame(width: 22, height: 7)
                gearButton
            }
            .padding(.top, 2)
        }
        .padding(.top, DockLayout.capsuleTopPad)
        .padding(.bottom, DockLayout.capsuleBottomPad)
        .padding(.horizontal, 10)
        .frame(width: DockLayout.capsuleWidth)
    }

    @ViewBuilder
    private func ringRow(for provider: ProviderUsage) -> some View {
        let isSelected = store.selectedID == provider.id
        RingButton(provider: provider, selected: isSelected) {
            store.select(provider.id)
        } onHoverChange: { hovering in
            if hovering { store.pointerEnteredRing(provider.id) }
            else { store.pointerExitedRing(provider.id) }
        }
        .frame(height: DockLayout.ringRow)
    }

    private var gearButton: some View {
        Button {
            if store.settingsOpen {
                store.closeSettings()
            } else {
                store.openSettings()
            }
        } label: {
            Image(systemName: "gearshape")
                .font(.system(size: 13, weight: .regular))
                .foregroundStyle(Color.white.opacity(store.settingsOpen ? 0.92 : 0.55))
                .frame(width: 22, height: 22)
                .contentShape(Circle())
        }
        .buttonStyle(QuietButtonStyle())
        .help("Ajustes")
        .accessibilityLabel("Ajustes")
    }

    @ViewBuilder
    private var dockMenu: some View {
        Button(store.isLoading ? "Atualizando…" : "Atualizar") {
            Task { await store.refresh() }
        }
        Button(store.collapsed ? "Expandir" : "Recolher") {
            store.setCollapsed(!store.collapsed)
        }
        Button("Ajustes") { store.openSettings() }
        Button("Reposicionar à direita", action: onResetPosition)
        Divider()
        Button("Sair", action: onQuit)
    }
}

struct RingButton: View {
    let provider: ProviderUsage
    let selected: Bool
    let action: () -> Void
    var onHoverChange: (Bool) -> Void = { _ in }
    @State private var hovering = false

    private var band: UsageBand {
        UsageBand.band(for: provider.usedPercent, ok: provider.ok)
    }

    private var active: Bool { selected || hovering }
    private var critical: Bool { provider.ok && band == .critical }
    private var exhausted: Bool { provider.ok && provider.ringPercent >= 99.5 }
    private var ringWidth: CGFloat { exhausted ? 3.8 : 3.2 }
    /// Codenotch 1.15: leitura velha esmaece; o número continua o último bom.
    private var ringOpacity: Double {
        if !provider.ok { return 0.5 }
        return provider.isAged ? 0.45 : 1
    }

    private var ringProgress: CGFloat {
        CGFloat(provider.ringPercent / 100)
    }

    var body: some View {
        Button(action: action) {
            VStack(spacing: 4) {
                ringGraphic
                .frame(width: DockLayout.ringIcon, height: DockLayout.ringIcon)
                .overlay {
                    BrandMark(id: provider.id, tone: active ? .dark : .light)
                        .frame(width: 20, height: 20)
                }
                .scaleEffect(active ? 1.04 : 1)
                .animation(.easeOut(duration: 0.16), value: active)
                .opacity(ringOpacity)

                Text(provider.ok ? "\(Int(provider.ringPercent.rounded()))%" : "—")
                    .font(.system(size: 12, weight: .semibold, design: .rounded))
                    .monospacedDigit()
                    .foregroundStyle(
                        provider.ok
                            ? (exhausted ? band.ring : DockTheme.text)
                            : DockTheme.muted
                    )
                    .contentTransition(.numericText())
                    .animation(.easeInOut(duration: 0.4), value: Int(provider.ringPercent.rounded()))
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .contentShape(Rectangle())
        }
        .buttonStyle(QuietButtonStyle())
        .onHover { hovering in
            self.hovering = hovering
            onHoverChange(hovering)
        }
        .help(ringHelp)
        .accessibilityAddTraits(selected ? .isSelected : [])
        .accessibilityLabel(provider.name)
    }

    private var ringHelp: String {
        if provider.isAged { return "\(provider.name) · leitura antiga" }
        if provider.ok { return provider.name }
        return provider.error ?? provider.name
    }

    private var ringGraphic: some View {
        TimelineView(.animation(minimumInterval: 1.0 / 24, paused: !critical)) { context in
            let wave = alertWave(at: context.date)
            ZStack {
                Circle()
                    .fill(Color.white)
                    .frame(width: 28, height: 28)
                    .opacity(active ? 1 : 0)
                    .animation(.easeOut(duration: 0.16), value: active)

                Circle()
                    .stroke(
                        exhausted ? band.ring.opacity(0.45) : DockTheme.track,
                        style: StrokeStyle(lineWidth: ringWidth, lineCap: .round)
                    )
                    .padding(ringWidth / 2)

                Circle()
                    .trim(from: 0, to: provider.ok ? ringProgress : 0)
                    .stroke(
                        band.ring,
                        style: StrokeStyle(lineWidth: ringWidth, lineCap: .round)
                    )
                    .padding(ringWidth / 2)
                    .rotationEffect(.degrees(-90))
                    .shadow(color: alertShadowColor(wave: wave), radius: alertShadowRadius(wave: wave))
                    .animation(.easeInOut(duration: 0.4), value: provider.ringPercent)
            }
        }
    }

    private func alertWave(at date: Date) -> CGFloat {
        guard critical else { return 0 }
        let t = date.timeIntervalSinceReferenceDate
        return (sin(t * Double.pi / 1.15) + 1) / 2
    }

    private func alertShadowColor(wave: CGFloat) -> Color {
        let opacity = exhausted
            ? 0.45 + wave * 0.4
            : (critical ? 0.16 + wave * 0.4 : 0)
        return band.ring.opacity(opacity)
    }

    private func alertShadowRadius(wave: CGFloat) -> CGFloat {
        exhausted ? 5 + wave * 6 : (critical ? 2.5 + wave * 5 : 0)
    }
}

private struct QuietButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .contentShape(Rectangle())
            .opacity(configuration.isPressed ? 0.8 : 1)
    }
}
