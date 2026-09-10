pragma ComponentBehavior: Bound
import QtQuick
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
                // A small launch arrow, drawn with theme-colored geometry.
                Rectangle { x: parent.width * 0.20; y: parent.height * 0.63; width: parent.width * 0.63; height: 2; rotation: -45; transformOrigin: Item.Left; color: root.barForegroundColor }
                Rectangle { x: parent.width * 0.40; y: parent.height * 0.19; width: parent.width * 0.43; height: 2; color: root.barForegroundColor }
                Rectangle { x: parent.width * 0.76; y: parent.height * 0.19; width: 2; height: parent.height * 0.43; color: root.barForegroundColor }
                Rectangle { x: parent.width * 0.17; y: parent.height * 0.81; width: parent.width * 0.66; height: 2; color: root.barForegroundColor; opacity: 0.55 }
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
