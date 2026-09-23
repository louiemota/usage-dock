import SwiftUI

struct SettingsModal: View {
    @ObservedObject var store: UsageStore
    var onQuit: () -> Void
    var onResetPosition: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack(spacing: 8) {
                Image(systemName: "gearshape.fill")
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundStyle(DockTheme.text.opacity(0.9))
                Text("Usage Dock")
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundStyle(DockTheme.text)
                Spacer(minLength: 8)
                Button(action: store.closeSettings) {
                    Image(systemName: "xmark")
                        .font(.system(size: 11, weight: .bold))
                        .foregroundStyle(DockTheme.muted)
                        .frame(width: 22, height: 22)
                        .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .help("Fechar")
            }

            Text("0–39% verde · 40–69% amarelo · 70–89% laranja · 90–100% vermelho")
                .font(.system(size: 11))
                .foregroundStyle(DockTheme.muted)
                .fixedSize(horizontal: false, vertical: true)

            if let updated = store.lastUpdated {
                Text(store.providers.contains(where: \.isAged)
                     ? "Leitura antiga — último ok \(updated.formatted(date: .omitted, time: .shortened))"
                     : "Atualizado \(updated.formatted(date: .omitted, time: .shortened))")
                    .font(.system(size: 11))
                    .foregroundStyle(store.providers.contains(where: \.isAged) ? UsageBand.hot.ring : DockTheme.muted)
            }
            if let error = store.lastError, !error.isEmpty {
                Text(error)
                    .font(.system(size: 11))
                    .foregroundStyle(UsageBand.hot.ring)
                    .fixedSize(horizontal: false, vertical: true)
            }

            if !store.parked.isEmpty {
                Text("Fora da fila")
                    .font(.system(size: 11, weight: .semibold))
                    .foregroundStyle(DockTheme.muted)
                ForEach(store.parked) { item in
                    HStack(alignment: .top, spacing: 8) {
                        VStack(alignment: .leading, spacing: 2) {
                            Text(item.name)
                                .font(.system(size: 12, weight: .medium))
                                .foregroundStyle(DockTheme.text)
                            Text(item.reason)
                                .font(.system(size: 10))
                                .foregroundStyle(DockTheme.muted)
                                .lineLimit(2)
                                .fixedSize(horizontal: false, vertical: true)
                        }
                        Spacer(minLength: 6)
                        Button("Vigiar") {
                            store.restoreWatch(item.id)
                        }
                        .buttonStyle(.plain)
                        .font(.system(size: 11, weight: .semibold))
                        .foregroundStyle(DockTheme.text)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 4)
                        .background(
                            RoundedRectangle(cornerRadius: 6, style: .continuous)
                                .fill(Color.white.opacity(0.08))
                        )
                    }
                }
            }

            VStack(spacing: 6) {
                modalButton(store.isLoading ? "Atualizando…" : "Atualizar") {
                    Task { await store.refresh() }
                }
                modalButton("Recolher") {
                    store.setCollapsed(true)
                }
                modalButton("Reposicionar à direita", action: onResetPosition)
                SettingsLink {
                    Text("Ajustes do sistema…")
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
                .buttonStyle(ModalRowStyle())
                modalButton("Sair", destructive: true, action: onQuit)
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 14)
        .frame(width: DockLayout.popoutWidth, alignment: .leading)
        .background(
            DockSurface(
                shape: RoundedRectangle(cornerRadius: 13, style: .continuous),
                stroke: true
            )
            .shadow(color: .black.opacity(0.42), radius: 16, y: 7)
        )
    }

    private func modalButton(
        _ title: String,
        disabled: Bool = false,
        destructive: Bool = false,
        action: @escaping () -> Void
    ) -> some View {
        Button(action: action) {
            Text(title)
                .font(.system(size: 12, weight: .medium))
                .foregroundStyle(destructive ? UsageBand.hot.ring : DockTheme.text)
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.horizontal, 10)
                .padding(.vertical, 7)
                .background(
                    RoundedRectangle(cornerRadius: 8, style: .continuous)
                        .fill(Color.white.opacity(0.06))
                )
        }
        .buttonStyle(.plain)
        .disabled(disabled)
        .opacity(disabled ? 0.55 : 1)
    }
}

private struct ModalRowStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.system(size: 12, weight: .medium))
            .foregroundStyle(DockTheme.text)
            .padding(.horizontal, 10)
            .padding(.vertical, 7)
            .background(
                RoundedRectangle(cornerRadius: 8, style: .continuous)
                    .fill(Color.white.opacity(configuration.isPressed ? 0.1 : 0.06))
            )
    }
}
