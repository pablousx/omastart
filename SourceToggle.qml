pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls as Controls
import qs.Commons
import qs.Ui as Ui
import "Model.js" as Model

Ui.ToggleSwitch {
    id: root
    required property var sourceItem
    required property var manager
    property string appName: sourceItem.name || "Application"
    readonly property bool pending: manager.busy && manager.pendingId === sourceItem.id
    checked: sourceItem.enabled === true
    interactive: !sourceItem.readOnly
    busy: manager.busy
    activeFocusOnTab: interactive
    hasCursor: activeFocus
    Accessible.role: Accessible.CheckBox
    Accessible.name: "Start " + appName + " at login via " + Model.sourceLabel(sourceItem.kind)
    Accessible.checked: checked
    Accessible.description: sourceItem.readOnly || (pending ? "Saving startup setting" : "Applies at next login")
    Accessible.onToggleAction: if (interactive && !busy) manager.change(sourceItem)
    Keys.onSpacePressed: if (interactive && !busy) manager.change(sourceItem)
    Keys.onReturnPressed: if (interactive && !busy) manager.change(sourceItem)
    onToggled: manager.change(sourceItem)
    Controls.ToolTip {
        id: tip
        visible: root.containsMouse
        delay: 500
        width: Style.space(root.sourceItem.globalEnabled ? 310 : 215)
        text: root.pending ? "Saving…" : root.busy ? "Checking startup settings…"
            : (root.checked ? "Disable" : "Enable") + " at next login"
                + (root.sourceItem.globalEnabled ? ". Turning this off also blocks manual starts until you enable it again." : "")
        contentItem: Text {
            text: tip.text
            textFormat: Text.PlainText
            wrapMode: Text.WordWrap
            color: Color.tooltip.text
            font.family: Style.font.family
            font.pixelSize: Style.font.caption
        }
        background: Rectangle { color: Color.tooltip.background; border.color: Color.tooltip.border; radius: Style.cornerRadius }
    }
}
