import AppKit
import Combine
import SwiftUI

@MainActor
final class OverlayController {
    private let store: UsageStore
    private var panel: NSPanel?
    private var hosting: NSHostingController<DockView>?
    private var cancellables = Set<AnyCancellable>()
    private var layout = DockLayout(collapsed: false, selectedIndex: nil, ringCount: 5, popoutHeight: 0, coupled: true)
    private var anchorMaxX: CGFloat
    private var anchorMaxY: CGFloat
    private var dragStartMaxX: CGFloat = 0
    private var dragStartMaxY: CGFloat = 0
    private var dragStartMouse: NSPoint = .zero
    private var dragging = false
    private var dragArmed = false
    private var suppressClick = false
    private var placing = false
    private var eventMonitors: [Any] = []

    private enum Defaults {
        static let maxX = "usageDock.anchorMaxX"
        static let maxY = "usageDock.anchorMaxY"
        static let coupled = "usageDock.coupledTrailing"
    }

    init(store: UsageStore) {
        self.store = store
        let defaults = UserDefaults.standard
        if defaults.object(forKey: Defaults.maxX) != nil,
           defaults.object(forKey: Defaults.maxY) != nil {
            anchorMaxX = CGFloat(defaults.double(forKey: Defaults.maxX))
            anchorMaxY = CGFloat(defaults.double(forKey: Defaults.maxY))
        } else {
            let visible = NSScreen.main?.visibleFrame
                ?? NSRect(x: 0, y: 0, width: 1440, height: 900)
            let capsuleHeight = DockLayout(
                collapsed: false,
                selectedIndex: nil,
                ringCount: 5,
                popoutHeight: 0,
                coupled: true
            ).capsuleHeight
            anchorMaxX = visible.maxX
            anchorMaxY = visible.midY + capsuleHeight / 2
        }
    }

    func show() {
        let controller = NSHostingController(
            rootView: DockView(
                store: store,
                onQuit: { NSApp.terminate(nil) },
                onLayout: { [weak self] in
                    DispatchQueue.main.async { self?.syncLayoutIfNeeded() }
                },
                onResetPosition: { [weak self] in self?.resetPosition() }
            )
        )
        controller.sizingOptions = []
        controller.safeAreaRegions = []
        let root = MovableRootView(frame: NSRect(origin: .zero, size: layout.panelSize))
        root.wantsLayer = true
        root.layer?.backgroundColor = NSColor.clear.cgColor
        root.layer?.masksToBounds = false
        controller.view.frame = root.bounds
        controller.view.autoresizingMask = [.width, .height]
        controller.view.wantsLayer = true
        controller.view.layer?.backgroundColor = NSColor.clear.cgColor
        controller.view.layer?.masksToBounds = false
        root.addSubview(controller.view)
        self.hosting = controller

        let panel = NSPanel(
            contentRect: NSRect(origin: .zero, size: layout.panelSize),
            styleMask: [.borderless, .nonactivatingPanel],
            backing: .buffered,
            defer: false
        )
        panel.isFloatingPanel = true
        panel.level = .statusBar
        panel.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]
        panel.isOpaque = false
        panel.backgroundColor = .clear
        panel.hasShadow = false
        panel.hidesOnDeactivate = false
        panel.becomesKeyOnlyIfNeeded = true
        panel.acceptsMouseMovedEvents = true
        panel.ignoresMouseEvents = false
        panel.isMovable = false
        panel.isMovableByWindowBackground = false
        panel.animationBehavior = .none
        panel.appearance = NSAppearance(named: .darkAqua)
        panel.contentView = root
        panel.isReleasedWhenClosed = false
        self.panel = panel

        store.objectWillChange
            .receive(on: RunLoop.main)
            .sink { [weak self] _ in
                DispatchQueue.main.async {
                    self?.syncLayoutIfNeeded()
                }
            }
            .store(in: &cancellables)

        NotificationCenter.default.addObserver(
            forName: NSApplication.didChangeScreenParametersNotification,
            object: nil,
            queue: .main
        ) { [weak self] _ in
            Task { @MainActor in self?.syncLayoutIfNeeded(force: true) }
        }

