import QtQuick
import Quickshell
import qs.Commons

Item {
    id: root
    property string iconName: ""
    property string appName: ""
    implicitWidth: Style.space(26)
    implicitHeight: Style.space(26)

    Image {
        id: icon
        anchors.centerIn: parent
        width: parent.width
        height: width
        sourceSize.width: width * 2
        sourceSize.height: height * 2
        fillMode: Image.PreserveAspectFit
        asynchronous: true
        source: root.iconName === "" ? "" : root.iconName[0] === "/"
            ? "file://" + root.iconName : Quickshell.iconPath(root.iconName, true)
    }
    Label {
        anchors.centerIn: parent
        visible: icon.status !== Image.Ready
        text: root.appName === "hyprsunset" ? "☾" : root.appName.slice(0, 1).toUpperCase() || "↗"
        font.pixelSize: root.appName === "hyprsunset" ? Style.space(16) : Style.space(12)
        font.bold: true
        color: Color.accent
    }
}
