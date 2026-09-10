pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import qs.Commons
import qs.Ui as Ui
import "Model.js" as Model

Rectangle {
    id: root
    required property var entry
    required property var manager
    property bool picker: false
    property bool hasCursor: false
    readonly property bool expanded: !picker && manager.expandedId === entry.id
    property bool technical: false
    readonly property bool pending: manager.busy && (manager.pendingId === entry.id || !picker && entry.sources.some(function(s) { return s.id === manager.pendingId }))
    readonly property bool locked: !picker && Model.locked(entry)
    signal selected()
    signal revealRequested()
    onExpandedChanged: { if (!expanded) technical = false; else revealRequested() }
    onTechnicalChanged: if (technical) revealRequested()
    Behavior on color { ColorAnimation { duration: 120 } }
    implicitHeight: contents.implicitHeight + Style.space(16)
    radius: Style.space(6)
    color: expanded ? Qt.alpha(Color.accent, 0.045) : (hover.containsMouse || hasCursor ? Qt.alpha(Color.foreground, 0.05) : "transparent")
    border.width: expanded || hasCursor ? 1 : 0
    border.color: Qt.alpha(Color.accent, hasCursor ? 0.7 : 0.20)

    FontMetrics {
        id: statusMetrics
        font.family: Style.font.family
        font.pixelSize: Style.space(11)
    }

    Rectangle {
        anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
        height: 1
        color: Qt.alpha(Color.foreground, 0.08)
        visible: !root.expanded
    }

    function activate() {
        if (picker) { if (entry.exists) manager.viewApplication(entry); else if (!manager.busy) manager.addApplication(entry) }
        else manager.expandedId = expanded ? "" : entry.id
    }
    MouseArea {
        id: hover
        anchors.top: parent.top
        width: parent.width
        height: summary.implicitHeight + Style.space(18)
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: { root.selected(); root.activate() }
    }

    ColumnLayout {
        id: contents
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: Style.space(9)
        spacing: Style.space(10)

        RowLayout {
            id: summary
            Layout.fillWidth: true
            spacing: Style.space(8)
            AppIcon { iconName: root.entry.icon; appName: root.entry.name }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: Style.space(4)
                Label { objectName: "applicationTitle"; Layout.fillWidth: true; text: root.entry.name; font.bold: false; font.pixelSize: Style.space(13) }
                Label {
                    Layout.fillWidth: true
                    text: root.picker ? (root.entry.exists ? "Already in your startup list" : "Start this app when you sign in") : Model.subtitle(root.entry)
                    color: Qt.alpha(Color.popups.text, 0.70)
                    font.pixelSize: Style.space(11)
                }
            }
            ActionButton {
                objectName: "pickerAction"
                visible: root.picker
                text: root.pending ? "Adding…" : root.entry.exists ? "Manage" : "+ Add"
                opacity: enabled || root.entry.exists ? 1 : 0.5
                Accessible.name: root.entry.exists ? "Manage startup for " + root.entry.name : "Add " + root.entry.name + " to startup"
                focusable: true
                enabled: root.picker && (root.entry.exists || !root.manager.busy)
                onClicked: root.activate()
            }
            ColumnLayout {
                id: statusColumn
                visible: !root.picker
                Layout.preferredWidth: Math.ceil(Math.max(statusMetrics.advanceWidth("Disabled"), statusMetrics.advanceWidth("Saving…"),
                    statusMetrics.advanceWidth(root.entry.status || ""), root.locked ? statusMetrics.advanceWidth("Read-only") : 0))
                Layout.minimumWidth: statusColumn.Layout.preferredWidth
                Layout.maximumWidth: statusColumn.Layout.preferredWidth
                spacing: 0
                Label {
                    Layout.alignment: Qt.AlignRight
                    text: root.pending ? "Saving…" : root.entry.status || ""
                    color: root.entry.enabled ? Color.accent : Qt.alpha(Color.popups.text, 0.70)
                    font.pixelSize: Style.space(11)
                }
                Label {
                    Layout.alignment: Qt.AlignRight
                    visible: root.locked
                    text: "Read-only"
                    font.pixelSize: Style.space(10)
                    color: Qt.alpha(Color.popups.text, 0.70)
                }
            }
            Item {
                visible: !root.picker && !root.locked && root.entry.sources && root.entry.sources.length > 0
                implicitWidth: Style.space(54)
                implicitHeight: Style.space(34)
                SourceToggle {
                    id: singleToggle
                    objectName: "startupToggle"
                    anchors.centerIn: parent
                    visible: !root.picker && root.entry.sources && root.entry.sources.length > 0 && !root.locked
                    sourceItem: root.entry.sources ? root.entry.sources[0] : ({})
                    applicationItem: root.entry.sources && root.entry.sources.length > 1 ? root.entry : null
                    manager: root.manager
                    appName: root.entry.name
                }
            }
            ActionButton {
                objectName: "sourceDetails"
                visible: !root.picker
                text: root.expanded ? "⌃" : "⌄"
                iconOnly: true
                fontSize: Style.space(11)
                horizontalPadding: Style.space(8)
                tooltipText: root.locked ? "Why this startup item is read-only" : "Startup details for " + root.entry.name
                Accessible.name: (root.expanded ? "Hide details for " : "Show details for ") + root.entry.name
                focusable: true
                onClicked: root.activate()
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            visible: root.expanded
            spacing: Style.space(10)

            Label {
                Layout.fillWidth: true
                visible: root.entry.duplicate === true
                text: "This app may launch more than once. Turn off the extra startup source below."
                color: Color.urgent
                font.pixelSize: Style.space(11)
                wrapMode: Text.WordWrap
            }
            Label {
                Layout.fillWidth: true
                visible: !!root.entry.sources && root.entry.sources.length > 1 && !root.entry.duplicate
                text: root.entry.toggleReadOnly || "The app toggle turns off all enabled methods. Turning it on uses "
                    + (Model.preferredSource(root.entry) ? Model.sourceLabel(Model.preferredSource(root.entry).kind) : "an available method") + "."
                font.pixelSize: Style.space(11)
                color: Qt.alpha(Color.popups.text, 0.7)
                wrapMode: Text.WordWrap
            }
            ActionButton {
                objectName: "undoApplication"
                visible: root.entry.canUndo === true
                text: "Undo app startup change"
                link: true
                enabled: !root.manager.busy
                onClicked: root.manager.request({action:"undoApplication", id:root.entry.id, revision:root.entry.revision, name:root.entry.name})
            }
            Repeater {
                model: root.expanded ? root.entry.sources : []
                ColumnLayout {
                    id: detail
                    required property var modelData
                    Layout.fillWidth: true
                    spacing: Style.space(5)
                    Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Qt.alpha(Color.foreground, 0.10) }
                    RowLayout {
                        Layout.fillWidth: true
                        Label { text: Model.sourceLabel(detail.modelData.kind); font.bold: false; font.pixelSize: Style.space(11) }
                        Item { Layout.fillWidth: true }
                        Label { text: root.manager.busy && root.manager.pendingId === detail.modelData.id ? "Saving…" : Model.sourceState(detail.modelData); color: detail.modelData.enabled ? Color.accent : Qt.alpha(Color.popups.text, 0.70); font.pixelSize: Style.space(11) }
                        SourceToggle {
                            objectName: "detail-" + detail.modelData.id
                            sourceItem: detail.modelData
                            manager: root.manager
                            appName: root.entry.name
                            visible: !detail.modelData.readOnly
                        }
                    }
                    Label {
                        Layout.fillWidth: true
                        visible: root.technical
                        text: detail.modelData.command || "Command unavailable"
                        font.pixelSize: Style.space(11)
                        wrapMode: Text.WrapAnywhere
                        elide: Text.ElideNone
                    }
                    Label {
                        Layout.fillWidth: true
                        visible: root.technical
                        text: detail.modelData.path + (detail.modelData.line ? ":" + detail.modelData.line : "")
                        color: Qt.alpha(Color.popups.text, 0.70)
                        font.pixelSize: Style.space(11)
                        wrapMode: Text.WrapAnywhere
                        elide: Text.ElideNone
                    }
                    Label {
                        Layout.fillWidth: true
                        visible: !!detail.modelData.readOnly || !!detail.modelData.eligibility
                        text: detail.modelData.readOnly || detail.modelData.eligibility || ""
                        color: Qt.alpha(Color.popups.text, 0.70)
                        font.pixelSize: Style.space(11)
                        wrapMode: Text.WordWrap
                        elide: Text.ElideNone
                    }
                    Label {
                        Layout.fillWidth: true
                        visible: root.technical && (detail.modelData.running !== "unknown" || (detail.modelData.generatedUnits || []).length > 0)
                        text: ((detail.modelData.generatedUnits || []).length ? "Generated systemd unit belongs to this XDG entry. " : "")
                            + (detail.modelData.running !== "unknown" ? "Current service: " + detail.modelData.running + "." : "")
                        color: Qt.alpha(Color.popups.text, 0.70)
                        font.pixelSize: Style.space(11)
                        wrapMode: Text.WordWrap
                        elide: Text.ElideNone
                    }
                    Label {
                        Layout.fillWidth: true
                        visible: detail.modelData.globalEnabled === true && !detail.modelData.readOnly
                        text: "Enabled for all users. Turning it off here also blocks manual starts for your user until you enable it again."
                        color: Qt.alpha(Color.popups.text, 0.70)
                        font.pixelSize: Style.space(11)
                        wrapMode: Text.WordWrap
                    }
                    ActionButton {
                        objectName: "undo-" + detail.modelData.id
                        visible: detail.modelData.canUndo === true
                        text: "Undo last change"
                        link: true
                        fontSize: Style.space(11)
                        focusable: true
                        enabled: !root.manager.busy
                        onClicked: root.manager.request({action:"undo", id:detail.modelData.id, revision:detail.modelData.revision, name:root.entry.name})
                    }
                }
            }
            RowLayout {
                Layout.fillWidth: true
                ActionButton {
                    objectName: "technicalDetails"
                    text: root.technical ? "Hide technical details" : "Technical details"
                    link: true
                    fontSize: Style.space(11)
                    focusable: true
                    onClicked: root.technical = !root.technical
                }
                Item { Layout.fillWidth: true }
                ActionButton {
                    objectName: "removeApplication"
                    visible: root.entry.canRemove === true
                    text: "Remove"
                    fontSize: Style.space(11)
                    enabled: !root.manager.busy
                    tooltipText: "Remove from the list. Startup methods stay disabled."
                    onClicked: root.manager.removeApplication(root.entry)
                }
            }
        }
    }
}