        NSWorkspace.shared.notificationCenter.addObserver(
            forName: NSWorkspace.didWakeNotification,
            object: nil,
            queue: .main
        ) { [weak self] _ in
            Task { @MainActor in self?.syncLayoutIfNeeded(force: true) }
        }
        NSWorkspace.shared.notificationCenter.addObserver(
            forName: NSWorkspace.screensDidWakeNotification,
            object: nil,
            queue: .main
        ) { [weak self] _ in
            Task { @MainActor in self?.syncLayoutIfNeeded(force: true) }
        }

        NotificationCenter.default.addObserver(
            forName: NSWindow.didMoveNotification,
            object: panel,
            queue: .main
        ) { [weak self] _ in
            Task { @MainActor in self?.captureAnchorFromWindow() }
        }

        store.coupledTrailing = restoredCoupling(visible: visibleFrame())
        if store.coupledTrailing {
            anchorMaxX = visibleFrame().maxX
        }
        syncLayoutIfNeeded(force: true)
        if store.coupledTrailing {
            snapIfNearTrailingEdge()
        }
        installDismissMonitors()
        installDragMonitors()
        panel.orderFrontRegardless()
    }

    private func installDragMonitors() {
        if let down = NSEvent.addLocalMonitorForEvents(matching: .leftMouseDown, handler: { [weak self] event in
            self?.armDrag(with: event)
            return event
        }) {
            eventMonitors.append(down)
        }
        if let dragged = NSEvent.addLocalMonitorForEvents(matching: .leftMouseDragged, handler: { [weak self] event in
            self?.continueDrag()
            return event
        }) {
            eventMonitors.append(dragged)
        }
        if let up = NSEvent.addLocalMonitorForEvents(matching: .leftMouseUp, handler: { [weak self] event in
            guard let self else { return event }
            return self.finishDrag() ? nil : event
        }) {
            eventMonitors.append(up)
        }
        if let globalUp = NSEvent.addGlobalMonitorForEvents(matching: .leftMouseUp, handler: { [weak self] _ in
            Task { @MainActor in
                guard let self, self.dragging else { return }
                _ = self.finishDrag()
            }
        }) {
            eventMonitors.append(globalUp)
        }
    }

    private func armDrag(with event: NSEvent) {
        guard let panel, event.window === panel, isInCapsule(event.locationInWindow) else {
            dragArmed = false
            return
        }
        dragArmed = true
        suppressClick = false
        dragStartMouse = NSEvent.mouseLocation
        dragStartMaxX = anchorMaxX
        dragStartMaxY = anchorMaxY
    }

    private func continueDrag() {
        guard dragArmed else { return }
        let mouse = NSEvent.mouseLocation
        if !dragging {
            let dx = mouse.x - dragStartMouse.x
            let dy = mouse.y - dragStartMouse.y
            if (dx * dx) + (dy * dy) < 36 { return }
            dragging = true
            store.beginDrag()
        }
        drag()
    }

    /// Returns true when the mouse-up should not become a SwiftUI click.
    private func finishDrag() -> Bool {
        dragArmed = false
        if dragging {
            endDrag()
            suppressClick = true
            return true
        }
        if suppressClick {
            suppressClick = false
            return true
        }
        return false
    }

    private func isInCapsule(_ windowPoint: NSPoint) -> Bool {
        let width = layout.collapsed ? DockLayout.peekWidth : DockLayout.capsuleWidth
        let panelWidth = panel?.frame.width ?? layout.panelSize.width
        return windowPoint.x >= panelWidth - width - 2
    }

    private func installDismissMonitors() {
        let localKey = NSEvent.addLocalMonitorForEvents(matching: .keyDown) { [weak self] event in
            guard event.keyCode == 53, let self else { return event }
            return self.handleEscape() ? nil : event
        }
        if let localKey { eventMonitors.append(localKey) }

        if let globalKey = NSEvent.addGlobalMonitorForEvents(matching: .keyDown, handler: { [weak self] event in
            guard event.keyCode == 53 else { return }
            Task { @MainActor in _ = self?.handleEscape() }
        }) {
            eventMonitors.append(globalKey)
        }

        if let globalMouse = NSEvent.addGlobalMonitorForEvents(matching: [.leftMouseDown, .rightMouseDown], handler: { [weak self] _ in
            Task { @MainActor in self?.dismissIfClickOutside() }
        }) {
            eventMonitors.append(globalMouse)
        }
    }

    /// Esc fecha ajustes, depois o card. Só recolhe a pílula se o ponteiro estiver
    /// sobre o dock: Esc no editor não pode sumir com o HUD (SPEC estado 7).
    /// Retorna true quando o evento foi consumido.
    private func handleEscape() -> Bool {
        if store.settingsOpen {
            store.closeSettings()
            return true
        }
        if store.selectedID != nil {
            store.dismiss()
            return true
        }
        if !store.collapsed, let panel, panel.frame.contains(NSEvent.mouseLocation) {
            store.setCollapsed(true)
            return true
        }
        return false
    }

    private func dismissIfClickOutside() {
        guard let panel else { return }
        if panel.frame.contains(NSEvent.mouseLocation) { return }
        if store.settingsOpen {
            store.closeSettings()
        }
        if store.selectedID != nil {
            store.dismiss()
        }
    }

    private func drag() {
        guard dragging else { return }
        let mouse = NSEvent.mouseLocation
        anchorMaxX = dragStartMaxX + (mouse.x - dragStartMouse.x)
        anchorMaxY = dragStartMaxY + (mouse.y - dragStartMouse.y)
        clampAnchor()
        updateCoupling(magnetize: false)
        apply(size: layout.panelSize)
    }

    private func endDrag() {
        dragging = false
        store.endDrag()
        snapIfNearTrailingEdge()
        persistAnchor()
        apply(size: layout.panelSize)
    }

    private func resetPosition() {
        let visible = visibleFrame()
        anchorMaxX = visible.maxX
        anchorMaxY = visible.midY + layout.capsuleHeight / 2
        store.coupledTrailing = true
        persistAnchor()
        syncLayoutIfNeeded(force: true)
    }

    private func snapIfNearTrailingEdge() {
        updateCoupling(magnetize: true)
        if store.coupledTrailing {
            syncLayoutIfNeeded(force: true)
        }
    }

    private func updateCoupling(magnetize: Bool) {
        let visible = visibleFrame()
        let near = visible.maxX - anchorMaxX <= DockLayout.snapDistance
        if near {
            if magnetize { anchorMaxX = visible.maxX }
            if !store.coupledTrailing { store.coupledTrailing = true }
        } else if store.coupledTrailing {
            store.coupledTrailing = false
        }
        layout = DockLayout.from(store: store)
    }

    private func captureAnchorFromWindow() {
        guard !dragging, !placing, let panel else { return }
        let frame = panel.frame
        if store.coupledTrailing {
            anchorMaxX = visibleFrame().maxX
            anchorMaxY = frame.maxY - layout.scoopPad
        } else {
            anchorMaxX = frame.maxX
            anchorMaxY = frame.maxY - layout.scoopPad
        }
        clampAnchor()
        persistAnchor()
    }

    private func clampAnchor() {
        let visible = visibleFrame()
        let capWidth = DockLayout.capsuleWidth
        let capHeight = layout.expandedCapsuleHeight
        let scoop = layout.scoopPad
        anchorMaxX = min(max(anchorMaxX, visible.minX + capWidth), visible.maxX)
        anchorMaxY = min(
            max(anchorMaxY, visible.minY + capHeight + scoop),
            visible.maxY - scoop
        )
    }

    private func restoredCoupling(visible: NSRect) -> Bool {
        let defaults = UserDefaults.standard
        if defaults.object(forKey: Defaults.coupled) != nil {
            return defaults.bool(forKey: Defaults.coupled)
        }
        return visible.maxX - anchorMaxX <= DockLayout.snapDistance
    }

    private func persistAnchor() {
        UserDefaults.standard.set(Double(anchorMaxX), forKey: Defaults.maxX)
        UserDefaults.standard.set(Double(anchorMaxY), forKey: Defaults.maxY)
        UserDefaults.standard.set(store.coupledTrailing, forKey: Defaults.coupled)
        UserDefaults.standard.synchronize()
    }

    private func syncLayoutIfNeeded(force: Bool = false) {
        if dragging {
            layout = DockLayout.from(store: store)
            updateHitTesting()
            return
        }
        let newLayout = DockLayout.from(store: store)
        let sizeChanged = newLayout.panelSize != layout.panelSize
            || newLayout.coupled != layout.coupled
        layout = newLayout
        updateHitTesting()
        guard force || sizeChanged else { return }
        apply(size: newLayout.panelSize)
    }

    private func apply(size: NSSize) {
        guard let hosting, let panel else { return }
        hosting.view.setFrameSize(size)
        panel.contentView?.setFrameSize(size)
        place(size: size)
    }

    private func place(size: NSSize) {
        guard let panel, let hosting else { return }
        clampAnchor()
        if layout.coupled && !dragging {
            anchorMaxX = visibleFrame().maxX
        }
        let maxX = anchorMaxX
        let maxY = anchorMaxY
        let scoop = layout.scoopPad
        let frame = NSRect(
            x: maxX - size.width,
            y: maxY + scoop - size.height,
            width: size.width,
            height: size.height
        )
        hosting.view.frame = NSRect(origin: .zero, size: size)
        hosting.view.autoresizingMask = [.width, .height]
        placing = true
        panel.setFrame(frame, display: true, animate: false)
        Task { @MainActor in
            self.placing = false
            self.updateHitTesting()
        }
    }

    private func updateHitTesting() {
        guard let root = panel?.contentView as? MovableRootView else { return }
        root.capsuleWidth = store.collapsed ? DockLayout.peekWidth : DockLayout.capsuleWidth
        root.popoutOpen = !store.collapsed && (store.selectedID != nil || store.settingsOpen)
        root.collapsed = store.collapsed
        root.peekHeight = DockLayout.peekHeight
        root.shellHeight = layout.expandedShellHeight
        root.popoutTopFromTop = store.settingsOpen
            ? layout.scoopPad + 8
            : layout.selectedIndex.map { layout.popoutTopPadding(index: $0) } ?? 0
        root.popoutHeight = layout.popoutHeight
        root.popoutWidth = DockLayout.popoutWidth
        root.popoutGap = DockLayout.popoutGap
    }

    private func visibleFrame() -> NSRect {
        if let screen = panel?.screen {
            return screen.visibleFrame
        }
        let probe = NSPoint(x: min(max(anchorMaxX - 4, 0), 10_000), y: min(max(anchorMaxY - 4, 0), 10_000))
        let screen = NSScreen.screens.first { $0.frame.contains(probe) }
            ?? NSScreen.main
            ?? NSScreen.screens.first
        return screen?.visibleFrame ?? NSRect(x: 0, y: 0, width: 1440, height: 900)
    }
}

