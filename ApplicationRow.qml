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
    signal selected()
    implicitHeight: contents.implicitHeight + Style.space(18)
    radius: Style.cornerRadius
    color: expanded ? Qt.alpha(Color.accent, 0.045) : (hover.containsMouse || hasCursor ? Qt.alpha(Color.foreground, 0.05) : "transparent")
    border.width: expanded || hasCursor ? 1 : 0
    border.color: Qt.alpha(Color.accent, hasCursor ? 0.7 : 0.20)

    function activate() {
        if (!picker) manager.expandedId = expanded ? "" : entry.id
    }
    MouseArea {
        id: hover
        anchors.fill: parent
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
            Layout.fillWidth: true
            spacing: Style.space(12)
            AppIcon { iconName: root.entry.icon; appName: root.entry.name }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: Style.space(4)
                Label { Layout.fillWidth: true; text: root.entry.name; font.bold: true; font.pixelSize: Style.font.subtitle }
                Label {
                    Layout.fillWidth: true
                    text: root.picker ? (root.entry.exists ? "Already has a startup source" : "Installed application") : Model.subtitle(root.entry)
                    color: Qt.alpha(Color.popups.text, 0.70)
                    font.pixelSize: Style.font.caption
                }
            }
            Ui.Button {
                visible: root.picker
                text: root.entry.exists ? "Added" : "+ Add"
                focusable: true
                enabled: root.picker && !root.entry.exists && !root.manager.busy
                onClicked: root.manager.addApplication(root.entry)
            }
            ColumnLayout {
                visible: !root.picker
                spacing: 0
                Label {
                    Layout.alignment: Qt.AlignRight
                    text: root.entry.status || ""
                    color: root.entry.enabled ? Color.accent : Qt.alpha(Color.popups.text, 0.70)
                    font.pixelSize: Style.font.caption
                }
                Label {
                    Layout.alignment: Qt.AlignRight
                    visible: !root.picker && root.entry.system === true
                    text: "Protected"
                    font.pixelSize: Style.space(10)
                    color: Qt.alpha(Color.popups.text, 0.70)
                }
            }
            Item {
                visible: !root.picker
                implicitWidth: Style.space(50)
                implicitHeight: Style.space(34)
                Ui.ToggleSwitch {
                    id: singleToggle
                    objectName: "startupToggle"
                    anchors.centerIn: parent
                    visible: !root.picker && root.entry.sources && root.entry.sources.length === 1
                    checked: root.entry.enabled || false
                    interactive: visible && !root.entry.sources[0].readOnly
                    busy: root.manager.busy
                    opacity: interactive ? 1 : 0.35
                    activeFocusOnTab: interactive
                    hasCursor: activeFocus
                    Accessible.role: Accessible.CheckBox
                    Accessible.name: "Start " + root.entry.name + " at login"
                    Accessible.checked: checked
                    Accessible.onToggleAction: if (interactive && !busy) root.manager.change(root.entry.sources[0])
                    Keys.onSpacePressed: if (interactive && !busy) root.manager.change(root.entry.sources[0])
                    Keys.onReturnPressed: if (interactive && !busy) root.manager.change(root.entry.sources[0])
                    onToggled: root.manager.change(root.entry.sources[0])
                }
                Ui.Button {
                    anchors.centerIn: parent
                    visible: !singleToggle.visible
                    text: root.expanded ? "⌃" : "⌄"
                    focusable: true
                    tooltipText: "Manage startup sources"
                    onClicked: root.activate()
                }
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            visible: root.expanded
            spacing: Style.space(10)

            Label {
                Layout.fillWidth: true
                visible: root.entry.duplicate === true
                text: "More than one source is enabled. Each source is managed independently."
                color: Color.urgent
                font.pixelSize: Style.font.caption
                wrapMode: Text.WordWrap
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
                        Label { text: Model.sourceLabel(detail.modelData.kind); font.bold: true; font.pixelSize: Style.font.caption }
                        Item { Layout.fillWidth: true }
                        Label { text: Model.sourceState(detail.modelData); color: detail.modelData.enabled ? Color.accent : Qt.alpha(Color.popups.text, 0.70); font.pixelSize: Style.font.caption }
                        Ui.ToggleSwitch {
                            checked: detail.modelData.enabled === true
                            interactive: !detail.modelData.readOnly
                            busy: root.manager.busy
                            opacity: interactive ? 1 : 0.35
                            activeFocusOnTab: interactive
                            hasCursor: activeFocus
                            Accessible.role: Accessible.CheckBox
                            Accessible.name: root.entry.name + " via " + Model.sourceLabel(detail.modelData.kind)
                            Accessible.checked: checked
                            Accessible.onToggleAction: if (interactive && !busy) root.manager.change(detail.modelData)
                            Keys.onSpacePressed: if (interactive && !busy) root.manager.change(detail.modelData)
                            Keys.onReturnPressed: if (interactive && !busy) root.manager.change(detail.modelData)
                            onToggled: root.manager.change(detail.modelData)
                        }
                    }
                    Label {
                        Layout.fillWidth: true
                        text: detail.modelData.command || "Command unavailable"
                        font.pixelSize: Style.font.caption
                        wrapMode: Text.WrapAnywhere
                        elide: Text.ElideNone
                    }
                    Label {
                        Layout.fillWidth: true
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
                        font.pixelSize: Style.font.caption
                        wrapMode: Text.WordWrap
                        elide: Text.ElideNone
                    }
                    Label {
                        Layout.fillWidth: true
                        visible: detail.modelData.running !== "unknown" || (detail.modelData.generatedUnits || []).length > 0
                        text: ((detail.modelData.generatedUnits || []).length ? "Generated systemd unit belongs to this XDG entry. " : "")
                            + (detail.modelData.running !== "unknown" ? "Current service: " + detail.modelData.running + "." : "")
                        color: Qt.alpha(Color.popups.text, 0.70)
                        font.pixelSize: Style.space(11)
                        wrapMode: Text.WordWrap
                        elide: Text.ElideNone
                    }
                    Ui.Button {
                        visible: detail.modelData.canUndo === true
                        text: "Undo last change"
                        fontSize: Style.font.caption
                        focusable: true
                        enabled: !root.manager.busy
                        onClicked: root.manager.request({action:"undo", id:detail.modelData.id, revision:detail.modelData.revision})
                    }
                }
            }
        }
    }
}
