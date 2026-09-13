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
    property var applicationOrder: []
    property bool openingScanPending: true
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
    property bool requestTimedOut: false
    property bool responseExceeded: false
    property string processOutput: ""
    property string processErrors: ""
    property bool filtersOpen: false
    property bool warningDetails: false
    property string savedQuery: ""
    property real savedScroll: 0
    property string savedSelection: ""
    property string pickerAddedId: ""
    property string undoId: ""
    property string undoRevision: ""
    property bool undoApplication: false
    property bool undoRemoval: false
    property int messageRemaining: 0
    readonly property bool readOnlyView: !adding && statusFilter === "readonly"
    readonly property bool systemFilterActive: showSystem && !readOnlyView
    readonly property bool filtered: searchField.text.trim() !== "" || sourceFilter !== "all" || statusFilter !== "all" || systemFilterActive
    readonly property var undoSource: undoRemoval ? Model.findRemoval(inventory, undoId) : undoApplication ? Model.findApplication(inventory.applications, undoId) : Model.findSource(inventory.applications, undoId)
    readonly property bool canUndoMessage: !!undoSource && undoSource.canUndo === true && undoSource.revision === undoRevision
    readonly property bool mutating: busy && pendingRequest.action !== "scan"
    // Supplied only by the isolated QML harness. It disables every backend invocation.
    property var fixtureData: null
    readonly property var applications: Model.filtered(Model.ordered(inventory.applications, applicationOrder), searchField.text, sourceFilter, statusFilter, showSystem)
    readonly property var choices: Model.catalogFiltered(inventory.catalog, searchField.text)
    readonly property int displayedCount: adding ? choices.length : applications.length
    readonly property string backendPath: decodeURIComponent(Qt.resolvedUrl("backend/omastart.py").toString().replace(/^file:\/\//, ""))
    readonly property string bridgePath: decodeURIComponent(Qt.resolvedUrl("backend/bridge.py").toString().replace(/^file:\/\//, ""))

    function open() {
        root.controller.show()
        refresh()
    }
    onOpenedChanged: {
        if (opened) {
            applicationOrder = Model.openingOrder(inventory.applications)
            openingScanPending = true
            resetPosition()
        }
    }
    function acceptInventory(next, fromScan, firstId) {
        applicationOrder = !loaded || openingScanPending && fromScan
            ? Model.openingOrder(next.applications)
            : Model.ordered(next.applications, applicationOrder).map(function(app) { return app.id })
        if (firstId) applicationOrder = [firstId].concat(applicationOrder.filter(function(id) { return id !== firstId }))
        openingScanPending = false
        inventory = next
        loaded = true
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
        pickerAddedId = ""
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
        if (pickerAddedId) {
            resetFilters()
            savedScroll = 0
            savedSelection = pickerAddedId
            pickerAddedId = ""
        } else searchField.text = savedQuery
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
        if (Model.locked(existing)) statusFilter = "readonly"
        else if (existing.system) showSystem = true
        searchField.text = existing.name
        expandedId = existing.id
    }
    function dismissMessage() { message = ""; undoId = ""; undoRevision = ""; undoApplication = false; undoRemoval = false }
    function undoLast() {
        if (canUndoMessage) request({action: undoRemoval ? "undoRemoval" : undoApplication ? "undoApplication" : "undo", id: undoSource.id, revision: undoSource.revision, name: undoSource.name})
    }
    onSourceFilterChanged: resetPosition()
    onStatusFilterChanged: {
        if (statusFilter !== "all" && statusFilter !== "readonly") statusFilter = "all"
        resetPosition()
    }
    onShowSystemChanged: resetPosition()
    function inspect() {
        return {opened: opened, loaded: loaded, busy: busy, error: error, adding: adding, searchFocused: searchField.activeFocus,
                query: searchField.text, expandedId: expandedId, counts: inventory.counts,
                sourceFilter: sourceFilter, statusFilter: statusFilter, showSystem: showSystem, filtersOpen: filtersOpen,
                message: message, canUndoMessage: canUndoMessage, choices: adding ? choices.map(function(a) { return {id:a.id, name:a.name, exists:a.exists} }) : [],
                geometry: {x: popup.cardOrigin.x, y: popup.cardOrigin.y, width: popup.contentWidth, height: popup.contentHeight,
                           screen: "screen" in popup && popup.screen ? popup.screen.name : ""},
                rows: applications.map(function(a) { return {id: a.id, name: a.name, status: a.status,
                    startupEnabled: a.startupEnabled, preferredSource: a.preferredSource, toggleReadOnly: a.toggleReadOnly,
                    sources: a.sources.map(function(s) { return {id: s.id, kind: s.kind, enabled: s.enabled, readOnly: s.readOnly, generatedUnits: s.generatedUnits || []} })} })}
    }
    function request(payload) {
        if (busy || fixtureData !== null) return
        if (payload.action !== "scan") { error = ""; dismissMessage(); openingScanPending = false }
        pendingRequest = payload
        requestTimedOut = false
        responseExceeded = false
        processOutput = ""
        processErrors = ""
        pendingId = payload.id || ""
        busy = true
        process.command = ["/usr/bin/python3", "-I", "-B", root.bridgePath, root.backendPath, JSON.stringify(payload)]
        process.running = true
        requestTimer.restart()
    }
    function refresh(manual) {
        if (manual) error = ""
        if (fixtureData !== null) { acceptInventory(fixtureData, true); return }
        request({action: "scan", manual: manual === true})
    }
    function change(item) {
        if (busy || item.readOnly) return
        request({action: "toggle", id: item.id, revision: item.revision, enabled: !item.enabled, name: item.name})
    }
    function changeApplication(app) {
        if (busy || app.toggleReadOnly) return
        request({action: "toggleApplication", id: app.id, revision: app.revision, enabled: !app.startupEnabled, name: app.name})
    }
    function addApplication(app) {
        if (app.exists || busy) return
        request({action: "add", id: app.id, revision: app.revision, name: app.name})
    }
    function removeApplication(app) {
        if (busy || !app.canRemove) return
        request({action: "remove", id: app.id, revision: app.revision, name: app.name})
    }
    function captureProcessOutput(data, isError) {
        var current = isError ? processErrors : processOutput
        var limit = isError ? 64000 : 2000000
        if (current.length + data.length > limit) {
            responseExceeded = true
            if (process.running) process.signal(9)
            return
        }
        if (isError) processErrors += data
        else processOutput += data
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
            var added = pendingRequest.action === "add" ? result.applications.find(function(app) {
                return app.id === result.addedApplicationId || app.sources.some(function(source) { return source.id === "xdg:" + root.pendingRequest.id })
            }) : null
            acceptInventory(result, pendingRequest.action === "scan", added ? added.id : "")
            if (added && adding) pickerAddedId = added.id
            if (pendingRequest.action && pendingRequest.action !== "scan") {
                var action = pendingRequest.action
                var addedAsApplication = action === "add" && result.addedApplicationUndo === "application"
                var changedId = addedAsApplication ? result.addedApplicationId : action === "add" ? "xdg:" + pendingRequest.id : pendingRequest.id
                var applicationChange = action === "toggleApplication" || action === "undoApplication" || addedAsApplication
                var changed = action === "remove" ? Model.findRemoval(result, changedId) : applicationChange ? Model.findApplication(result.applications, changedId) : Model.findSource(result.applications, changedId)
                var name = pendingRequest.name || (changed ? changed.name : "Startup setting")
                message = action === "add" ? name + " added to startup."
                    : action === "undo" || action === "undoApplication" ? "Previous startup setting restored."
                    : action === "remove" ? name + " removed from the list. Startup methods stay disabled."
                    : action === "undoRemoval" ? name + " restored to the list."
                    : action === "recover" ? "Interrupted change restored."
                    : action === "toggleApplication" ? name + (pendingRequest.enabled ? " will start at login via "
                        + (changed && Model.preferredSource(changed) ? Model.sourceLabel(Model.preferredSource(changed).kind) : "the selected method") + "." : " won't start at login.")
                    : name + (pendingRequest.enabled ? " will start at login." : " won't start at login through this source.")
                if (action === "toggle" && !pendingRequest.enabled) {
                    var app = result.applications.find(function(a) { return a.sources.some(function(s) { return s.id === changedId }) })
                    message = name + (app && app.enabled ? " still has another enabled startup source." : " won't start at login.")
                }
                undoRemoval = action === "remove"
                undoApplication = action === "toggleApplication" || addedAsApplication || !!result.applicationUndoId
                if (result.applicationUndoId) {
                    changedId = result.applicationUndoId
                    changed = Model.findApplication(result.applications, changedId)
                }
                undoId = action === "toggle" || action === "add" || undoApplication || undoRemoval ? changedId : ""
                undoRevision = changed ? changed.revision : ""
                messageRemaining = 10000
                if (action === "remove" && expandedId === pendingRequest.id) expandedId = ""
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
        clearEnvironment: true
        environment: Object.assign({}, {
            "HOME": Quickshell.env("HOME"),
            "USER": Quickshell.env("USER"),
            "LOGNAME": Quickshell.env("LOGNAME"),
            "XDG_CONFIG_HOME": Quickshell.env("XDG_CONFIG_HOME"),
            "XDG_STATE_HOME": Quickshell.env("XDG_STATE_HOME"),
            "XDG_DATA_HOME": Quickshell.env("XDG_DATA_HOME"),
            "XDG_CONFIG_DIRS": Quickshell.env("XDG_CONFIG_DIRS"),
            "XDG_DATA_DIRS": Quickshell.env("XDG_DATA_DIRS"),
            "XDG_RUNTIME_DIR": Quickshell.env("XDG_RUNTIME_DIR"),
            "XDG_CURRENT_DESKTOP": Quickshell.env("XDG_CURRENT_DESKTOP"),
            "DBUS_SESSION_BUS_ADDRESS": Quickshell.env("DBUS_SESSION_BUS_ADDRESS"),
            "LANG": Quickshell.env("LANG"),
            "LC_MESSAGES": Quickshell.env("LC_MESSAGES"),
            "LC_ALL": "C",
            "PYTHONDONTWRITEBYTECODE": "1",
            "SYSTEMD_COLORS": "0"
        })
        stdout: SplitParser { onRead: function(data) { root.captureProcessOutput(data, false) } }
        stderr: SplitParser { onRead: function(data) { root.captureProcessOutput(data, true) } }
        onExited: function(exitCode) {
            requestTimer.stop()
            if (root.requestTimedOut) {
                root.busy = false
                root.pendingId = ""
                root.pendingRequest = ({})
                return
            }
            if (root.responseExceeded) {
                root.busy = false
                root.pendingId = ""
                root.pendingRequest = ({})
                root.error = "The backend response exceeded its safety limit. Refresh and try again."
                return
            }
            var out = root.processOutput
            var err = root.processErrors
            Qt.callLater(function() { root.finish(out, err, exitCode) })
        }
    }
    Timer {
        id: requestTimer
        interval: 22000
        onTriggered: {
            root.requestTimedOut = true
            if (process.running) process.signal(9)
            root.error = "The backend request exceeded its time limit. Refresh and try again."
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
        contentWidth: fittedContentWidth(Style.space(440))
        contentHeight: cappedContentHeight(Style.space(650))

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
                spacing: Style.space(14)

                RowLayout {
                    Layout.fillWidth: true
                    spacing: Style.space(8)
                    LaunchIcon { implicitWidth: Style.space(24); implicitHeight: Style.space(24); foreground: Color.popups.text }
                    Label { text: "omastart"; font.pixelSize: Style.space(21); Layout.fillWidth: true }
                    Label { text: "SESSION STARTUP"; font.pixelSize: Style.space(9); font.letterSpacing: 1; color: Qt.alpha(Color.popups.text, 0.65) }
                }

                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: overview.implicitHeight + Style.space(26)
                    radius: Style.space(8)
                    color: Qt.alpha(Color.accent, 0.07)
                    border.color: Qt.alpha(Color.accent, 0.16)
                    ColumnLayout {
                        id: overview
                        anchors { left: parent.left; right: parent.right; top: parent.top; margins: Style.space(13) }
                        spacing: Style.space(6)
                        Label {
                            Layout.fillWidth: true
                            text: root.adding ? "Add application" : root.loaded ? root.inventory.counts.enabled + " apps enabled at login" : "Finding startup apps…"
                            color: Color.accent
                            font.pixelSize: Style.space(16)
                        }
                        Label {
                            Layout.fillWidth: true
                            text: root.adding ? "Choose an installed app to start when you sign in." : "Manage everything that starts with your session."
                            color: Qt.alpha(Color.popups.text, 0.70)
                            font.pixelSize: Style.space(11)
                            wrapMode: Text.WordWrap
                        }
                    }
                }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: Style.space(8)
                    ActionButton {
                        text: root.adding ? "Back to startup" : "+ Add app"
                        focusable: true
                        enabled: root.loaded
                        selected: !root.adding
                        onClicked: { if (root.adding) root.leavePicker(); else root.enterPicker() }
                    }
                    ActionButton {
                        objectName: "refreshButton"
                        text: root.busy && !root.mutating && (root.pendingRequest.manual || !root.loaded) ? "Refreshing…" : "Refresh"
                        focusable: true
                        enabled: !root.busy
                        tooltipText: "Check for startup changes made elsewhere"
                        onClicked: root.refresh(true)
                    }
                    Item { Layout.fillWidth: true }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: Style.space(4)
                    Ui.TextField {
                        id: searchField
                        font.pixelSize: Style.space(12)
                        implicitHeight: Style.space(38)
                        leftPadding: Style.space(12)
                        background: Rectangle {
                            radius: Style.space(6)
                            color: Qt.alpha(Color.popups.text, 0.035)
                            border.color: searchField.activeFocus ? Color.accent : Qt.alpha(Color.popups.text, 0.15)
                        }
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
                    ActionButton {
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
                        model: [{id:"all", title:"Applications"}, {id:"readonly", title:"Read-only"}]
                        ActionButton {
                            required property var modelData
                            objectName: "status-" + modelData.id
                            text: modelData.title
                            selected: root.statusFilter === modelData.id
                            Accessible.role: Accessible.RadioButton
                            Accessible.name: modelData.title
                            Accessible.checked: selected
                            focusable: true
                            fontSize: Style.space(11)
                            horizontalPadding: Style.space(10)
                            onClicked: root.statusFilter = modelData.id
                        }
                    }
                    Item { Layout.fillWidth: true }
                    ActionButton {
                        objectName: "filtersButton"
                        text: "Filters" + (root.sourceFilter !== "all" || root.systemFilterActive ? " •" : "") + (root.filtersOpen ? " ⌃" : " ⌄")
                        fontSize: Style.space(11)
                        focusable: true
                        selected: root.filtersOpen || root.sourceFilter !== "all" || root.systemFilterActive
                        tooltipText: root.readOnlyView ? "Filter by startup source" : "Filter by startup source or include system items"
                        onClicked: root.filtersOpen = !root.filtersOpen
                    }
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    visible: !root.adding && root.filtersOpen
                    spacing: Style.space(5)
                    RowLayout {
                        Layout.fillWidth: true
                        Label { text: "Source"; font.pixelSize: Style.space(11); color: Qt.alpha(Color.popups.text, 0.7) }
                        Repeater {
                            model: [{id:"all", title:"All"}, {id:"hyprland", title:"Hyprland"}, {id:"xdg", title:"XDG"}, {id:"systemd", title:"systemd"}]
                            ActionButton {
                                required property var modelData
                                text: modelData.title
                                selected: root.sourceFilter === modelData.id
                                focusable: true
                                fontSize: Style.space(11)
                                onClicked: root.sourceFilter = modelData.id
                            }
                        }
                        Item { Layout.fillWidth: true }
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        ActionButton {
                            visible: !root.readOnlyView
                            text: (root.showSystem ? "▣ " : "□ ") + "Include system items"
                            fontSize: Style.space(11)
                            focusable: true
                            selected: root.showSystem
                            Accessible.role: Accessible.CheckBox
                            Accessible.checked: root.showSystem
                            onClicked: root.showSystem = !root.showSystem
                        }
                        Item { Layout.fillWidth: true }
                        ActionButton { text: "Reset filters"; link: true; fontSize: Style.space(11); focusable: true; onClicked: root.resetFilters() }
                    }
                }
                RowLayout {
                    Layout.fillWidth: true
                    visible: !root.adding && !root.filtersOpen && (root.sourceFilter !== "all" || root.systemFilterActive)
                    Label {
                        Layout.fillWidth: true
                        text: (root.sourceFilter !== "all" ? Model.sourceLabel(root.sourceFilter) : "All sources") + (root.systemFilterActive ? " · Including system items" : "")
                        font.pixelSize: Style.space(11)
                        color: Color.accent
                    }
                    ActionButton { text: "Reset"; link: true; fontSize: Style.space(11); focusable: true; onClicked: root.resetFilters() }
                }

                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: noticeContents.implicitHeight + Style.space(26)
                    visible: root.error !== "" || root.inventory.warnings.length > 0
                    radius: Style.space(8)
                    color: Qt.alpha(Color.urgent, 0.07)
                    border.color: Qt.alpha(Color.urgent, 0.16)
                    ColumnLayout {
                        id: noticeContents
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        anchors.margins: Style.space(13)
                        spacing: Style.space(6)
                        RowLayout {
                            Layout.fillWidth: true
                            Label {
                                Layout.fillWidth: true
                                text: root.error ? "Couldn't save changes" : "Needs attention"
                                color: Color.urgent
                                font.bold: false
                                font.pixelSize: Style.space(16)
                            }
                            ActionButton {
                                text: root.error ? "Refresh" : root.warningDetails ? "Less" : "Details"
                                link: true
                                focusable: true
                                fontSize: Style.space(11)
                                enabled: !root.busy
                                onClicked: { if (root.error) root.refresh(true); else root.warningDetails = !root.warningDetails }
                            }
                        }
                        Label {
                            Layout.fillWidth: true
                            visible: root.error !== "" || root.warningDetails
                            text: root.error || root.inventory.warnings.map(function(warning) { return "• " + warning }).join("\n\n")
                            wrapMode: Text.Wrap
                            elide: Text.ElideNone
                            font.pixelSize: Style.space(11)
                            color: Qt.alpha(Color.popups.text, 0.85)
                        }
                    }
                }

                Repeater {
                    model: root.inventory.recoveries || []
                    ActionButton {
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

                Label {
                    Layout.fillWidth: true
                    text: root.adding ? "INSTALLED APPLICATIONS" : root.readOnlyView ? "READ-ONLY ITEMS" : "STARTUP APPLICATIONS"
                    font.pixelSize: Style.space(10)
                    font.letterSpacing: 1
                    color: Qt.alpha(Color.popups.text, 0.65)
                }

                ListView {
                    id: listView
                    objectName: "applicationList"
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    spacing: Style.space(4)
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
                                : root.readOnlyView ? "No read-only items"
                                : "No startup apps yet"
                            horizontalAlignment: Text.AlignHCenter
                            font.bold: false
                            font.pixelSize: Style.space(16)
                        }
                        Label {
                            width: parent.width
                            text: !root.loaded ? (root.busy ? "Checking your session’s startup settings." : "Refresh to try reading your startup settings again.")
                                : searchField.text.trim() ? "Try another name or clear your search."
                                : root.readOnlyView && root.sourceFilter === "all" ? "Read-only startup items, including protected system items, appear here."
                                : root.filtered && !root.adding ? "Change the filters to see more apps."
                                : root.adding ? "Apps with desktop entries will appear here." : "Add an installed app to open it when you sign in."
                            color: Qt.alpha(Color.popups.text, 0.70)
                            horizontalAlignment: Text.AlignHCenter
                            wrapMode: Text.WordWrap
                        }
                        ActionButton {
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
                        font.pixelSize: Style.space(11)
                    }
                    Label {
                        text: root.adding ? "Enter to choose · Esc to go back" : "Click an app for details"
                        color: Qt.alpha(Color.popups.text, 0.60)
                        font.pixelSize: Style.space(11)
                    }
                }
                FocusScope {
                    id: feedback
                    objectName: "feedback"
                    Layout.fillWidth: true
                    // Reserve the same three-line message/action area at rest,
                    // while saving, and after Undo appears or disappears.
                    implicitHeight: Math.max(messageUndo.implicitHeight, feedbackMetrics.lineSpacing * 3) + Style.space(18)
                    Layout.minimumHeight: implicitHeight
                    Layout.maximumHeight: implicitHeight
                    FontMetrics {
                        id: feedbackMetrics
                        font.family: Style.font.family
                        font.pixelSize: Style.space(11)
                    }
                    HoverHandler { id: feedbackHover }
                    Rectangle {
                        anchors.fill: parent
                        radius: Style.space(8)
                        color: root.message ? Qt.alpha(Color.accent, 0.08) : "transparent"
                        Behavior on color { ColorAnimation { duration: 140 } }
                    }
                    RowLayout {
                        id: feedbackRow
                        anchors.fill: parent
                        anchors.margins: Style.space(9)
                        spacing: Style.space(5)
                        Label {
                            Layout.fillWidth: true
                            text: root.message || "Changes apply at next login. Running apps stay open."
                            color: root.message ? Color.accent : Qt.alpha(Color.popups.text, 0.70)
                            font.pixelSize: Style.space(11)
                            wrapMode: Text.WordWrap
                            maximumLineCount: 3
                            Accessible.role: Accessible.StaticText
                            Accessible.name: text
                        }
                        Item {
                            implicitWidth: messageUndo.implicitWidth
                            implicitHeight: messageUndo.implicitHeight
                            ActionButton {
                                id: messageUndo
                                objectName: "messageUndoButton"
                                anchors.centerIn: parent
                                visible: root.message !== "" && root.canUndoMessage
                                text: "Undo"
                                focusable: true
                                bordered: true
                                enabled: !root.busy
                                onClicked: root.undoLast()
                            }
                        }

                    }
                }
            }
        }
    }
}
