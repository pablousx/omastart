// Offscreen geometry adapter only. The real Wayland KeyboardPanel is verified
// separately in the installed Omarchy shell; Qt has no offscreen PanelWindow.
import QtQuick

Item {
    required property Item anchorItem
    required property QtObject bar
    property var owner: null
    property Item focusTarget: null
    property bool open: false
    property int contentWidth: 610
    property int contentHeight: 690
    property point cardOrigin: Qt.point(0, 0)
    default property alias contentItem: holder.children
    width: contentWidth
    height: contentHeight
    function fittedContentWidth(value) { return value }
    function cappedContentHeight(value) { return value }
    Item { id: holder; anchors.fill: parent }
}