private final class MovableRootView: NSView {
    var capsuleWidth: CGFloat = DockLayout.capsuleWidth
    var popoutOpen = false
    var collapsed = false
    var peekHeight: CGFloat = DockLayout.peekHeight
    var shellHeight: CGFloat = 400
    var popoutTopFromTop: CGFloat = 0
    var popoutHeight: CGFloat = 0
    var popoutWidth: CGFloat = DockLayout.popoutWidth
    var popoutGap: CGFloat = DockLayout.popoutGap

    override var mouseDownCanMoveWindow: Bool { false }

    override func hitTest(_ point: NSPoint) -> NSView? {
        if collapsed {
            let w = DockLayout.peekWidth
            let h = peekHeight
            let peekTopFromTop = (shellHeight - h) / 2
            let peekMinY = bounds.height - (peekTopFromTop + h)
            let peekMaxY = bounds.height - peekTopFromTop
            if point.x >= bounds.maxX - w - 2,
               point.y >= peekMinY - 2,
               point.y <= peekMaxY + 2 {
                return super.hitTest(point)
            }
            return nil
        }
        if point.x >= bounds.maxX - capsuleWidth - 2 {
            return super.hitTest(point)
        }
        if popoutOpen {
            let popoutMaxX = bounds.maxX - capsuleWidth - popoutGap
            let popoutMinX = popoutMaxX - popoutWidth
            let popoutMaxY = bounds.maxY - popoutTopFromTop
            let popoutMinY = popoutMaxY - popoutHeight
            if point.x >= popoutMinX,
               point.x <= popoutMaxX + 2,
               point.y >= popoutMinY - 2,
               point.y <= popoutMaxY + 2 {
                return super.hitTest(point)
            }
        }
        return nil
    }
}
