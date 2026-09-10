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
    property var pendingRequest: ({})
    property bool filtersOpen: false
    property bool warningDetails: false
    property string savedQuery: ""
    property real savedScroll: 0
    property string savedSelection: ""
    property string undoId: ""
    property string undoRevision: ""
    property int messageRemaining: 0
    readonly property bool filtered: searchField.text.trim() !== "" || sourceFilter !== "all" || statusFilter !== "all" || showSystem
    readonly property var undoSource: Model.findSource(inventory.applications, undoId)
    readonly property bool canUndoMessage: !!undoSource && undoSource.canUndo === true && undoSource.revision === undoRevision
    readonly property bool mutating: busy && pendingRequest.action !== "scan"
    // Supplied only by the isolated QML harness. It disables every backend invocation.
    property var fixtureData: null
    readonly property var applications: Model.filtered(inventory.applications, searchField.text, sourceFilter, statusFilter, showSystem)
    readonly property var choices: Model.catalogFiltered(inventory.catalog, searchField.text)
    readonly property int displayedCount: adding ? choices.length : applications.length
    readonly property string backendPath: decodeURIComponent(Qt.resolvedUrl("backend/omastart.py").toString().replace(/^file:\/\//, ""))

    function open() {
        root.controller.show()
        refresh()
    }
    function setSearch(value) { searchField.text = value }
    function focusSearch() { searchField.forceActiveFocus(); searchField.selectAll() }
    function resetPosition() { listView.currentIndex = -1; listView.positionViewAtBeginning() }
    function resetFilters() {
        searchField.text = ""
        sourceFilter = "all"
        statusFilter = "all"
        showSystem = false
        resetPosition()
        searchField.forceActiveFocus()
    }
    function enterPicker() {
        savedQuery = searchField.text
        savedScroll = listView.contentY
        savedSelection = listView.currentItem ? listView.currentItem.entry.id : ""
        adding = true
        searchField.text = ""
        resetPosition()
        searchField.forceActiveFocus()
    }
    function leavePicker() {
        adding = false
        searchField.text = savedQuery
        Qt.callLater(function() { root.restorePosition(root.savedScroll, root.savedSelection); searchField.forceActiveFocus() })
    }
    function handleEscape() {
        if (searchField.text !== "") { searchField.text = ""; searchField.forceActiveFocus() }
        else if (adding) leavePicker()
        else if (expandedId !== "") { expandedId = ""; listView.forceActiveFocus() }
        else if (filtersOpen) { filtersOpen = false; searchField.forceActiveFocus() }
        else close()
    }
    function findControl(item, name, focused) {
        if (focused ? item.activeFocus && item.objectName : item.visible && item.objectName === name) return item
        var children = item.children || []
        for (var i = 0; i < children.length; i++) {
            var found = findControl(children[i], name, focused)
            if (found) return found
        }
        return null
    }
    function rememberListFocus() {
        var delegates = listView.contentItem.children
        for (var i = 0; i < delegates.length; i++) {
            if (!delegates[i].entry) continue
            var focused = findControl(delegates[i], "", true)
            if (focused) return {id: delegates[i].entry.id, control: focused.objectName}
        }
        return null
    }
    function restoreListFocus(saved) {
        if (!saved) return
        var rows = adding ? choices : applications
        var index = rows.findIndex(function(row) { return row.id === saved.id })
        if (index < 0) { searchField.forceActiveFocus(); return }
        listView.forceLayout()
        var row = listView.itemAtIndex(index)
        var control = row ? findControl(row, saved.control, false) : null
        if (control && control.visible && control.enabled) control.forceActiveFocus()
        else listView.forceActiveFocus()
    }
    function restorePosition(y, selected) {
        var rows = adding ? choices : applications
        listView.currentIndex = rows.findIndex(function(row) { return row.id === selected })
        listView.contentY = Math.max(listView.originY, Math.min(y, listView.originY + listView.contentHeight - listView.height))
    }
    function viewApplication(app) {
        var existing = inventory.applications.find(function(a) {
            return a.id === app.identity || a.sources.some(function(s) { return s.id === "xdg:" + app.id })
        })
        if (!existing) return
        adding = false
        resetFilters()
        searchField.text = existing.name
        expandedId = existing.id
    }
    function dismissMessage() { message = ""; undoId = ""; undoRevision = "" }
    function undoLast() {
        if (canUndoMessage) request({action: "undo", id: undoSource.id, revision: undoSource.revision, name: undoSource.name})
    }
    onSourceFilterChanged: resetPosition()
    onStatusFilterChanged: resetPosition()
    onShowSystemChanged: resetPosition()
    function inspect() {
        return {opened: opened, loaded: loaded, busy: busy, error: error, adding: adding, searchFocused: searchField.activeFocus,
                query: searchField.text, expandedId: expandedId, counts: inventory.counts,
                sourceFilter: sourceFilter, statusFilter: statusFilter, showSystem: showSystem, filtersOpen: filtersOpen,
                message: message, canUndoMessage: canUndoMessage, choices: adding ? choices.map(function(a) { return {id:a.id, name:a.name, exists:a.exists} }) : [],
                geometry: {x: popup.cardOrigin.x, y: popup.cardOrigin.y, width: popup.contentWidth, height: popup.contentHeight,
                           screen: "screen" in popup && popup.screen ? popup.screen.name : ""},
                rows: applications.map(function(a) { return {id: a.id, name: a.name, status: a.status,
                    sources: a.sources.map(function(s) { return {id: s.id, kind: s.kind, enabled: s.enabled, readOnly: s.readOnly, generatedUnits: s.generatedUnits || []} })} })}
    }
    function request(payload) {
        if (busy || fixtureData !== null) return
        if (payload.action !== "scan") { error = ""; dismissMessage() }
        pendingRequest = payload
        pendingId = payload.id || ""
        busy = true
        process.command = ["python3", "-B", root.backendPath, JSON.stringify(payload)]
        process.running = true
    }
    function refresh(manual) {
        if (manual) error = ""
        if (fixtureData !== null) { inventory = fixtureData; loaded = true; return }
        request({action: "scan", manual: manual === true})
    }
    function change(item) {
        if (busy || item.readOnly) return
        request({action: "toggle", id: item.id, revision: item.revision, enabled: !item.enabled, name: item.name})
    }
    function addApplication(app) {
        if (app.exists || busy) return
        request({action: "add", id: app.id, revision: app.revision, name: app.name})
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
            var savedFocus = rememberListFocus()
            var selected = listView.currentItem ? listView.currentItem.entry.id : ""
            inventory = result
            loaded = true
            if (pendingRequest.action && pendingRequest.action !== "scan") {
                var action = pendingRequest.action
                var changedId = action === "add" ? "xdg:" + pendingRequest.id : pendingRequest.id
                var changed = Model.findSource(result.applications, changedId)
                var name = pendingRequest.name || (changed ? changed.name : "Startup setting")
                message = action === "add" ? name + " added to startup."
                    : action === "undo" ? "Previous startup setting restored."
                    : action === "recover" ? "Interrupted change restored."
                    : name + (pendingRequest.enabled ? " will start at login." : " won't start at login through this source.")
                if (action === "toggle" && !pendingRequest.enabled) {
                    var app = result.applications.find(function(a) { return a.sources.some(function(s) { return s.id === changedId }) })
                    message = name + (app && app.enabled ? " still has another enabled startup source." : " won't start at login.")
                }
                undoId = action === "toggle" || action === "add" ? changedId : ""
                undoRevision = changed ? changed.revision : ""
                messageRemaining = 10000
            } else if (result.message) { message = result.message; messageRemaining = 10000 }
            Qt.callLater(function() {
                root.restorePosition(scrollY, savedFocus ? savedFocus.id : selected)
                root.restoreListFocus(savedFocus)
            })
            pendingRequest = ({})
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
        interval: 1000
        repeat: true
        running: root.message !== "" && root.opened
        onTriggered: {
            if (!feedbackHover.hovered && !feedback.activeFocus) root.messageRemaining -= 1000
            if (root.messageRemaining <= 0) root.dismissMessage()
        }
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
        contentHeight: cappedContentHeight(Style.space(760))

        FocusScope {
            anchors.fill: parent
            Keys.onEscapePressed: function(event) {
                root.handleEscape()
                event.accepted = true
            }

            Keys.onPressed: function(event) {
                if ((event.modifiers & Qt.ControlModifier) && event.key === Qt.Key_F) { root.focusSearch(); event.accepted = true }
            }

            ColumnLayout {
                anchors.fill: parent
                spacing: Style.space(12)

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
                        enabled: root.loaded
                        selected: !root.adding
                        onClicked: { if (root.adding) root.leavePicker(); else root.enterPicker() }
                    }
                    Ui.Button { text: "×"; fontSize: Style.space(24); focusable: true; tooltipText: "Close · Esc"; onClicked: root.close() }
                }

                RowLayout {
                    Layout.fillWidth: true
                    Label {
                        Layout.fillWidth: true
                        text: root.adding ? "Add as many apps as you need. They stay closed for now."
                            : root.loaded ? root.inventory.counts.enabled + " of " + root.inventory.counts.applications + (root.inventory.counts.applications === 1 ? " app enabled at login" : " apps enabled at login")
                            : "Finding your startup apps…"
                        font.pixelSize: Style.font.caption
                        color: Qt.alpha(Color.popups.text, 0.75)
                        wrapMode: Text.WordWrap
                    }
                    Ui.Button {
                        objectName: "refreshButton"
                        text: root.busy && !root.mutating && (root.pendingRequest.manual || !root.loaded) ? "Refreshing…" : "Refresh"
                        fontSize: Style.font.caption
                        focusable: true
                        enabled: !root.busy
                        opacity: root.mutating ? 0.6 : 1
                        tooltipText: "Check for startup changes made elsewhere"
                        onClicked: root.refresh(true)
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: Style.space(4)
                    Ui.TextField {
                        id: searchField
                        objectName: "searchField"
                        Layout.fillWidth: true
                        placeholderText: root.adding ? "Search installed applications…" : "Search startup apps…"
                        Accessible.name: root.adding ? "Search installed applications" : "Search startup apps"
                        onTextChanged: root.resetPosition()
                        onAccepted: {
                            if (listView.count > 0) {
                                listView.currentIndex = Math.max(0, listView.currentIndex)
                                listView.forceActiveFocus()
                                if (listView.currentItem) listView.currentItem.activate()
                            }
                        }
                        Keys.onEscapePressed: function(event) { root.handleEscape(); event.accepted = true }
                        Keys.onDownPressed: function(event) {
                            if (listView.count > 0) { listView.forceActiveFocus(); if (listView.currentIndex < 0) listView.currentIndex = 0 }
                            event.accepted = true
                        }
                    }
                    Ui.Button {
                        objectName: "clearSearchButton"
                        visible: searchField.text !== ""
                        text: "×"
                        tooltipText: "Clear search · Esc"
                        Accessible.name: "Clear search"
                        focusable: true
                        onClicked: { searchField.text = ""; searchField.forceActiveFocus() }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    visible: !root.adding
                    spacing: Style.space(4)
                    Repeater {
                        model: [{id:"all", title:"All apps"}, {id:"enabled", title:"Enabled"}, {id:"disabled", title:"Disabled"}]
                        Ui.Button {
                            required property var modelData
                            objectName: "status-" + modelData.id
                            text: modelData.title
                            selected: root.statusFilter === modelData.id
                            Accessible.role: Accessible.RadioButton
                            Accessible.name: modelData.title
                            Accessible.checked: selected
                            focusable: true
                            fontSize: Style.font.caption
                            horizontalPadding: Style.space(10)
                            onClicked: root.statusFilter = modelData.id
                        }
                    }
                    Item { Layout.fillWidth: true }
                    Ui.Button {
                        objectName: "filtersButton"
                        text: "Filters" + (root.sourceFilter !== "all" || root.showSystem ? " •" : "") + (root.filtersOpen ? " ⌃" : " ⌄")
                        fontSize: Style.font.caption
                        focusable: true
                        selected: root.filtersOpen || root.sourceFilter !== "all" || root.showSystem
                        tooltipText: "Filter by startup source or include system items"
                        onClicked: root.filtersOpen = !root.filtersOpen
                    }
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    visible: !root.adding && root.filtersOpen
                    spacing: Style.space(5)
                    RowLayout {
                        Layout.fillWidth: true
                        Label { text: "Source"; font.pixelSize: Style.font.caption; color: Qt.alpha(Color.popups.text, 0.7) }
                        Repeater {
                            model: [{id:"all", title:"All"}, {id:"hyprland", title:"Hyprland"}, {id:"xdg", title:"XDG"}, {id:"systemd", title:"systemd"}]
                            Ui.Button {
                                required property var modelData
                                text: modelData.title
                                selected: root.sourceFilter === modelData.id
                                focusable: true
                                fontSize: Style.font.caption
                                onClicked: root.sourceFilter = modelData.id
                            }
                        }
                        Item { Layout.fillWidth: true }
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        Ui.Button {
                            text: (root.showSystem ? "▣ " : "□ ") + "Include system items"
                            fontSize: Style.font.caption
                            focusable: true
                            selected: root.showSystem
                            Accessible.role: Accessible.CheckBox
                            Accessible.checked: root.showSystem
                            onClicked: root.showSystem = !root.showSystem
                        }
                        Item { Layout.fillWidth: true }
                        Ui.Button { text: "Reset filters"; fontSize: Style.font.caption; focusable: true; onClicked: root.resetFilters() }
                    }
                }
                RowLayout {
                    Layout.fillWidth: true
                    visible: !root.adding && !root.filtersOpen && (root.sourceFilter !== "all" || root.showSystem)
                    Label {
                        Layout.fillWidth: true
                        text: (root.sourceFilter !== "all" ? Model.sourceLabel(root.sourceFilter) : "All sources") + (root.showSystem ? " · Including system items" : "")
                        font.pixelSize: Style.font.caption
                        color: Color.accent
                    }
                    Ui.Button { text: "Reset"; fontSize: Style.font.caption; focusable: true; onClicked: root.resetFilters() }
                }

                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: noticeContents.implicitHeight + Style.space(18)
                    visible: root.error !== "" || root.inventory.warnings.length > 0
                    radius: Style.cornerRadius
                    color: Qt.alpha(Color.urgent, 0.09)
                    ColumnLayout {
                        id: noticeContents
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        anchors.margins: Style.space(9)
                        spacing: Style.space(5)
                        RowLayout {
                            Layout.fillWidth: true
                            Label {
                                Layout.fillWidth: true
                                text: root.error ? "Couldn't complete the request" : "Some startup items need attention"
                                color: Color.urgent
                                font.bold: true
                                font.pixelSize: Style.font.caption
                            }
                            Ui.Button {
                                text: root.error ? "Refresh" : root.warningDetails ? "Less" : "Details"
                                focusable: true
                                fontSize: Style.font.caption
                                enabled: !root.busy
                                onClicked: { if (root.error) root.refresh(true); else root.warningDetails = !root.warningDetails }
                            }
                        }
                        Label {
                            Layout.fillWidth: true
                            visible: root.error !== "" || root.warningDetails
                            text: root.error || root.inventory.warnings.join("\n")
                            wrapMode: Text.Wrap
                            maximumLineCount: 5
                            font.pixelSize: Style.font.caption
                            color: Qt.alpha(Color.popups.text, 0.85)
                        }
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
                    Keys.onEscapePressed: root.handleEscape()
                    Keys.onLeftPressed: root.expandedId = ""
                    Keys.onRightPressed: if (currentIndex >= 0 && !root.adding) root.expandedId = root.applications[currentIndex].id
                    Keys.onUpPressed: function(event) {
                        if (currentIndex <= 0) { searchField.forceActiveFocus(); event.accepted = true }
                        else event.accepted = false
                    }

                    delegate: ApplicationRow {
                        required property var modelData
                        required property int index
                        width: listView.width - Style.space(8)
                        entry: modelData
                        manager: root
                        picker: root.adding
                        hasCursor: listView.activeFocus && listView.currentIndex === index
                        onSelected: listView.currentIndex = index
                        onRevealRequested: Qt.callLater(function() { listView.positionViewAtIndex(index, ListView.Contain) })
                    }

                    Column {
                        anchors.centerIn: parent
                        width: parent.width * 0.85
                        spacing: Style.space(9)
                        visible: listView.count === 0
                        Label {
                            width: parent.width
                            text: !root.loaded ? (root.busy ? "Finding your startup apps…" : "Startup information unavailable")
                                : searchField.text.trim() ? "No apps found"
                                : root.adding ? "No installed apps available"
                                : root.statusFilter === "disabled" ? "No disabled apps"
                                : root.statusFilter === "enabled" ? "No enabled apps" : "No startup apps yet"
                            horizontalAlignment: Text.AlignHCenter
                            font.bold: true
                            font.pixelSize: Style.font.subtitle
                        }
                        Label {
                            width: parent.width
                            text: !root.loaded ? (root.busy ? "Checking your session’s startup settings." : "Refresh to try reading your startup settings again.")
                                : searchField.text.trim() ? "Try another name or clear your search."
                                : root.filtered && !root.adding ? "Change the filters to see more apps."
                                : root.adding ? "Apps with desktop entries will appear here." : "Add an installed app to open it when you sign in."
                            color: Qt.alpha(Color.popups.text, 0.70)
                            horizontalAlignment: Text.AlignHCenter
                            wrapMode: Text.WordWrap
                        }
                        Ui.Button {
                            anchors.horizontalCenter: parent.horizontalCenter
                            visible: !root.loaded || searchField.text !== "" || (!root.adding && (root.filtered || root.inventory.counts.applications === 0))
                            text: !root.loaded ? "Refresh" : searchField.text !== "" ? "Clear search" : root.filtered ? "Reset filters" : "+ Add app"
                            focusable: true
                            bordered: true
                            enabled: !root.busy
                            onClicked: {
                                if (!root.loaded) root.refresh(true)
                                else if (searchField.text !== "") { searchField.text = ""; searchField.forceActiveFocus() }
                                else if (root.filtered) root.resetFilters()
                                else root.enterPicker()
                            }
                        }
                    }
                }

                Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Qt.alpha(Color.foreground, 0.12) }
                RowLayout {
                    Layout.fillWidth: true
                    Label {
                        Layout.fillWidth: true
                        text: root.displayedCount + (root.adding ? (root.displayedCount === 1 ? " installed app" : " installed apps") : (root.displayedCount === 1 ? " app shown" : " apps shown"))
                        color: Qt.alpha(Color.popups.text, 0.70)
                        font.pixelSize: Style.font.caption
                    }
                    Label {
                        text: root.adding ? "Enter to choose · Esc to go back" : "Click an app for details"
                        color: Qt.alpha(Color.popups.text, 0.60)
                        font.pixelSize: Style.font.caption
                    }
                }
                FocusScope {
                    id: feedback
                    Layout.fillWidth: true
                    implicitHeight: Style.space(52)
                    HoverHandler { id: feedbackHover }
                    Rectangle {
                        anchors.fill: parent
                        radius: Style.cornerRadius
                        color: root.message ? Qt.alpha(Color.accent, 0.08) : "transparent"
                        Behavior on color { ColorAnimation { duration: 140 } }
                    }
                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: root.message ? Style.space(8) : 0
                        spacing: Style.space(5)
                        Label {
                            Layout.fillWidth: true
                            text: root.message || "Changes apply at your next login. Running apps stay open."
                            color: root.message ? Color.accent : Qt.alpha(Color.popups.text, 0.70)
                            font.pixelSize: Style.font.caption
                            wrapMode: Text.WordWrap
                            maximumLineCount: 3
                            Accessible.role: Accessible.StaticText
                            Accessible.name: text
                        }
                        Ui.Button {
                            objectName: "messageUndoButton"
                            visible: root.message !== "" && root.canUndoMessage
                            text: "Undo"
                            focusable: true
                            bordered: true
                            enabled: !root.busy
                            onClicked: root.undoLast()
                        }
                        Ui.Button {
                            visible: root.message !== ""
                            text: "×"
                            tooltipText: "Dismiss message"
                            Accessible.name: "Dismiss message"
                            focusable: true
                            onClicked: root.dismissMessage()
                        }
                    }
                }
            }
        }
    }
}
