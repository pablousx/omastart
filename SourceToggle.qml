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
    property var applicationItem: null
    property string appName: sourceItem.name || "Application"
    readonly property var preferred: applicationItem ? Model.preferredSource(applicationItem) : null
    readonly property string blocked: applicationItem ? applicationItem.toggleReadOnly || "" : sourceItem.readOnly || ""
    readonly property bool pending: manager.busy && manager.pendingId === (applicationItem ? applicationItem.id : sourceItem.id)
    readonly property bool masksService: applicationItem
        ? applicationItem.sources.some(function(s) { return s.enabled && s.globalEnabled }) : sourceItem.globalEnabled === true
    readonly property string description: blocked || (pending ? "Saving startup setting" : applicationItem
        ? checked ? "Disable every enabled startup method for this app"
                  : "Enable at next login via " + (preferred ? Model.sourceLabel(preferred.kind) : "the preferred available method")
        : (checked ? "Disable" : "Enable") + " at next login")
    function activate() {
        if (!interactive || busy) return
        if (applicationItem) manager.changeApplication(applicationItem)
        else manager.change(sourceItem)
    }
    rounded: true
    checked: applicationItem ? applicationItem.startupEnabled === true : sourceItem.enabled === true
    interactive: blocked === ""
    opacity: interactive ? 1 : 0.45
    busy: manager.busy
    activeFocusOnTab: interactive
    hasCursor: activeFocus
    Accessible.role: Accessible.CheckBox
    Accessible.name: "Start " + appName + " at login" + (applicationItem ? "" : " via " + Model.sourceLabel(sourceItem.kind))
    Accessible.checked: checked
    Accessible.description: description
    Accessible.onToggleAction: activate()
    Keys.onSpacePressed: activate()
    Keys.onReturnPressed: activate()
    onToggled: activate()
    HoverHandler { id: tooltipHover }
    Controls.ToolTip {
        id: tip
        visible: tooltipHover.hovered
        delay: 500
        width: Style.space(root.applicationItem || root.masksService ? 310 : 215)
        text: root.pending ? "Saving…" : root.busy ? "Checking startup settings…"
            : root.description + (!root.blocked && root.masksService ? ". Turning this off also blocks manual starts until you enable that service again." : "")
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
