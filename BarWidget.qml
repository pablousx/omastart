pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Shapes
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui as Ui

Ui.BarWidget {
    id: root
    moduleName: "io.github.pablousx.omastart"
    implicitWidth: button.implicitWidth
    implicitHeight: button.implicitHeight
    readonly property bool opened: panelLoader.item ? panelLoader.item.opened : false
    readonly property bool popoutSwitchClosing: panelLoader.item ? panelLoader.item.popoutSwitchClosing : false

    function open() { if (panelLoader.item) panelLoader.item.open() }
    function close() { if (panelLoader.item) panelLoader.item.close() }
    function toggle() { if (opened) close(); else open() }
    function closeForPopoutSwitch() { if (panelLoader.item) panelLoader.item.closeForPopoutSwitch() }
    function injectPanel() {
        if (!panelLoader.item) return
        panelLoader.item.bar = root.bar
        panelLoader.item.settings = root.settings
        panelLoader.item.anchorItem = button
        panelLoader.item.hostWidget = root
    }
    function currentPanel() {
        var widgets = root.bar && typeof root.bar.moduleWidgets === "function" ? root.bar.moduleWidgets(root.moduleName) : [root]
        for (var i = 0; i < widgets.length; i++) {
            if (widgets[i].opened && typeof widgets[i].ownPanel === "function") return widgets[i].ownPanel()
        }
        return panelLoader.item
    }
    function ownPanel() { return panelLoader.item }

    onBarChanged: injectPanel()
    onSettingsChanged: injectPanel()

    Ui.BarIconButton {
        id: button
        anchors.fill: parent
        bar: root.bar
        tooltipText: "omastart · Startup applications"
        iconComponent: Component {
            Item {
                Shape {
                    anchors.centerIn: parent
                    width: 24
                    height: 24
                    scale: Math.min(parent.width, parent.height) / 24
                    // One continuous curve: a 45-degree launch, ending vertical.
                    ShapePath {
                        strokeColor: root.barForegroundColor
                        strokeWidth: 1.8
                        fillColor: "transparent"
                        capStyle: ShapePath.RoundCap
                        joinStyle: ShapePath.RoundJoin
                        startX: 4.5
                        startY: 15.5
                        PathCubic { control1X: 10.5; control1Y: 9.5; control2X: 14; control2Y: 10; x: 14; y: 3.5 }
                        PathMove { x: 10; y: 7.5 }
                        PathLine { x: 14; y: 3.5 }
                        PathLine { x: 18; y: 7.5 }
                    }
                    ShapePath {
                        strokeColor: root.barForegroundColor
                        strokeWidth: 1.8
                        fillColor: "transparent"
                        capStyle: ShapePath.RoundCap
                        startX: 4
                        startY: 20.5
                        PathLine { x: 20; y: 20.5 }
                    }
                }
            }
        }
        onPressed: function(mouseButton) { if (mouseButton === Qt.LeftButton) root.toggle() }
    }
    readonly property color barForegroundColor: bar ? bar.barForeground : Color.foreground

    Loader {
        id: panelLoader
        active: true
        visible: false
        source: Qt.resolvedUrl("Panel.qml")
        onLoaded: { root.injectPanel(); Qt.callLater(root.injectPanel) }
    }

    IpcHandler {
        enabled: !!root.QsWindow.window && root.QsWindow.window.screen === Quickshell.screens[0]
        target: root.moduleName
        // UI-only inspection controls. No mutation endpoint is exposed over IPC.
        function inspect(): string { return JSON.stringify(root.currentPanel().inspect()) }
        function instances(): string {
            var widgets = root.bar && typeof root.bar.moduleWidgets === "function" ? root.bar.moduleWidgets(root.moduleName) : [root]
            return JSON.stringify(widgets.map(function(widget) { return widget.ownPanel().inspect() }))
        }
        function openOnScreen(screen: string): void {
            var widgets = root.bar && typeof root.bar.moduleWidgets === "function" ? root.bar.moduleWidgets(root.moduleName) : [root]
            for (var i = 0; i < widgets.length; i++) {
                var panel = widgets[i].ownPanel()
                if (panel.inspect().geometry.screen === screen) widgets[i].open()
            }
        }
        function search(query: string): void { root.currentPanel().setSearch(query) }
        function expand(id: string): void { root.currentPanel().expandedId = id }
        function filters(source: string, status: string, system: string): void {
            root.currentPanel().sourceFilter = source
            root.currentPanel().statusFilter = status
            root.currentPanel().showSystem = system === "true"
        }
        function picker(show: string): void {
            var panel = root.currentPanel()
            if (show === "true" && !panel.adding) panel.enterPicker()
            else if (show !== "true" && panel.adding) panel.leavePicker()
        }
        function filterOptions(show: string): void { root.currentPanel().filtersOpen = show === "true" }
        function refresh(): void { root.currentPanel().refresh(true) }
    }
}
