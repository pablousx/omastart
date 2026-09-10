import QtQuick
import Quickshell
import qs.Commons

Rectangle {
    id: root
    property string iconName: ""
    property string appName: ""
    implicitWidth: Style.space(38)
    implicitHeight: Style.space(38)
    radius: Style.cornerRadius
    color: Qt.alpha(Color.foreground, 0.055)

    Image {
        id: icon
        anchors.centerIn: parent
        width: parent.width * 0.72
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
        font.pixelSize: root.appName === "hyprsunset" ? Style.space(27) : Style.font.subtitle
        font.bold: true
        color: Color.accent
    }
}
