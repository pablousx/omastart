pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui as Ui
import "Model.js" as Model

Ui.Panel {
    id: root
    moduleName: "io.github.pablousx.omastart"
    manageIpc: false
    property var anchorItem: null
    property var hostWidget: null
    property var inventory: ({applications: [], catalog: [], warnings: [], counts: {applications: 0, enabled: 0, system: 0}})
    property bool loaded: false
    property bool busy: false
    property string error: ""
    property string message: ""
    property string sourceFilter: "all"
    property string statusFilter: "all"
    property bool showSystem: false
    property bool adding: false
    property string expandedId: ""
    property string pendingId: ""
    // Supplied only by the isolated QML harness. It disables every backend invocation.
    property var fixtureData: null
    readonly property var applications: Model.filtered(inventory.applications, searchField.text, sourceFilter, statusFilter, showSystem)
    readonly property var choices: Model.catalogFiltered(inventory.catalog, searchField.text)
    readonly property string backendPath: decodeURIComponent(Qt.resolvedUrl("backend/omastart.py").toString().replace(/^file:\/\//, ""))

    function open() {
        root.controller.show()
        refresh()
    }
    function setSearch(value) { searchField.text = value }
    function inspect() {
        return {opened: opened, loaded: loaded, busy: busy, error: error, adding: adding, searchFocused: searchField.activeFocus,
                query: searchField.text, expandedId: expandedId, counts: inventory.counts,
                geometry: {x: popup.cardOrigin.x, y: popup.cardOrigin.y, width: popup.contentWidth, height: popup.contentHeight,
                           screen: "screen" in popup && popup.screen ? popup.screen.name : ""},
                rows: applications.map(function(a) { return {id: a.id, name: a.name, status: a.status,
                    sources: a.sources.map(function(s) { return {id: s.id, kind: s.kind, enabled: s.enabled, readOnly: s.readOnly, generatedUnits: s.generatedUnits || []} })} })}
    }
    function request(payload) {
        if (busy || fixtureData !== null) return
        error = ""
        if (payload.action !== "scan") message = ""
        pendingId = payload.id || ""
        busy = true
        process.command = ["python3", "-B", root.backendPath, JSON.stringify(payload)]
        process.running = true
    }
    function refresh() {
        if (fixtureData !== null) { inventory = fixtureData; loaded = true; return }
        request({action: "scan"})
    }
    function change(item) {
        if (busy || item.readOnly) return
        request({action: "toggle", id: item.id, revision: item.revision, enabled: !item.enabled})
    }
    function addApplication(app) {
        if (app.exists || busy) return
        request({action: "add", id: app.id, revision: app.revision})
    }
    function finish(output, errors, exitCode) {
        busy = false
        pendingId = ""
        try {
            var result = JSON.parse(output)
            if (!result.ok) {
                error = result.error || "The change could not be saved. Refresh and try again."
                return
            }
            if (exitCode !== 0) { error = "The backend exited before completing its request."; return }
            var scrollY = listView.contentY
            var selected = listView.currentItem ? listView.currentItem.entry.id : ""
            inventory = result
            loaded = true
            if (result.message) { message = result.message; messageTimer.restart() }
            Qt.callLater(function() {
                var rows = root.adding ? root.choices : root.applications
                listView.currentIndex = rows.findIndex(function(row) { return row.id === selected })
                listView.contentY = Math.max(listView.originY, Math.min(scrollY, listView.originY + listView.contentHeight - listView.height))
            })
        } catch (e) {
            error = "Could not read startup information. " + (errors ? errors.slice(0, 240) : String(e))
        }
    }

    Process {
        id: process
        stdout: StdioCollector { id: output }
        stderr: StdioCollector { id: errors }
        onExited: function(exitCode) {
            var out = output.text
            var err = errors.text
            Qt.callLater(function() { root.finish(out, err, exitCode) })
        }
    }
    Timer {
        id: messageTimer
        interval: 6000
        onTriggered: root.message = ""
    }
    Timer {
        interval: 15000
        running: root.opened && root.fixtureData === null
        repeat: true
        onTriggered: root.refresh()
    }

    Ui.KeyboardPanel {
        id: popup
        anchorItem: root.anchorItem
        bar: root.bar
        owner: root.hostWidget || root
        open: root.opened
        focusTarget: searchField
        contentWidth: fittedContentWidth(Style.space(610))
        contentHeight: cappedContentHeight(Math.max(Style.space(480), Math.min(Style.space(860),
            Style.space(root.adding ? 250 : 365) + listView.contentHeight)))

        FocusScope {
            anchors.fill: parent
            Keys.onEscapePressed: function(event) {
                if (root.adding) { root.adding = false; searchField.text = "" }
                else root.close()
                event.accepted = true
            }

            ColumnLayout {
                anchors.fill: parent
                spacing: Style.space(14)

                RowLayout {
                    Layout.fillWidth: true
                    spacing: Style.space(12)
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: Style.space(4)
                        Label { text: root.adding ? "Add application" : "omastart"; font.pixelSize: Style.space(27); font.bold: true }
                        Label {
                            Layout.fillWidth: true
                            text: root.adding ? "Choose an installed app to start at login." : "Manage everything that starts with your Omarchy session."
                            color: Qt.alpha(Color.popups.text, 0.70)
                            font.pixelSize: Style.font.caption
                            wrapMode: Text.WordWrap
                        }
                    }
                    Ui.Button {
                        text: root.adding ? "Back" : "+ Add app"
                        focusable: true
                        bordered: true
                        enabled: root.loaded && !root.busy
                        onClicked: { root.adding = !root.adding; searchField.text = ""; searchField.forceActiveFocus() }
                    }
                    Ui.Button { text: "×"; fontSize: Style.space(24); focusable: true; tooltipText: "Close · Esc"; onClicked: root.close() }
                }

                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: Style.space(61)
                    visible: !root.adding
                    radius: Style.cornerRadius
                    color: Qt.alpha(Color.accent, 0.075)
                    border.color: Qt.alpha(Color.accent, 0.17)
                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: Style.space(13)
                        spacing: Style.space(10)
                        Label {
                            text: root.loaded ? String(root.inventory.counts.enabled) : "—"
                            font.pixelSize: Style.space(29)
                            font.bold: true
                            color: Color.accent
                        }
                        ColumnLayout {
                            spacing: 1
                            Layout.fillWidth: true
                            Label { text: "apps enabled at login"; font.bold: true }
                            Label { text: root.loaded ? root.inventory.counts.applications + " applications · three startup sources" : "Reading your session configuration…"; font.pixelSize: Style.font.caption; color: Qt.alpha(Color.popups.text, 0.70) }
                        }
                        Ui.Button { text: root.busy ? "Reading…" : "Refresh"; focusable: true; enabled: !root.busy; onClicked: root.refresh() }
                    }
                }

                Ui.TextField {
                    id: searchField
                    objectName: "searchField"
                    Layout.fillWidth: true
                    placeholderText: root.adding ? "Search installed applications…" : "Search apps, commands, or sources…"
                    Keys.onEscapePressed: function(event) {
                        if (text !== "") text = ""
                        else if (root.adding) root.adding = false
                        else root.close()
                        event.accepted = true
                    }
                    Keys.onDownPressed: function(event) { listView.forceActiveFocus(); if (listView.currentIndex < 0) listView.currentIndex = 0; event.accepted = true }
                }

                RowLayout {
                    Layout.fillWidth: true
                    visible: !root.adding
                    spacing: Style.space(5)
                    Repeater {
                        model: [{id:"all", title:"All sources"}, {id:"hyprland", title:"Hyprland"}, {id:"xdg", title:"XDG"}, {id:"systemd", title:"systemd"}]
                        Ui.Button {
                            required property var modelData
                            text: modelData.title
                            selected: root.sourceFilter === modelData.id
                            focusable: true
                            fontSize: Style.font.caption
                            horizontalPadding: Style.space(10)
                            onClicked: root.sourceFilter = modelData.id
                        }
                    }
                    Item { Layout.fillWidth: true }
                    Ui.Button {
                        text: root.statusFilter === "all" ? "Any status ▾" : root.statusFilter === "enabled" ? "Enabled ▾" : "Disabled ▾"
                        fontSize: Style.font.caption
                        focusable: true
                        tooltipText: "Cycle: all, enabled, disabled"
                        onClicked: root.statusFilter = root.statusFilter === "all" ? "enabled" : root.statusFilter === "enabled" ? "disabled" : "all"
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: notice.implicitHeight + Style.space(18)
                    visible: root.error !== "" || root.inventory.warnings.length > 0
                    radius: Style.cornerRadius
                    color: Qt.alpha(Color.urgent, 0.09)
                    Label {
                        id: notice
                        anchors.fill: parent
                        anchors.margins: Style.space(9)
                        text: root.error || root.inventory.warnings.join("\n")
                        wrapMode: Text.Wrap
                        font.pixelSize: Style.font.caption
                        color: Color.urgent
                        elide: Text.ElideNone
                    }
                }

                Repeater {
                    model: root.inventory.recoveries || []
                    Ui.Button {
                        required property var modelData
                        visible: modelData.recoverable
                        text: "Restore interrupted change"
                        tooltipText: modelData.item
                        focusable: true
                        bordered: true
                        enabled: !root.busy
                        onClicked: root.request({action: "recover", id: modelData.id, revision: modelData.revision})
                    }
                }

                ListView {
                    id: listView
                    objectName: "applicationList"
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    spacing: Style.space(5)
                    boundsBehavior: Flickable.StopAtBounds
                    model: root.adding ? root.choices : root.applications
                    currentIndex: -1
                    keyNavigationEnabled: true
                    highlightMoveDuration: 100
                    Controls.ScrollBar.vertical: Controls.ScrollBar { policy: Controls.ScrollBar.AsNeeded }
                    Keys.onReturnPressed: if (currentItem) currentItem.activate()
                    Keys.onSpacePressed: if (currentItem) currentItem.activate()
                    Keys.onEscapePressed: root.close()

                    delegate: ApplicationRow {
                        required property var modelData
                        required property int index
                        width: listView.width - Style.space(8)
                        entry: modelData
                        manager: root
                        picker: root.adding
                        hasCursor: listView.activeFocus && listView.currentIndex === index
                        onSelected: listView.currentIndex = index
                    }

                    Column {
                        anchors.centerIn: parent
                        width: parent.width * 0.85
                        spacing: Style.space(9)
                        visible: listView.count === 0
                        Label { width: parent.width; text: !root.loaded ? (root.busy ? "Finding your startup apps…" : "Startup information unavailable") : "No applications match"; horizontalAlignment: Text.AlignHCenter; font.bold: true; font.pixelSize: Style.font.subtitle }
                        Label { width: parent.width; text: !root.loaded ? "Hyprland · XDG autostart · User systemd" : "Try another search or adjust the filters."; color: Qt.alpha(Color.popups.text, 0.70); horizontalAlignment: Text.AlignHCenter; wrapMode: Text.WordWrap }
                    }
                }

                Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Qt.alpha(Color.foreground, 0.12) }
                RowLayout {
                    Layout.fillWidth: true
                    Ui.Button {
                        visible: !root.adding
                        text: (root.showSystem ? "▣ " : "□ ") + "Show system items"
                        fontSize: Style.font.caption
                        focusable: true
                        selected: root.showSystem
                        onClicked: root.showSystem = !root.showSystem
                    }
                    Item { Layout.fillWidth: true }
                    Label { text: (root.adding ? root.choices.length : root.applications.length) + " shown"; color: Qt.alpha(Color.popups.text, 0.70); font.pixelSize: Style.font.caption }
                }
                Label {
                    Layout.fillWidth: true
                    text: root.message || "Changes apply to future logins. Running programs stay open."
                    color: root.message ? Color.accent : Qt.alpha(Color.popups.text, 0.70)
                    font.pixelSize: Style.font.caption
                    wrapMode: Text.WordWrap
                }
            }
        }
    }
}
