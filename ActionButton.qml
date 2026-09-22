import QtQuick
import QtQuick.Controls as Controls
import qs.Commons

Controls.Button {
    id: control
    property bool selected: false
    property bool focusable: true
    property bool bordered: false
    property bool link: false
    property bool iconOnly: false
    property string tooltipText: ""
    property real fontSize: Style.space(12)
    horizontalPadding: Style.space(12)
    readonly property color tint: selected || link ? Color.accent : Color.popups.text
    implicitHeight: Math.max(Style.space(32), label.implicitHeight + Style.space(12))
    implicitWidth: label.implicitWidth + horizontalPadding * 2
    focusPolicy: focusable ? Qt.StrongFocus : Qt.NoFocus
    hoverEnabled: true
    opacity: enabled ? 1 : 0.45
    Accessible.name: text
    Accessible.description: tooltipText
    Controls.ToolTip.visible: hovered && tooltipText !== ""
    Controls.ToolTip.text: tooltipText
    Controls.ToolTip.delay: 700
    contentItem: Text {
        id: label
        text: control.text
        textFormat: Text.PlainText
        color: control.iconOnly && (control.hovered || control.activeFocus || control.down) ? Color.accent : control.tint
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        font.family: Style.font.family
        font.pixelSize: control.fontSize
        font.underline: control.link && !control.iconOnly && control.hovered
        font.bold: control.iconOnly && control.activeFocus
    }
    background: Rectangle {
        visible: !control.iconOnly
        radius: Style.cornerRadius
        color: control.down ? Style.pressedFillFor(Color.popups.text, Color.accent)
            : control.hovered || control.activeFocus ? Style.hoverFillFor(Color.popups.text, Color.accent)
            : control.selected ? Style.selectedFillFor(Color.popups.text, Color.accent) : "transparent"
        border.width: control.link && !control.activeFocus ? 0 : 1
        border.color: control.activeFocus ? Color.accent : Qt.alpha(control.tint, control.selected ? 0.45 : 0.15)
        Behavior on color { ColorAnimation { duration: 100 } }
    }
    HoverHandler { cursorShape: control.enabled ? Qt.PointingHandCursor : Qt.ArrowCursor }
}
